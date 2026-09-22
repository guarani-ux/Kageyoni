# Independent V4–V8 review

20 September 2026. The acceptance obligations were frozen in [V4-V8-ACCEPTANCE.md](V4-V8-ACCEPTANCE.md) before these tests. This review owns no implementation modules and uses only disposable worlds, local files and subprocesses. It did not change the campaign.

The final focused run passed **16 tests in 1.726 seconds**:

```bash
python3 -m unittest discover -s tests -p test_v4_v8_adversarial.py -v
```

The test file is [test_v4_v8_adversarial.py](../tests/test_v4_v8_adversarial.py). It calls the actual installed services and SQLite store. Repository tests execute real Python tests; the interruption test kills a separate process after the file effect and before its receipt. No transfer qualification, contribution or policy result is mocked.

## Findings and corrections

| Finding | Evidence and disposition |
|---|---|
| Terminal encounter entry bypassed closure | Independently reproduced: a definition whose initial state was completed/achieved started successfully with a required loop still open. The first 16-test run failed because no rejection occurred. V4 now requires an active initial state; the regression passes. |
| Resolving a parent ignored required nested children | Source review identified that only explicit `depends_on` edges were checked; `parent` containment was ignored. V4 added the required-child guard before the final valid runtime probe. The test rejects early parent resolution, then executes the same action after child completion. This was a code-review finding, not a recorded pre-fix runtime reproduction. |
| Caller-written pass flags could qualify a transfer | Root identified the original qualification gap. The independent negative test now rejects an artifact containing invented `passed: true` checks. Genuine positive/negative mapped-operation trials and an executed repository receipt qualify through the real services. |
| Manual waiting/failure could release downstream work | Source review identified unconditional completion of manual replies. The fixed API requires an explicit disposition. The independent test retains waiting and failed states, prevents the dependent write, then consumes the actual approved value when completed. |
| Different provenance could give duplicate calculations extra weight | Source review found that source metadata was part of the calculation signature. V6 now deduplicates identical checked calculation bodies for the same task. A real three-node test uses separate method origins and verifies the copied calculation does not change the two-node ranking or claim independent corroboration. |
| Captured context could retain newly hidden nested references | The original read path checked referring record visibility without comparing its permitted projection. V5 added projection revalidation before the independent probe. A resource remains public while its holder becomes hidden; the old viewer workspace is rejected, while authorized owner history remains readable. |
| A generated draft could be mistaken for completed production | Review distinguished source coverage from satisfying a brief. V5 now explicitly records the broader task objective as unresolved and obligation satisfaction as not established. The independent test preserves a cancellation for brief A and a required obligation for brief B. |

The review also challenged missing downstream output consumption, repository preparation recovery and the portable artifact-root mismatch. Their owners added actual `content_from` consumption, explicit preparation reconciliation, and restoration under the engine's canonical artifact root. The independent manual-flow test verifies actual value consumption; owner tests cover preparation and relocated bundles.

## What the independent run establishes

| Boundary | Executed evidence |
|---|---|
| Character and encounter | Sparse introduction preserves unknown capabilities and separate Named Will interpretation across reopening and exact retry. Required children and terminal entry cannot fabricate closure. Pending judgment survives reopening; invalid/stale answers fail and exact delivery records one accepted choice. |
| Destination qualification | Reversing a directed relationship blocks a proposed mapping. A wrong expected ordering fails an executed trial. A valid source-bound ordering plus an invented-number negative control qualifies, then changes actual document section order while retaining its method/trial identity. |
| Document work | Actual file bytes become quoted passages. Missing values, dates, visual evidence and premise remain unknown. Source instructions do not change engine settings. Separate brief obligations survive. Exact artifact bytes reopen, unchanged world return succeeds, and changed-world return blocks without overwriting newer state. |
| Collective calculation | Actual contribution bodies and disagreements are present; copied calculations do not add votes. An unconfigured contributor produces blocked output with no selected candidate. |
| Repository and pipeline | A real two-test local repair, mapped method execution and exact candidate receipt precede qualification. Candidate mutation blocks promotion; restored checked bytes promote exactly. Manual failures block required work. A real process exit after fsync requires reconciliation and retains one attempt rather than writing twice. |
| Operational policy | Missing or insufficient trials cannot activate a policy, and proposals cannot remove checks. A mixed accepted/rejected corpus records fewer actual check calls with equal decisions. The activated policy is used by a real pipeline write; rollback preserves the earlier attempt and restores the previous policy for later checks. |

## Scope of the conclusion

These tests demonstrate bounded mechanisms, failure controls and honest unresolved states. They do not establish semantic truth, professional competence, character mastery, creative quality, representative production savings or general collective advantage. The numerals, character profiles and arithmetic repair are deliberately synthetic fixtures. Exact passage matching verifies supplied words and values; it does not establish that the operator's conceptual mapping is correct.

The independent file is not the complete release gate. Root owns the combined regression run, complete journey/document/collective/repository/pipeline/export chain, menu checks, unchanged campaign migration and relocated recovery evidence. Peer suites additionally exercise actual authored Will costs and dialogue, document composition body consumption and disagreement, retry/version budgets, artifact interruption and bundle corruption. Their results must accompany the release rather than be inferred from the 16 tests here.

The planned native-host A/B/C/D comparison is a separate, single-task diagnostic. Even when executed with preserved inputs and outputs, one current host is neither independent nor blinded, and that comparison cannot be represented as the blueprint's broader 32-run study or proof of general advantage.
