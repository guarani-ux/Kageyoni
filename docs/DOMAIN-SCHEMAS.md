# Domain and runtime schema guide

`kageyoni/model.py` is the source for the generated `schema.sql`. Domain tables remain normalized and use branch-scoped IDs. Record projections retain evidence, epistemic status, visibility, and version. Foreign keys and engine validation reject wrong references, invalid enum values, location/objective cycles, contradictory custody, and invalid collective records.

The principal domains are:

| Family | Domains | Meaning |
| --- | --- | --- |
| Entity and social | `character`, `faction`, `relationship`, `affiliation`, `will`, `capability`, `ability` | Continuing identities, directional ties, principles, and available practices |
| Character continuity | `character_identity`, `character_aspect`, `character_presence`, `character_lineage` | Existing identity, active/ended facets, embodied presence and transformations |
| Personality and expression | `personality_profile`, `dialogue_turn` | Optional authored type interpretation and exact policy reference; speech separated from private decision grounding. Emotion, comfort, appraisal, thought and regulation extend existing aspects. See `PERSONALITY-SYSTEM.md`. |
| Versioned Will | `will_definition`, `will_expression`, `will_technique`, `will_awakening`, `will_development`, `will_effect` | Definition, bearer-bound expression, learned technique, awakening, evidenced development, and active/residual effect |
| Material and place | `location`, `environment`, `route`, `item`, `loadout`, `loot`, `resource` | Physical and environmental conditions, custody, and scarcity |
| Story and history | `scene`, `arc`, `objective`, `dependency`, `decision`, `thread`, `historical_account`, `knowledge` | Choices, accounts, obligations, beliefs, and unresolved questions |
| Politics and time | `political_claim`, `law`, `accord`, `office`, `clock`, `experience`, `schedule`, `world_rule` | Authority, institutions, clocks, subjective duration, and mechanisms |
| Progression | `progression`, `consequence` | Demonstrated learning and downstream effects |

The property registry adds stable IDs and immutable definition versions. A definition records type, units, applicable facets, constraints, lifecycle, and origin. A value records its subject, context, validity, source event, epistemic status, visibility, and one of `known`, `unknown`, `absent`, `not_applicable`, or `disputed`. Relational facts such as trust remain directional relationships; collective resources are not copied into each member.

Entity profiles keep identity, nature, composition, agency, control, and classification separate. Links record membership, components, splits, merges, and succession. Classification claims keep the claimant and the established mechanism that could make a claim mechanically consequential separate from the subject’s identity.

Runtime tables and their implementation locations are listed in the registry. Use `dependencies` or `registry` operations for impact reports; a dependency marked `declared` or `uncertain` is not presented as verified discovery.

## Will contract invariants

The legacy flat `will` domain is retained. The additive Will domains store
`will-contract/0.1` JSON contracts with immutable identity/version and separate
design status/provenance. A definition has no bearer; an expression binds one
definition to one bearer; a technique references one expression and cannot be
borrowed by another bearer. Exact rule and record references are checked by the
engine, as are ancestry cycles, target kinds, units, non-negative costs, and
source-event/clock/process/consequence links. `will_contract_history` keeps old
contract versions for replay and branches. `will_attempts` pins a prepared
attempt, input snapshot, bounded judgments, and random result without creating a
fictional event; `will_attempt` is the atomic commit event.


Writing interface 1 adds `writing-brief`, `writing-publish`, and `dialogue-receive`. Recipient-scoped `writing_delivery` stores exact presented text; `dialogue_reception` stores a listener interpretation. Both preserve corrections through supersession. See docs/WRITING-HANDOFF.md.
