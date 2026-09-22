# V2 consequential expression contract

Status: implemented bounded operations, not general character cognition or cross-workspace transfer.

A node's assigned, versioned method changes a calculation or a check of supplied evidence. Display names do not select behavior. Method revisions can change fields, weights, direction, or the registered operation. The calculation produces reasons and exact source-field references, and the contribution service preserves its input and output identity. No paid model service is used.

## Entry points

```python
expression = Expression(engine)
source = expression.source_ref(branch, record_id, viewer=None)
packet = expression.prepare(branch, character_id, task, viewer=None, workspace_id=None)
result = expression.execute(branch, character_id, task, viewer=None,
                            workspace_id=None, prepared=packet)
```

`prepare` uses one transaction snapshot across character visibility, source revisions, field values, and method assignments. It may run pure calculations to determine whether supported candidates exist. `execute` regenerates the packet from current inputs and rejects any supplied packet that differs. It creates no story event and has no external effects. The application contribution boundary separately stores the checked result and exact artifact bytes transactionally.

The workspace in V2 is the node's bound `world:<branch>` workspace. A task domain is an explicit label chosen for the bounded trial. An authorized assignment is `experimental`; it does not establish expertise in the domain.

## Task input

```json
{
  "task_id": "editing-choice",
  "revision": 1,
  "domain": "planning",
  "objective": "Compare the supplied hypothetical editing plans.",
  "source_refs": [
    {"domain": "resource", "id": "short-time", "record_revision": 1,
     "snapshot_hash": "<64-character current record SHA-256>"}
  ],
  "candidates": [
    {"id": "short", "label": "Short edit", "claims": {
      "time": {"value": 20, "evidence": [
        {"source_ref": {"domain": "resource", "id": "short-time", "record_revision": 1,
                        "snapshot_hash": "<same SHA-256>"},
         "field_path": ["data", "quantity"]}
      ]}
    }}
  ]
}
```

`method_ids` optionally selects a nonempty subset of currently permitted methods. A requested unavailable method is rejected; omitting this field uses the permitted experimental methods for the task domain. Each candidate can supply `counterclaims` in the same shape as `claims`.

Source identity is exact: domain, stable ID, record revision and full-record digest. Every claim reference must also be in the declared task sources. Field paths resolve only through the caller's permitted record projection and must begin with `data`. Administrative provenance fields cannot be used as claims. A boolean does not match a number. A missing, null or unequal field is unsupported. Hidden and absent sources produce the same generic error before any source body is exposed.

Exact field equality establishes only that the calculation uses a recorded value. Calling `resource.quantity` "safety" does not establish that it measures safety. The input's semantic mapping remains an attributed task assumption. Source statuses such as proposed or reported remain visible; a calculation does not promote them to truth.

## Registered operations

| Operation | Parameters | Result |
|---|---|---|
| `constraint_rank` | `criteria`: distinct `{field, weight, direction, required?}` objects; direction is `maximize` or `minimize`; `max_results` optional | Weighted sum over exact supported numeric inputs. Reasons explain each term. Unsupported or conflicting required values exclude that candidate. Optional missing values remain explicit unknowns and contribute no score. |
| `counterexample_check` | `fields`: distinct field names | Identifies supplied unsupported claims, unresolved counterclaims, contradictory recorded values, and the absence of a supplied conflict. It cannot conclude that no other counterexample exists. |

Ranking uses supplied weights without inventing normalization or converting incompatible units. Scores preserve finite numerical precision and are recomputed with exact rational arithmetic. Candidate IDs break equal-score ties; names and input ordering do not. There must be at least one supported candidate for a ranking contribution to complete.

## Authored conditions and checks

Condition strings are registered identifiers, not natural-language instructions that the code pretends to understand.

| List | Recognized identifiers | Effect |
|---|---|---|
| `preconditions` | `task_domain_matches`, `sources_current` | Exact domain assignment and current source checks are always enforced. |
| `preconditions` | `claims_match_recorded_fields` | All supplied claims and counterclaims must match their cited visible fields; otherwise the whole method is blocked. |
| `preconditions` | `numeric_criteria` | Ranking only. Non-numeric supplied criterion values block the method. |
| `failure_conditions` | `stale_source` | Stale sources are rejected before contribution. |
| `failure_conditions` | `missing_support`, `conflicting_evidence` | Ranking only. Required missing or conflicting candidate values are excluded; no supported candidate blocks the operation. |
| `checking_procedure` | `check_source_fields`, `compare_counterclaims` | Exact source-field and supplied-counterclaim checks. |
| `checking_procedure` | `recompute_scores` | Ranking only. Scores are recomputed independently using rational arithmetic. |

Unknown identifiers, authored prose, inapplicable checks, or unknown operation kinds produce a bounded waiting packet for a human or the current subscription-native host. Creating that packet does not execute a model. V2 does not auto-accept a host response or convert it into authority. No incomplete manual operation receives a completed artifact.

## Output and boundaries

`prepare.phase` is `ready`, `waiting`, or `blocked`. Successful execution returns `phase: completed`, `outcome: contributed` and an `application/json` artifact whose `digest` is the canonical SHA-256 of `content`. The binding contains the exact task fingerprint, node, viewer, branch, workspace, world and profile revisions, method and assignment revisions, and the union of task and method source references.

`objective: achieved` is scoped explicitly to `objective_scope: registered_operation`. `task_objective` remains `unresolved`; sorting candidate plans is not proof that the underlying project will succeed. The engine does not establish source truth, independent semantic judgment, skill growth, mastery, a canonical story consequence, cross-domain qualification, or external action from this result.

Character and method renames leave the calculated artifact unchanged when the underlying operation and inputs are unchanged. Attribution bindings still change when relevant recorded identity or method revisions change. A changed operation must have a changed method revision and an explicit assignment to that revision before it changes behavior.

Focused tests cover rename and paraphrase controls, actual changed method outcomes, stale inputs, forged prepared packets, exact source-field support, hidden provenance, unsupported domains, pending judgment, reopening, and numeric/input boundaries. All fixtures are disposable and explicitly synthetic.
