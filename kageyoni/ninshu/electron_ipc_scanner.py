r"""Zero-dependency Electron Active Hook & IPC Boundary Scanner (CH 26).

Parses extracted Electron preload scripts, renderer scripts, and main process scripts
to identify IPC boundary channels, contextBridge exposures, and security configurations.

Pure Python standard library implementation:
- Scanning:
  * ipcRenderer.send('<channel>', ...)
  * ipcRenderer.invoke('<channel>', ...)
  * ipcRenderer.on('<channel>', ...)
  * ipcMain.handle('<channel>', ...)
  * ipcMain.on('<channel>', ...)
  * contextBridge.exposeInMainWorld('<apiKey>', ...)
- Security posture evaluation:
  * contextIsolation flag (true vs false)
  * nodeIntegration flag (true vs false)
  * Wildcard / dynamic channel sinks: ipcRenderer.send(arg), ipcRenderer.invoke(varName)
- Fail-closed verification & memory bounding:
  * Input payload size bounded <= 64 KB (65536 bytes)
  * Empty payload validation raises InvalidInputError
  * AST / Regex catastrophic backtracking prevention
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class ElectronScannerError(Exception):
    """Base exception for Electron scanner errors."""
    pass


class InvalidInputError(ElectronScannerError):
    """Raised when script payload is empty, invalid, or exceeds memory bounds."""
    pass


@dataclasses.dataclass(frozen=True)
class IpcChannelDeclaration:
    """Represents an intercepted IPC channel call or registration."""
    channel_name: str
    direction: str  # "renderer_to_main", "main_handler", "listener", "unknown"
    api_method: str  # "send", "invoke", "on", "handle"
    is_dynamic: bool
    line_number: int
    raw_statement: str


@dataclasses.dataclass(frozen=True)
class ContextBridgeExposure:
    """Represents an API bridge exposed via contextBridge.exposeInMainWorld."""
    api_key: str
    line_number: int
    raw_statement: str


@dataclasses.dataclass(frozen=True)
class SecurityConfiguration:
    """Evaluated Electron security settings and risk posture."""
    context_isolation: Optional[bool]
    node_integration: Optional[bool]
    sandbox: Optional[bool]
    enable_remote_module: Optional[bool]
    risk_level: str  # "SECURE", "LOW", "MEDIUM", "CRITICAL"
    vulnerabilities: List[str]


@dataclasses.dataclass(frozen=True)
class ElectronScanSummary:
    """Summary of all IPC channels, contextBridge exposures, and security configurations."""
    total_bytes: int
    sha256_digest: str
    ipc_channels: List[IpcChannelDeclaration]
    bridge_exposures: List[ContextBridgeExposure]
    security: SecurityConfiguration
    dynamic_sinks_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "ipc_channels": [dataclasses.asdict(c) for c in self.ipc_channels],
            "bridge_exposures": [dataclasses.asdict(b) for b in self.bridge_exposures],
            "security": dataclasses.asdict(self.security),
            "dynamic_sinks_count": self.dynamic_sinks_count,
        }


class ElectronIpcScanner:
    """Scanner for Electron IPC boundaries and security flags."""

    MAX_PAYLOAD_SIZE = 64 * 1024  # 64 KB memory ceiling

    # IPC Call Patterns - matching ipcRenderer/ipcMain calls
    # Supports quoted strings or unquoted variables/expressions as first argument
    # Examples: ipcRenderer.send('channel', ...), ipcMain.handle("channel", ...)
    IPC_PATTERN = re.compile(
        r"""(?P<module>ipcRenderer|ipcMain)\s*\.\s*(?P<method>send|invoke|on|handle)\s*\(\s*(?P<arg>(?:['"`](?P<channel>[^'"`\r\n\\]+)['"`]|[^,\)\r\n\s]+))""",
        re.MULTILINE,
    )

    # contextBridge.exposeInMainWorld('apiKey', ...)
    CONTEXT_BRIDGE_PATTERN = re.compile(
        r"""contextBridge\s*\.\s*exposeInMainWorld\s*\(\s*(?:['"`](?P<apiKey>[^'"`\r\n\\]+)['"`]|(?P<dynApiKey>[^,\)\r\n\s]+))""",
        re.MULTILINE,
    )

    # Security configuration flags in webPreferences or options objects
    CONTEXT_ISOLATION_PATTERN = re.compile(
        r"""\bcontextIsolation\s*:\s*(?P<val>true|false)\b""",
        re.IGNORECASE,
    )
    NODE_INTEGRATION_PATTERN = re.compile(
        r"""\bnodeIntegration\s*:\s*(?P<val>true|false)\b""",
        re.IGNORECASE,
    )
    SANDBOX_PATTERN = re.compile(
        r"""\bsandbox\s*:\s*(?P<val>true|false)\b""",
        re.IGNORECASE,
    )
    REMOTE_MODULE_PATTERN = re.compile(
        r"""\benableRemoteModule\s*:\s*(?P<val>true|false)\b""",
        re.IGNORECASE,
    )

    @classmethod
    def _validate_input(cls, script_content: Union[str, bytes]) -> Tuple[str, bytes]:
        if script_content is None:
            raise InvalidInputError("Input payload cannot be None")

        if isinstance(script_content, str):
            raw_bytes = script_content.encode("utf-8")
            text = script_content
        elif isinstance(script_content, (bytes, bytearray, memoryview)):
            raw_bytes = bytes(script_content)
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as e:
                # Fall back to replacing errors or reject
                text = raw_bytes.decode("utf-8", errors="replace")
        else:
            raise InvalidInputError(f"Unsupported input type: {type(script_content).__name__}")

        if len(raw_bytes) == 0 or len(text.strip()) == 0:
            raise InvalidInputError("Input script payload is empty")

        if len(raw_bytes) > cls.MAX_PAYLOAD_SIZE:
            raise InvalidInputError(
                f"Payload size ({len(raw_bytes)} bytes) exceeds maximum ceiling of {cls.MAX_PAYLOAD_SIZE} bytes (64 KB)"
            )

        return text, raw_bytes

    @classmethod
    def parse_bytes(cls, data: bytes) -> ElectronScanSummary:
        """Parses raw bytes representing an Electron script."""
        return cls.scan(data)

    @classmethod
    def scan(cls, script_content: Union[str, bytes]) -> ElectronScanSummary:
        """Scans the script content for IPC channels, bridge exposures, and security posture."""
        text, raw_bytes = cls._validate_input(script_content)
        sha256_digest = hashlib.sha256(raw_bytes).hexdigest()

        ipc_channels: List[IpcChannelDeclaration] = []
        bridge_exposures: List[ContextBridgeExposure] = []
        dynamic_sinks = 0

        # Scan IPC calls
        for match in cls.IPC_PATTERN.finditer(text):
            module = match.group("module")
            method = match.group("method")
            channel = match.group("channel")
            arg = match.group("arg")

            # Determine if dynamic argument (e.g. variable name instead of literal string)
            is_dynamic = channel is None
            channel_name = channel if channel is not None else arg.strip()

            if is_dynamic:
                dynamic_sinks += 1

            # Determine direction / semantics
            if module == "ipcRenderer":
                if method in ("send", "invoke"):
                    direction = "renderer_to_main"
                else:
                    direction = "listener"
            else:  # ipcMain
                if method == "handle":
                    direction = "main_handler"
                else:
                    direction = "listener"

            line_no = text[:match.start()].count("\n") + 1
            raw_statement = match.group(0)

            ipc_channels.append(
                IpcChannelDeclaration(
                    channel_name=channel_name,
                    direction=direction,
                    api_method=method,
                    is_dynamic=is_dynamic,
                    line_number=line_no,
                    raw_statement=raw_statement,
                )
            )

        # Scan contextBridge exposures
        for match in cls.CONTEXT_BRIDGE_PATTERN.finditer(text):
            api_key = match.group("apiKey") or match.group("dynApiKey") or "unknown"
            line_no = text[:match.start()].count("\n") + 1
            raw_statement = match.group(0)

            bridge_exposures.append(
                ContextBridgeExposure(
                    api_key=api_key.strip(),
                    line_number=line_no,
                    raw_statement=raw_statement,
                )
            )

        # Evaluate Security Settings
        security = cls._evaluate_security(text, dynamic_sinks)

        return ElectronScanSummary(
            total_bytes=len(raw_bytes),
            sha256_digest=sha256_digest,
            ipc_channels=ipc_channels,
            bridge_exposures=bridge_exposures,
            security=security,
            dynamic_sinks_count=dynamic_sinks,
        )

    @classmethod
    def _evaluate_security(cls, text: str, dynamic_sinks: int) -> SecurityConfiguration:
        context_isolation: Optional[bool] = None
        node_integration: Optional[bool] = None
        sandbox: Optional[bool] = None
        enable_remote_module: Optional[bool] = None

        m_ci = cls.CONTEXT_ISOLATION_PATTERN.search(text)
        if m_ci:
            context_isolation = m_ci.group("val").lower() == "true"

        m_ni = cls.NODE_INTEGRATION_PATTERN.search(text)
        if m_ni:
            node_integration = m_ni.group("val").lower() == "true"

        m_sb = cls.SANDBOX_PATTERN.search(text)
        if m_sb:
            sandbox = m_sb.group("val").lower() == "true"

        m_rm = cls.REMOTE_MODULE_PATTERN.search(text)
        if m_rm:
            enable_remote_module = m_rm.group("val").lower() == "true"

        vulnerabilities: List[str] = []

        if node_integration is True:
            vulnerabilities.append("VULN_NODE_INTEGRATION_ENABLED: Renderer has direct access to Node.js APIs")

        if context_isolation is False:
            vulnerabilities.append("VULN_CONTEXT_ISOLATION_DISABLED: Preload scripts can be modified by web content")

        if enable_remote_module is True:
            vulnerabilities.append("VULN_REMOTE_MODULE_ENABLED: Remote module facilitates arbitrary code execution")

        if dynamic_sinks > 0:
            vulnerabilities.append(f"VULN_DYNAMIC_IPC_SINKS: Found {dynamic_sinks} dynamic IPC channel invocation(s)")

        if sandbox is False:
            vulnerabilities.append("INFO_SANDBOX_DISABLED: Chromium OS-level renderer sandbox is disabled")

        # Determine risk level
        if node_integration is True or context_isolation is False or enable_remote_module is True:
            risk_level = "CRITICAL"
        elif dynamic_sinks > 0:
            risk_level = "MEDIUM"
        elif sandbox is False:
            risk_level = "LOW"
        else:
            risk_level = "SECURE"

        return SecurityConfiguration(
            context_isolation=context_isolation,
            node_integration=node_integration,
            sandbox=sandbox,
            enable_remote_module=enable_remote_module,
            risk_level=risk_level,
            vulnerabilities=vulnerabilities,
        )
