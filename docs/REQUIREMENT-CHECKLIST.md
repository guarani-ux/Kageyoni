# Requirement-to-behavior checklist

This checklist was fixed before the final implementation pass. Each row names an observable behavior or a declared judgment boundary; passing row counts alone are not evidence.

| ID | Observable acceptance behavior | Evidence |
| --- | --- | --- |
| A | Person, damaged bridge, water, and family can participate in one event chain; stage-specific properties and a durable consequence are recorded. | `test_mixed_action_resolves_stages_once_and_keeps_uncertainty`, crossing fixture |
| B | A prior event changes an environment and therefore later options; an alternate branch retains the other options. | `test_branch_copies_auxiliary_state_and_isolates_changes`, `test_opportunities_keep_open_action_and_environment_constraints` |
| C | A specialist receives contextual probability contribution without guaranteed success. | `test_contextual_specialist_advantage_does_not_guarantee_success` |
| D | A collective response stores member disagreements independently. | `test_collective_members_keep_disagreement` |
| E | A hidden fact affects an authorized resolution while unauthorized context omits it. | `test_hidden_fact_affects_gm_resolution_without_context_leak` |
| F | A property is defined, assigned, used by a versioned rule, and appears in dependency impact. | `test_property_evolution_dependency_and_old_event` |
| G | A property can be revised/retired with replacement while an old event remains replayable. | `test_property_evolution_dependency_and_old_event` |
| H | Wrong type, unit, applicability, missing references, and dependency cycles are rejected. | `test_applicability_units_constraints_and_unknowns`, `test_rule_dependency_cycle_is_rejected` |
| I | Duplicate requests replay; stale revisions, incompatible skill versions, invalid atomic batches, and interrupted work leave no partial story write. | `test_duplicate_process_request_and_recovery`, `test_interface_mismatch_and_atomic_failure_do_not_mutate_story`, workflow stale-preview tests |
| J | Branch, snapshot, replay, temporal order, persistent consequences, and save/reload survive. | branch auxiliary test, `FreshSessionTests`, `verify`, replay and backup/restore checks |
| K | Background processes advance by elapsed time, event subscriptions mark mandatory work due, supported intervals are step-invariant, blocked work is preserved, and no external scheduler is required. | `test_background_process_advances_once_and_is_step_invariant`, `test_integrated_journey_coordinates_backgrounds_and_later_scene`, process run/subscription tables |
| L | Relevance and presentation are separate from mandatory causal processing and mechanics. | `test_relevance_is_presentation_only` |
| M | Session opening exposes versions/capabilities; opportunities retain an open action; modules use stable registry IDs. | CLI `session`, `opportunities`, module registry, workflow contract |
| N | Actual archive v1 upgrades with backup and migration checksum; the prior v2 DB is preserved and upgraded in a copy. | `build/recovery/*`, migration report in `TEST-REPORT.md` |
| O | One journey coordinates damaged bridge, changing water, family disagreement, specialist context, fatigue, patrol judgment, an expiring opportunity, an offscreen faction process, and a later blocked route; a branch without the earlier crossing choice differs. | `test_integrated_journey_coordinates_backgrounds_and_later_scene` |
| P | Versioned Will contracts preserve definition/expression/technique separation, exact references, historical versions, and branch isolation while retaining the legacy flat Will. | `test_two_bearers_cannot_borrow_technique`, `test_history_version_and_branch_persistence` |
| Q | Will feasibility blocks false preconditions before randomness; one stable attempt pins inputs/rolls; stale commits and caller-edited state deltas are rejected. | `test_false_precondition_blocks_before_randomness_or_cost`, `test_stable_attempt_roll_and_stale_commit`, `test_apply_rejects_caller_injected_delta` |
| R | Will target scope, units, design status, awakening state, hidden contract references, and real predecessor upgrade/recovery are enforced. | `test_scope_and_unit_validation`, `test_awakening_does_not_auto_activate_and_hidden_contract_is_redacted`, `WillUpgradeTests` |

The following remain explicit GM or design boundaries: the numerical freedom formula; “restrained intelligence”; detailed Haki mechanics; unestablished Gaia scope beyond the supplied law; unknown calendar conversions; unsupported free-text effects; and external scheduling or autonomous judgment.
