---
name: nin-quarry
description: Systems & Capability Quarry for Ninshū. Indexes extracted AST patterns, protocol schemas, and reusable adapters for future project builds.
---

# Systems & Capability Quarry (`/nin-quarry`)

Indexes proven capability fragments, protocol wire schemas, and pure-Python AST adapters extracted during reverse engineering into a persistent quarry (`vault/systems-quarry.md`), making solved structural engineering immediately reusable across projects.

## Table of Contents

- [1. Quarry Schema: The FSSOV Model](#1-quarry-schema-the-fssov-model)
- [2. Indexing a Capability](#2-indexing-a-capability)
- [3. Retrieving & Transducing Capabilities](#3-retrieving--transducing-capabilities)

---

## 1. Quarry Schema: The FSSOV Model

Every extracted capability in `vault/systems-quarry.md` is stored using the **FSSOV Schema**:
- **Format / Protocol Target (`F`)**: Name, version, and binary/wire container.
- **Structural Invariants (`S`)**: Magic bytes, fixed header layout, endianness, TLV markers.
- **Specimen Receipt (`S`)**: SHA-256 hash and byte length of verified golden specimens.
- **Operational Implementation (`O`)**: Path to pure-Python stdlib parser or AST adapter.
- **Verification Proof (`V`)**: Test suite exit code, peak heap allocation ($\le 64\text{ KB}$), and mutation kill rate.

---

## 2. Indexing a Capability

When an unknown specimen is smelted or an existing protocol is reverse-engineered:
1. Extract its structural grammar into a concise summary.
2. Record its SHA-256 proof and pure-Python implementation path.
3. Append the capability entry to `vault/systems-quarry.md`:

```markdown
### `SYS-CAP-001`: "ELF64 Multi-Architecture Instruction Stream CFG"
- **Target**: Linux / BSD ELF64 (x86_64, ARM64)
- **Invariants**: 0x7fELF magic, 64-bit LE, sequential ModR/M & fixed-width decoding
- **Specimen**: `\\wsl.localhost\Ubuntu\usr\bin\ls` (SHA256: `6a31a7...`)
- **Implementation**: `kageyoni/ninshu/raw_binary_parser.py`
- **Verification**: `tests.test_ninshu_rea_parity` (Exit 0, Peak Heap 5.6 KB)
```

---

## 3. Retrieving & Transducing Capabilities

When embarking on a new software engineering build:
- Query `/nin-quarry` to check if a binary parser, wire sniffer, or IPC scanner already exists in the quarry.
- Import or adapt the verified pure-Python implementation directly into the target project without pulling heavy external dependencies.
