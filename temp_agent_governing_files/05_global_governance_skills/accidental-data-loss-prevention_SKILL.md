---
name: accidental-data-loss-prevention
description: |
  Procedural protocol and risk recognition for operations risking irreversible data loss.
  Instructs the agent to halt and request explicit user confirmation before executing destructive commands.
  Note: This is a procedural guideline for the agent; mechanical blocking requires active host hooks or OS-level security boundaries.
license: Apache-2.0
metadata:
  version: v1
  publisher: google
---

# Accidental Data Loss Prevention — Procedural Protocol

> [!CAUTION]
> **STOP AND VERIFY (PROCEDURAL REQUIREMENT)**:
> Before running any command or tool that results in irreversible data loss, you **MUST** obtain explicit user consent.
> When in doubt, ask. It is better to wait for confirmation than to accidentally delete production data or critical project assets.

---

## 1. Scope of Destructive Risk Recognition

Recognize and halt prior to executing commands matching these patterns:

- **Database / SQL:** `DROP TABLE`, `DROP VIEW`, `DROP SCHEMA`, `DROP DATABASE`, `TRUNCATE`, or unconstrained `DELETE` (missing `WHERE` or using `1=1`).
- **Cloud Storage:** `gsutil rm`, `gcloud storage rm` targeting production buckets or recursive wildcards.
- **Infrastructure / Cloud Resources:** `gcloud projects delete`, deleting Spanner/BigQuery datasets, deleting secret manager secrets, or KMS key destruction.
- **Filesystem / VCS:** Recursive deletion of `.git` directories, `git clean -fdx`, `git reset --hard` to remote unpushed commits, or destructive disk formatting.

---

## 2. Mandatory Agent Procedure

1. **Halt Execution:** Do **not** execute the command or dispatch the tool.
2. **Request Explicit Consent:** Present the exact command and explain to the user:
   - The concrete **impact** of the operation.
   - **Why** the operation is proposed.
   - An explicit request for affirmative human approval.
3. **Wait:** Only proceed if the user provides clear, affirmative consent in the conversation.

---

## 3. Enforcement Realism & Trust Boundary

### Procedural vs. Mechanical Protection
- **Cognitive Guidance (This Skill):** This skill defines voluntary cognitive compliance for the agent model. It is *not* an operating system kernel, filesystem sandbox, or hardware security boundary.
- **Mechanical Enforcement (Host Hooks):** True mechanical interception requires an active, qualified host enforcement adapter (such as a verified `PreToolUse` lifecycle hook configured to return `deny` or `force_ask`).

### Uncovered Paths (Limitations)
The following execution paths are **not mechanically blocked** by this skill and must not be represented as secured unless independent host controls exist:
- **Direct Subshell Execution:** Shell commands executed via nested subshells, background daemons, or unmonitored scripts.
- **Obfuscated / Compound Commands:** Commands with variable expansions, aliased utilities, or pipelines not matching known pattern matchers.
- **Tool Boundary Bypasses:** Tools or MCP services that do not pass through the host's `PreToolUse` hook pipeline.
- **External Environment Mutations:** Out-of-band actions executed directly by external processes outside the agent session.
