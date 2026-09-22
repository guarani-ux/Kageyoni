# V3 independent adversarial review

Date: 20 September 2026. Scope: the bounded experience, lesson, qualification and later-expression loop. This reviewer changed only `tests/test_v3_adversarial.py` and this review; implementation fixes were made by the owning agents. All executed fixtures used disposable synthetic databases. No campaign was opened or advanced by this review.

## Executed result

```sh
python3 -m unittest discover -s tests -p test_v3_adversarial.py -v
```

Final result: **14 tests passed in 0.966 seconds**. This is the focused independent result, not the whole project test count.

The positive scenario begins with an experimental method that chooses a longer route. A separate, later world event records strain. An operator proposes and qualifies a conditional intervention. On a later task with different candidate distances, the intervention changes the choice to the shorter route while the stored base method digest and parameters remain unchanged. An unqualified proposal has no effect; a different context keeps the original choice. The resulting contribution identifies the exact applied lesson and review.

## Reproduced defects and fixes

| Finding | Reproduction | Corrected behavior |
|---|---|---|
| Public record visibility did not ensure a measured field was public | An owner observation cited a public resource's `data.holder`, which referred to a hidden character. A public lesson based on it incorrectly changed another viewer's choice. The initial 12-test run had 11 passes and this failure. | Observation projection checks the measured field and referenced identities. The owner can inspect the observation; an unauthorized viewer cannot receive it or use its lesson. |
| A descendant lesson could retain influence from a hidden ancestor observation | A second contribution used a qualified lesson, then supplied evidence for a second lesson. Hiding the character referenced by the first observation excluded the first lesson but still allowed the second to affect the public choice. The subsequent 13-test run had 12 passes and this failure. | Historical contributions recheck their exact original lesson and review dependencies, including supporting and contrary observations. Traversal uses an ancestry guard and does not rerun Expression or substitute a current review for a historical one. The descendant regression now passes. |

A further review finding concerned owner-written outcome rationale. Outcomes have no separate declaration publishing that note. The nonowner projection now omits it while retaining permitted measurements and their attributed outcome status. A canary assertion verifies both the exclusion and preservation of the usable public measurements.

## Other independently exercised boundaries

- A completed calculation plus an unrelated newer event does not turn an old source into a later outcome observation.
- An unknown outcome or a null field cannot support the tested known-outcome qualification path.
- Context matching distinguishes `true` from `1`, and distinguishes a supplied condition from an absent or null value.
- A proposal does not affect behavior before qualification. A qualified lesson pins the base method revision; assigning a new method revision does not inherit the old lesson.
- Private supporting and contrary observations cannot enter public lesson selection or reveal their identifying canaries.
- Contesting a lesson invalidates an earlier preparation packet. Replaying an old qualification request returns its receipt without reactivating the contested lesson.
- A cosmetic revision with unchanged intervention and evidence cannot reset a contested lesson into qualification.
- Repeated outcome records from one contribution and observation event retain one underlying origin rather than becoming independent votes.
- Public learning reads and subsequent expression survive reopening, including contributions that already used an earlier lesson, without recursive reexecution of current behavior.

## What the evidence establishes

The tests establish a persistent, attributable mechanism for an explicitly reviewed lesson to affect a later bounded decision. They also establish the listed failure and privacy controls in the synthetic scenarios.

Outcome interpretation, context relevance and lesson qualification remain operator judgments. Exact source equality establishes recorded provenance, not source truth or causal explanation. Parameter changes are authored interventions; the engine does not independently discover or validate a general cognitive strategy. These fixtures do not establish improved creative performance, real-world competence, autonomous judgment, cross-domain transfer or a network advantage. Repeated observations do not become independent evidence merely because they have different record IDs.

No outstanding blocker remained in this reviewed scope after the final focused run. Migration, complete regression, packaging and real-campaign preservation are owned by the root integration record and are not claimed by this review.
