---
name: reverse-engineering
description: Reverse engineering, binary analysis, protocol reconstruction, and application boundary inspection across PE/.NET, Electron, JavaScript, and native binaries.
---

# Reverse Engineering & Binary Inspection (REA Capability)

This operational capability empowers all agents, Shinobi participants, and Celestials to deconstruct compiled binaries, applications, and network/RPC protocols into falsifiable structural evidence.

## 1. Physical Carriers & Entry Points

- **Primary Carrier**: `tools/reverse_engineer.py`
  - Zero-dependency inspection engine for PE/.NET assemblies, JavaScript/Electron applications, and native binaries.
- **REA Engine**: `external_repos/rea` (morluto/rea)
  - Advanced decompiler bridges (Hopper, Ghidra, Cutter, NativeAOT, ASAR, WASM).
- **Shinobi Operative Form**: `shinobi/forms/reverse-engineering.json`
  - Declares the operational form for situated encounters and scout horizon queries.

## 2. CLI Usage & Commands

```sh
# Inspect a PE/.NET assembly, DLL, or executable
python tools/reverse_engineer.py inspect <path_to_binary> --json

# Inspect a JavaScript / Node.js / Electron application directory
python tools/reverse_engineer.py inspect <path_to_app_folder> --json

# Scan binary strings with regex filtering
python tools/reverse_engineer.py scan <path_to_binary> --filter "protobuf|cheetah|action" --limit 50

# Check status of the REA compiled runtime bridge
python tools/reverse_engineer.py rea-status
```

## 3. Supported Inspection Formats

1. **.NET CLR Assemblies & PE Binaries**:
   - Parses COFF and Optional Headers (PE32 / PE32+).
   - Extracts CLI Runtime Headers and parses the `BSJB` Metadata Root.
   - Extracts `#Strings`, `#US` (User Strings), `#Blob`, and `#GUID` streams.
   - Classifies types, properties, methods, backing fields, and Protobuf contracts without requiring an external .NET runtime or decompiler.
2. **JavaScript, Node.js & Electron Bundles**:
   - Parses `package.json` entrypoints, dependencies, scripts, and exports.
   - Identifies Electron main processes, preload scripts, and active IPC channels (`ipcMain` / `ipcRenderer`).
3. **Native Binaries (PE / ELF / Mach-O)**:
   - Identifies magic signatures, architectures (x86, x64, ARM64), sections, and printable ASCII/UTF-8 strings.

## 4. Operational Invariants & Reversibility Governance

- **Tier 0 (Autonomous Fast Loop)**:
  - Static byte reading, metadata parsing, string extraction, and AST analysis proceed autonomously without human pause.
- **Tier 1 (Local Destructive / Environment Mutation Gate)**:
  - Building REA dependencies (`npm ci && npm run build:cached`) or launching dynamic kernel/driver hooks requires explicit human authorization with:
    `WARNING: POTENTIALLY DESTRUCTIVE ACTION`
- **Epistemic Partitioning**:
  - Raw extracted bytes, offsets, and symbol strings are `OBSERVED`.
  - Architectural role classifications, dataflow models, and system diagrams are `INFERRED`.
  - Never fabricate or guess missing type signatures; represent absences explicitly.
