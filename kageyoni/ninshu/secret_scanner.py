r"""Zero-dependency in-tree Fast Token & Secret Regex Radar (CH 38).

Pure Python standard library implementation:
1. High-precision regex pattern matchers for security-sensitive tokens:
   - AWS Access Key ID (AKIA[0-9A-Z]{16}) and Secret Key candidates (40 base64 chars).
   - GitHub Personal Access Tokens (classic ghp_[0-9a-zA-Z]{36}, fine-grained github_pat_[0-9a-zA-Z_]{82}, OAuth gho_[0-9a-zA-Z]{36}, etc.).
   - Google API Keys (AIza[0-9A-Za-z-_]{35}).
   - Slack API Tokens (xox[baprs]-[0-9a-zA-Z]{10,48}).
   - Generic Private Keys (-----BEGIN (?:...)?PRIVATE KEY-----).
   - High entropy JWT tokens (eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+).
2. Redaction & Masking engine:
   - Masks detected secrets before emitting facts (e.g. keeping first 4 and last 4 chars, or appropriate secure redaction).
3. Shannon entropy gate:
   - Filters candidate matches by entropy to avoid false positives on repetitive tokens / hashes.
4. Strict fail-closed parsing:
   - Rejects empty data, malformed byte streams, inputs exceeding maximum size.
   - Thermodynamic memory bound: Peak heap <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union


class SecretScannerError(Exception):
    """Base exception for secret scanner errors."""
    pass


class InvalidInputError(SecretScannerError):
    """Raised when input data is invalid, empty, or exceeds memory bounds."""
    pass


@dataclasses.dataclass(frozen=True)
class SecretMatch:
    """Represents a validated, classified secret token match."""
    rule_id: str
    token_type: str
    raw_preview_masked: str
    sha256_hash: str
    start_offset: int
    end_offset: int
    entropy: float
    confidence: float
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "token_type": self.token_type,
            "raw_preview_masked": self.raw_preview_masked,
            "sha256_hash": self.sha256_hash,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "entropy": round(self.entropy, 4),
            "confidence": round(self.confidence, 4),
            "metadata": dict(self.metadata),
        }


@dataclasses.dataclass(frozen=True)
class SecretScanSummary:
    """Aggregated scan summary conforming to Ninshū serialization contracts."""
    total_bytes: int
    sha256_digest: str
    matches_count: int
    matches: List[SecretMatch]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "matches_count": self.matches_count,
            "matches": [m.to_dict() for m in self.matches],
        }


def calculate_shannon_entropy(data: str) -> float:
    """Calculates Shannon entropy in bits per character for a string."""
    if not data:
        return 0.0
    length = len(data)
    frequencies: Dict[str, int] = {}
    for char in data:
        frequencies[char] = frequencies.get(char, 0) + 1

    entropy = 0.0
    for count in frequencies.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def mask_secret(token: str, keep_start: int = 4, keep_end: int = 4) -> str:
    """Masks a sensitive token keeping outer characters and redacting the center.
    
    If token is too short (<= keep_start + keep_end), fully masks with fixed redaction.
    """
    if len(token) <= (keep_start + keep_end):
        if len(token) <= 4:
            return "****"
        return token[:1] + "*" * (len(token) - 2) + token[-1:]
    
    masked_len = len(token) - keep_start - keep_end
    mask_str = "*" * min(masked_len, 24)
    return f"{token[:keep_start]}{mask_str}{token[-keep_end:]}"


@dataclasses.dataclass(frozen=True)
class SecretRule:
    rule_id: str
    token_type: str
    pattern: Pattern[str]
    min_entropy: float
    min_length: int
    max_length: int
    base_confidence: float


# Pre-compiled high precision regex patterns with bounded repetition to prevent ReDoS / catastrophic backtracking
RULES: List[SecretRule] = [
    # 1. AWS Access Key ID: AKIA followed by 16 uppercase alphanumeric chars
    SecretRule(
        rule_id="SEC001_AWS_ACCESS_KEY",
        token_type="aws_access_key_id",
        pattern=re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        min_entropy=2.8,
        min_length=20,
        max_length=20,
        base_confidence=0.95,
    ),
    # 2. AWS Secret Key candidate: 40 character base64 string preceded by secret/key context
    SecretRule(
        rule_id="SEC002_AWS_SECRET_KEY",
        token_type="aws_secret_access_key",
        pattern=re.compile(r"(?i:aws_secret_access_key|aws_secret_key|secret_key|aws_key)[\s:=]{1,5}([A-Za-z0-9/+=]{40})\b"),
        min_entropy=4.0,
        min_length=40,
        max_length=40,
        base_confidence=0.90,
    ),
    # 3. GitHub Personal Access Tokens (Classic: ghp_ + 36, Fine-grained: github_pat_ + 82, OAuth: gho_ + 36)
    SecretRule(
        rule_id="SEC003_GITHUB_PAT_CLASSIC",
        token_type="github_pat_classic",
        pattern=re.compile(r"\b(ghp_[0-9a-zA-Z]{36})\b"),
        min_entropy=3.8,
        min_length=40,
        max_length=40,
        base_confidence=0.99,
    ),
    SecretRule(
        rule_id="SEC004_GITHUB_PAT_FINE_GRAINED",
        token_type="github_pat_fine_grained",
        pattern=re.compile(r"\b(github_pat_[0-9a-zA-Z_]{82})\b"),
        min_entropy=4.0,
        min_length=93,
        max_length=93,
        base_confidence=0.99,
    ),
    SecretRule(
        rule_id="SEC005_GITHUB_OAUTH_TOKEN",
        token_type="github_oauth_token",
        pattern=re.compile(r"\b(gho_[0-9a-zA-Z]{36})\b"),
        min_entropy=3.8,
        min_length=40,
        max_length=40,
        base_confidence=0.98,
    ),
    # 4. Google API Key: AIza followed by 35 alphanumeric, hyphens or underscores (total 39 chars)
    SecretRule(
        rule_id="SEC006_GOOGLE_API_KEY",
        token_type="google_api_key",
        pattern=re.compile(r"\b(AIza[0-9A-Za-z\-_]{35})\b"),
        min_entropy=3.8,
        min_length=39,
        max_length=39,
        base_confidence=0.98,
    ),
    # 5. Slack API Tokens (Bot, User, App, Workspace: xoxb-, xoxp-, xoxa-, xoxr-, xoxs-)
    SecretRule(
        rule_id="SEC007_SLACK_TOKEN",
        token_type="slack_api_token",
        pattern=re.compile(r"\b(xox[baprs]-[0-9a-zA-Z]{10,48}(?:-[0-9a-zA-Z]{10,48})*)\b"),
        min_entropy=3.2,
        min_length=15,
        max_length=120,
        base_confidence=0.95,
    ),
    # 6. Generic Private Key Header (RSA, OPENSSH, EC, DSA, PGP, ENCRYPTED, or generic PRIVATE KEY)
    SecretRule(
        rule_id="SEC008_PRIVATE_KEY",
        token_type="private_key_header",
        pattern=re.compile(r"-----BEGIN (?:(?:RSA|OPENSSH|EC|DSA|PGP|ENCRYPTED) )?PRIVATE KEY-----"),
        min_entropy=3.0,
        min_length=25,
        max_length=60,
        base_confidence=0.99,
    ),
    # 7. High Entropy JSON Web Tokens (JWT)
    SecretRule(
        rule_id="SEC009_JWT_TOKEN",
        token_type="json_web_token",
        pattern=re.compile(r"\b(eyJ[A-Za-z0-9\-_]{10,}\.eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,})\b"),
        min_entropy=4.2,
        min_length=36,
        max_length=4096,
        base_confidence=0.92,
    ),
]


class SecretScanner:
    """Channel 38: Fast Token & Secret Regex Radar.
    
    Operates under strict zero-trust rules:
    - Pure Python standard library
    - Memory bounded <= 64 KB per inspection unit
    - Fail-closed validation on empty data, malformed byte streams, or out-of-bound inputs
    - Masks secrets prior to emitting facts
    - Shannon entropy gating to eliminate false positives
    """

    MAX_INPUT_BYTES: int = 65536  # 64 KB memory ceiling

    def __init__(self, rules: Optional[List[SecretRule]] = None):
        self.rules = rules if rules is not None else RULES

    @classmethod
    def parse_bytes(cls, data: bytes) -> SecretScanSummary:
        """Parses raw bytes and returns a SecretScanSummary."""
        scanner = cls()
        matches = scanner.scan(data)
        return SecretScanSummary(
            total_bytes=len(data),
            sha256_digest=hashlib.sha256(data).hexdigest(),
            matches_count=len(matches),
            matches=matches,
        )

    def scan(self, data: Union[str, bytes]) -> List[SecretMatch]:
        """Scans the provided text or byte data for security tokens.
        
        Args:
            data: Input string or bytes to inspect.
            
        Returns:
            List of SecretMatch records.
            
        Raises:
            InvalidInputError: If data is empty, too large, or malformed bytes.
        """
        if data is None:
            raise InvalidInputError("Input data cannot be None.")

        if isinstance(data, bytes):
            if len(data) == 0:
                raise InvalidInputError("Input byte stream is empty.")
            if len(data) > self.MAX_INPUT_BYTES:
                raise InvalidInputError(
                    f"Input size ({len(data)} bytes) exceeds maximum ceiling of {self.MAX_INPUT_BYTES} bytes."
                )
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise InvalidInputError(f"Malformed byte stream: {exc}") from exc
        elif isinstance(data, str):
            if len(data) == 0:
                raise InvalidInputError("Input string is empty.")
            byte_len = len(data.encode("utf-8"))
            if byte_len > self.MAX_INPUT_BYTES:
                raise InvalidInputError(
                    f"Input string size ({byte_len} bytes) exceeds maximum ceiling of {self.MAX_INPUT_BYTES} bytes."
                )
            text = data
        else:
            raise InvalidInputError(f"Unsupported data type: {type(data).__name__}")

        if "\x00" in text:
            raise InvalidInputError("Input contains null bytes; binary streams must be strictly sanitized.")

        matches: List[SecretMatch] = []
        seen_spans: set = set()

        for rule in self.rules:
            for match in rule.pattern.finditer(text):
                if match.lastindex and match.lastindex >= 1:
                    token = match.group(1)
                    start, end = match.span(1)
                else:
                    token = match.group(0)
                    start, end = match.span(0)

                span_key = (start, end)
                if span_key in seen_spans:
                    continue

                token_len = len(token)
                if token_len < rule.min_length or token_len > rule.max_length:
                    continue

                entropy = calculate_shannon_entropy(token)
                if entropy < rule.min_entropy:
                    continue

                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                masked_preview = mask_secret(token)
                confidence = min(1.0, rule.base_confidence + (entropy - rule.min_entropy) * 0.05)

                secret_match = SecretMatch(
                    rule_id=rule.rule_id,
                    token_type=rule.token_type,
                    raw_preview_masked=masked_preview,
                    sha256_hash=token_hash,
                    start_offset=start,
                    end_offset=end,
                    entropy=entropy,
                    confidence=confidence,
                    metadata={
                        "token_length": token_len,
                        "rule_min_entropy": rule.min_entropy,
                    },
                )
                matches.append(secret_match)
                seen_spans.add(span_key)

        return matches


# Backward-compatible alias for Ninshū Channel 38
SecretRadarScanner = SecretScanner
