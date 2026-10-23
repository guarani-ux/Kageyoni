---
name: nin-probe
description: Deep multi-architecture binary, memory, and runtime inspector for Ninshū. Handles PE, ELF, Mach-O, ASAR, IPC, JS AST, PCAP, TLS, and memory ranges.
---

# Deep Binary & Runtime Inspector (`/nin-probe`)

Inspects binary structures, symbol tables, runtime boundaries, and wire captures across native and managed execution targets using Ninshū's in-tree parsers.

## Table of Contents

- [1. Supported Targets & Channels](#1-supported-targets--channels)
- [2. Binary Format Inspection](#2-binary-format-inspection)
- [3. Runtime Boundary & Hook Inspection](#3-runtime-boundary--hook-inspection)
- [4. Network & Telemetry Extraction](#4-network--telemetry-extraction)

---

## 1. Supported Targets & Channels

- **Native Executables**: Windows PE/COFF (`CH 01`), Linux/BSD ELF (`CH 02`), macOS Mach-O (`CH 03`), Raw Binaries (`CH 15`).
- **Managed & Bytecode**: .NET CLR (`CH 09`), NativeAOT (`CH 10`), WebAssembly (`CH 11`), EVM (`CH 12`), Go (`CH 13`), Rust (`CH 14`).
- **Dynamic & Memory**: Frida Stalker (`CH 17`), Dynamic Memory Interceptor (`CH 18`), GDB/Pwndbg Core Dumps (`CH 19`), Rizin Debug (`CH 20`), LLDB (`CH 21`), Process Lineage Supervisor (`CH 23`).
- **App Containers & Web**: Electron ASAR (`CH 25`), Electron IPC Hooks (`CH 26`), Chrome DevTools Protocol (`CH 27`), Android DEX/APK (`CH 28`), Jadx (`CH 29`), Apktool (`CH 30`), Dart/Flutter (`CH 31`), JEB (`CH 32`), Deep JS AST (`js_ast_analyzer`).
- **Network & Forensics**: PCAP Flow Reconstructor (`CH 33`), TLS Handshake & SNI (`CH 34`), Mitmproxy Flows (`CH 35`), Protobuf Sniffer (`CH 36`), SQLite Engine (`CH 37`), Secret Regex Radar (`CH 38`).

---

## 2. Binary Format Inspection

Execute target binaries directly through `ninshu_bridge.py`:

```bash
# Inspect Linux ELF binary
python domains/systems/scripts/ninshu_bridge.py execute --channel 2 --file /usr/bin/ls

# Inspect Windows PE executable
python domains/systems/scripts/ninshu_bridge.py execute --channel 1 --file C:/Windows/System32/notepad.exe

# Disassemble raw instruction stream with basic block CFG edges
python domains/systems/scripts/ninshu_bridge.py execute --channel 15 --file /path/to/firmware.bin
```

---

## 3. Runtime Boundary & Hook Inspection

- **Electron IPC Scanner (`CH 26`)**: Scans preload and renderer scripts to extract `ipcRenderer.send/invoke` channels and verify whether `contextIsolation` is enabled and `nodeIntegration` is disabled.
- **Deep JS AST Analyzer (`js_ast_analyzer.py`)**: Extracts Webpack/Vite module chunk tables, recovers base64/hex obfuscated strings, and traces dataflows into sensitive sinks (`eval`, `Function`, `innerHTML`, `postMessage`).
- **Process Lineage Supervisor (`CH 23`)**: Issues and validates cryptographically bound run tokens (`run_token = sha256(timestamp || pid || ppid || salt)`), tracking execution ancestry and enforcing time/memory leases.

---

## 4. Network & Telemetry Extraction

- **PCAP Flow Reconstructor (`CH 33`)**: Reconstructs TCP stream sessions and reassembles packet payloads.
- **TLS Handshake Extractor (`CH 34`)**: Extracts SNI hostnames, cipher suites, and supported extensions from ClientHello records.
- **Protobuf Sniffer (`CH 36`)**: Decodes arbitrary wire-format protobuf payloads into typed varints, fixed32/64 numbers, and length-delimited sub-records without needing the original `.proto` file.
