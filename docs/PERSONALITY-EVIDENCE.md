# Requirement-to-evidence report — release 7

`PERSONALITY-ACCEPTANCE.md` preserves the checklist written before implementation.
The 128-test baseline was run before editing. The final suite contains 148 tests:
the baseline plus 20 integrated personality tests. Actual results are in
`build/personality-test-results.txt`; package/campaign verification is in
`build/personality-delivery-verification.json`.

| Checklist | Observed evidence |
| --- | --- |
| 1. Reuse architecture | Only profile and dialogue-turn domains added. Migration leaves existing event/record content unchanged; actual save retains 165 records and revision 1. |
| 2. Individuality and affect | Same-type characters differ. Fear and joy coexist; comfort is person-specific; expiry removes an input without erasing it. Proposed type and unknown emotion remain unresolved. |
| 3. Likelihood, Will and agency | Same type/Will yields inspection weight 4 for Mira and inquiry 3.6 for Oren. No automatic technique, type change or success buff. |
| 4. Cross-domain use | All six modules receive context. Lower-weight choice is allowed. Natural 20 fails difficulty 25. Independent refusal blocks. Mixed combat/social applies an influence once and spends one effort/hour once. |
| 5. Dialogue and knowledge | Hidden evidence and unsupported assertions fail atomically. Rumor framed as belief creates hearing, not knowledge/trust. Private appraisal/grounding and hidden listener IDs stay out of participant context. Remote delivery requires an extension. |
| 6. Lasting consequences | Journey changes trust, comfort and habit; later options differ from the untouched branch. Practice writes progression and Will development while mastery stays ordinary and unlocks remain empty. |
| 7. Validation and dependencies | Wrong type, code, owner, intervals, references, duplicate influences/contributions and property unit/type/applicability fail. Reports identify affected rules, profiles, domains and event usage. Unsafe retirement is rejected. |
| 8. Continuity and recovery | Interrupted commit keeps one roll across reload and charges once. Concurrent change makes a proposal stale. New rule version preserves old explanation. Branch mutation, snapshots and replay preserve state. Actual v6 pending proposal survives upgrade. |
| 9. Experience | `examples/personality_journey.py` reproduces conversation → trust/comfort/habit → later choice → practice/Will reflection. Existing causal, character, Will and background-process regressions still pass. |
| 10. Delivery | Code, schemas, migrations, actual campaign, fixture, backups, provenance, workflows and evidence are packaged together. Extraction/reopen/resume is checked. Installed skills are unchanged. |

After the explicitly adjudicated supportive exchange, Mira's fixture weights
favor humor (6) and inquiry (5.4), while inspection remains 4. The untouched
branch still favors inspection. These are authored design weights, not measured
psychological probabilities. The practice interval spends one hour/effort,
leaves stamina 4, and grants no mastery. `resume-fixture` is saved pending.

Tests are in `tests/test_personality.py`, alongside all prior regressions.
Local Python 3.12/SQLite, the CLI and Python workflow API were tested. No external
model service, web deployment or GitHub push occurred. GM semantic judgment,
latest-canon reconciliation and previously unimplemented simulation/Will
lifecycles remain boundaries. Original world-engine A–J requirements and their
evidence remain preserved; this release does not claim every earlier outstanding
requirement is complete merely because these tests pass.
