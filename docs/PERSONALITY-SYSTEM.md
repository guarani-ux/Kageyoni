# Personality interface 1 — integrated release 7

Personality participates in the existing character → decision → event →
consequence → later-context loop. Identity, principles, Will, capability,
agency, physical condition, relationships and knowledge remain distinct.

## Authoritative state

| Aspect | Storage and behavior |
| --- | --- |
| Identity, control, facets | Existing character, identity, entity profile and lineage records; personality cannot change these automatically. |
| Principles, drives, commitments, boundaries | Existing interiority aspects; contextual inputs, with explicit change basis and provenance. |
| Optional type interpretation | New `personality_profile`: one per character, `mbti-inspired`, optional four-letter code, proposed/accepted/unknown, note, optional exact policy reference. Only accepted interpretations supply type conditions. |
| Voice and habits | Existing character fields and portrayal aspects; added vocabulary includes attention/thinking style, humor, regulation and verbal style. |
| Mixed feelings and physical condition | Existing condition aspects add emotion, comfort, arousal and expression state alongside separate injuries, fatigue and continuity disruptions. Multiple feelings coexist. |
| Thoughts and appraisal | Existing perspective/interiority aspects add thought, appraisal and self-concept. Records support relationship context, privacy and validity bounds. |
| Trust and obligation | Existing directional relationships; no global trust score. |
| Knowledge and growth | Existing knowledge, observations, progression and Will development. Learning claims do not automatically grant mastery. |
| Will | Existing independent definitions and individual expressions; a policy may associate an exact Will version with an approach. No Will requires a type, and no type grants a Will. |
| Dialogue | New `dialogue_turn`, existing observations and decision judgments. Public words are separate from private grounding. Hearing is not belief or objective truth. |

The requested Myers-Briggs-style labels are optional fictional author
interpretations. The engine does not administer an assessment or claim empirical
psychological prediction. No campaign character received a guessed type or score.

## Executed policies

Define policies through existing `maintain / add_rule`. The definition declares
`kind: personality`, `schema_version: personality-policy/1`, meaning, proposed
or active status, supported scopes, options with positive base weights, and
justified influences. See `examples/personality_journey.py:policy` for a runnable
definition. IDs and definition versions are immutable.

Conditions read an accepted type preference, known active aspect, directional
relationship, exact Will definition held by the character, character field,
locally perceived situation, or declared typed property. Prose comparisons use
exact equality; semantic interpretation remains with the GM. Unknown values
produce unresolved conditions. Absent/not applicable are distinct from unknown.

Matching factors multiply an option's weight once per influence, even if several
records or coordinated activity scopes match. Duplicate IDs and equivalent
option/condition contributions are rejected. Optional influence scopes limit
where an association applies. Shares normalize over supplied options; all-zero
weights return unknown shares. Invalid factors, overflow, wrong units, missing
declarations/references and unsupported scopes are rejected.

**These are authored relative preference weights, not calibrated psychological
probabilities, success modifiers, consent, or a closed action menu.** There is
no personality roll. Choosing a lower-weight approach remains permitted and its
rationale is recorded. Tone labels guide expression without altering dangers,
deadlines or motives. Policies cannot write properties; typed reads use the
existing exact-version dependency, applicability, unit and lifecycle checks.

## Connected resolution

`decision-propose` captures the actor's personality context and the separate
contexts of independent respondents. All six activity modules map to relevant
scopes, with dialogue or Will available as explicit primary scopes. Mixed
actions evaluate the policy once across those scopes. Permission, capabilities,
costs, time and optional action randomness remain in the existing single decision.
Personality weights never enter the d20 modifier. Refusal still blocks an action
that requires agreement.

Committed decisions preserve exact input images, rule/property versions,
weights, chosen approach and GM rationale. Explicit outcomes may change comfort,
trust, appraisal, habits, progression or Will development. Those events then
inform later choices. The engine executes the declared consequence; its emotional
meaning and justification remain recorded GM judgments. A friendly line does
not automatically create trust, and practice does not silently grant mastery.

Validity intervals use existing simulation clocks. Expired aspects stop
contributing while history remains. Free-text ending conditions need an explicit
state change. Reading, chatting and reopening never advance time or decay moods.

## Dialogue workflow

1. Read `personality-context` and the participant's scoped context.
2. Draft from knowledge, intent, voice, relationship and situation. Suspense,
   inquiry, learning, purpose, introspection, connection and lightheartedness
   are available tones, not compulsory ingredients in every line.
3. Call `dialogue-propose` with a normal decision specification, turn, annotated
   claims and named semantic review.
4. Review and use `decision-commit` with explicit acceptance. The utterance is
   recorded in either resolved outcome; other consequences may differ. A blocked
   proposal creates no speech, hearing or cost.

Implemented delivery requires established co-location for speech, gestures and
silence. Remote listeners or a mismatched scene require an extension. The GM
still judges hearing, attention, language and detailed channel conditions;
listing a listener asserts that delivery has been established.

Annotated assertions/beliefs need exact speaker evidence: owned knowledge or
memory, the speaker's observations, or their perceived situation. Unverified
knowledge requires belief/hypothesis framing. Hypotheses and lies may lack
evidence with explicit annotation and review. A character's recorded knowledge
is not certified world truth. Listeners get observations, not automatic beliefs.

The engine validates annotations and references. It **cannot verify every
semantic claim in unrestricted prose, infer the correct emotion, or guarantee
compelling dialogue**. Raw trusted `apply` remains a lower-level authoring path
without all dialogue-workflow checks. Viewer flags are projection controls for
a trusted host, not account authentication or protection from database access.

## Structured commands

Use `python -m kageyoni --db PATH OPERATION --input request.json`; `--input -`
reads stdin. All new workflows accept optional `interface_version`, default `1`.
An incompatible supplied version is rejected before story mutation.

| Operation | Inputs and purpose |
| --- | --- |
| `personality-context` | `character_id`; optional `branch`, `domain`, `domains`, `interlocutors`, `scene`. Supports sanitized `--viewer`. |
| `personality-evaluate` | `rule_id`, `version`, `character_id`; optional `branch`, `context`. GM-only weights/explanations. |
| `personality-record` | `branch`, `request_id`, `expected_revision`, `actor`, `narrative`, `changes`. GM event for profile/aspect/relationship/knowledge changes. |
| `dialogue-propose` | `branch`, `spec`, `turn`, `claims`, `review`. Creates a GM proposal for ordinary `decision-commit`. |
| `decision-propose` | Existing specification plus optional `personality`: domain, interlocutors, scene, exact policy, selected option, rationale. Captures context automatically. |
| `opportunities` | Existing world options plus compatible GM personality guidance. Participant views omit private weight evaluation. |
| `dependencies` | `kind`, `stable_id`, optional `version`. Domain/command/rule/property links, profile consumers and recorded event usage. |

Versions remain separate: legacy SQL marker 2, ordered migration 007, runtime 4,
workflow API 3, character schema 1, decision interface 1, personality interface 1,
property registry 1, resolution rules 1, story state 1, plus branch and record
revisions. Navigation locators name actual entry points and declared typed
dependencies, not every dependency in arbitrary external code or prose.

## Boundaries

Only the separate fixture contains authored types and weights. Canonical
personality/Will associations, numerical freedom, restrained intelligence and
detailed Haki remain unresolved. Gaia and existing Will mechanics are unchanged.
There is no automatic emotion inference, generative model, self-training policy,
always-running NPC or external scheduler.

Local visible environments count as perceivable under the coarse location
model. Undiscovered facts need appropriate visibility/knowledge; fine spatial
perception needs its own mechanic. The GM must still reconcile latest-story
canon. Installed skills and their source bundles were retained; this project
workflow and executable interface contain the new personality instructions.
