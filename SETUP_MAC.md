# Kageyōni: macOS / Darwin Quickstart

Kageyōni runs natively on macOS (Apple Silicon & Intel) with **zero external dependencies**. All core causal mechanics, the 48-channel Ninshū patchbay, and emergence engines use pure Python 3.10+ standard library.

---

## 3-Command Fast Track

```bash
# 1. Clone repository
git clone https://github.com/guarani-ux/Kageyoni.git && cd Kageyoni

# 2. Verify platform & engine integrity
python3 -m tools.runner cadence

# 3. List or initialize native outposts
python3 -m tools.runner outpost list
```

---

## Architectural Highlights on macOS

### 1. Pure Python 3.10+ Standard Library (Zero-Pip Core)
- No `pip install` required for Kageyōni core.
- Works out-of-the-box with macOS default Xcode CLI tools / Homebrew Python:
  ```bash
  python3 --version  # Requires >= 3.10
  ```

### 2. Dynamic Relative Path Resolution
- All engine modules (`kageyoni.emergence.*`, `kageyoni.ninshu.*`, etc.) dynamically resolve repository roots relative to `__file__`.
- Hardcoded Windows drive paths (`C:/Kageyoni`) and WSL UNC mirrors are bypassed automatically on non-Windows platforms.
- Set `SHINOBI_ROOT` (defaults to `~/shinobi`) if pairing with Shinobi runtime state:
  ```bash
  export SHINOBI_ROOT="$HOME/shinobi"
  ```

### 3. Native POSIX Outpost Sandbox
- On macOS/Darwin, downstream outposts operate natively in `$HOME/outposts/` (no WSL2 translation layer required).
- Custom outposts directory can be specified via `KAGEYONI_OUTPOSTS_DIR`:
  ```bash
  export KAGEYONI_OUTPOSTS_DIR="$HOME/my-outposts"
  ```
- Create and test an isolated downstream outpost:
  ```bash
  # Provision new isolated outpost with dedicated .venv
  python3 -m tools.runner outpost create my-subsystem --mandate "Isolated stream processing"

  # Run Day-0 verification tests natively
  python3 -m tools.runner outpost test my-subsystem

  # Execute pipeline
  python3 -m tools.runner outpost run my-subsystem
  ```

---

## Verification Suite

Run quick AST and syntax qualification across all modules:

```bash
python3 -m py_compile $(find kageyoni tools -name "*.py")
```
