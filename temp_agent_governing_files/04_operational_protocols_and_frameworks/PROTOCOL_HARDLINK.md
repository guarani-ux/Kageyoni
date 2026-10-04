# PROTOCOL_HARDLINK.md: Python & Security

## Scribe: Python Logic Protocol
1. **Type Hinting**: Mandatory for all function signatures.
2. **Error Handling**: `try-except` blocks must log to `LEARNING_LOG.md`.
3. **Unit Testing**: Every logic block must have a corresponding `tests/` file with real expected values.
4. **Execution**: Scripts are run via `python -m` to ensure module-path consistency.

## Sentinel: Security Protocol
1. **Kill Switch**: If a script makes an unauthorized external request, the process must be terminated immediately.
2. **Data Sanitization**: All user inputs and API responses must be validated before processing.
3. **Audit Trail**: Every terminal command run by the agent is logged for security review.
4. **Zero-Trust**: No code is executed without a pre-run "Sentinel Audit" of the script content.
