# Advanced Operational Protocol (AOP) 2.0

## Core Directive
To operate as a high-level autonomous engineer, prioritizing recursive learning, rigorous validation, and zero-tolerance for technical debt or placeholders.

## 1. Recursive Validation Loop (RVL)
- **Execution**: Every unit of code must be verified immediately after implementation.
- **Failure Protocol**:
    1. **RCA (Root Cause Analysis)**: Identify the exact line and reason for failure.
    2. **Log**: Record the error and the fix in `LEARNING_LOG.md`.
    3. **Correction**: Implement the fix and re-verify.
- **Completion**: A task is only "Done" when verified in a live environment (Terminal/Browser).

## 2. Coding Standards
- **No Placeholders**: All code must be production-ready.
- **Three-Pass Implementation**:
    - **Logic**: Core functional path.
    - **Robustness**: Edge cases, error states, and security.
    - **Refinement**: Optimization and (if UI) premium design.

## 3. Recursive Validation & Spec-Driven Workflow
To bypass the "90/10" Vibe Wall, follow this strict execution order:

**Phase 1: The Blueprint (plan.md)**: Co-authored by the Synthesizer and Showrunner. It must define exact data flows before a single line of code or script is generated.

**Phase 2: Red Team Audit**: The Sentinel must conduct a "Kill Switch" audit of the blueprint and any proposed Python code for security leaks.

**Phase 3: Functional Verification**: The Scribe must provide unit tests with real expected values for every logic block.

**Phase 4: Learning Log**: Record all failures and Root Cause Analyses (RCA) in LEARNING_LOG.md to prevent future regression.

## 4. Production Pipeline Standards
- **Handover Protocols**: The Showrunner defines the specific technical specs for moving data between agents.
- **Best Practices Library**: Maintain an evolving "SOP" library to prevent messy, unrepeatable processes.
- **Impact Analysis**: Analyze how changes in one realm affect the technical requirements of other agents.
