# WORKFLOW_SOPS.md: Project Alpha-1

## 1. Environment & Dependency SOP
- **Python**: Use virtual environments (`venv`) for all logic blocks.
- **Security**: No `.env` files in git; use Sentinel-verified secrets management.

## 2. Communication SOP (Agent-to-Agent)
- **Script -> Blueprint**: All data flows must be mapped in `plan.md` before execution.
- **Handover**: Each logic block must pass Scribe verification before being integrated.

## 3. Deployment SOP
- **Validation**: Every feature must be verified in the target environment (browser/terminal).
- **Audit**: Sentinel must conduct a "Kill Switch" audit post-deployment.
