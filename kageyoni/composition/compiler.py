from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

RUNNABLE_STATUSES = {"FILLED", "DERIVED", "INFERRED", "NOT_APPLICABLE"}
BLOCKING_STATUSES = {"UNKNOWN", "STALE", "UNPLACED", "INVALID"}


class Compiler:
    """Fail-closed Frame/Slot/Aspect composition compiler.

    This prototype intentionally owns only admission and dependency closure. It does
    not perform semantic world resolution and it never mutates campaign state.
    """

    def __init__(self, frame: dict[str, Any], aspects: Iterable[dict[str, Any]]):
        self.frame = frame
        self.init_issues=[]
        if not isinstance(aspects,(list,tuple)):
            raw=[];self.init_issues.append({"slot_id":"input","status":"INVALID","reason":"aspects must be a list"})
        else:
            raw=[]
            for i,a in enumerate(aspects):
                if not isinstance(a,dict) or not isinstance(a.get("aspect_id"),str) or not a.get("aspect_id"):
                    self.init_issues.append({"slot_id":"input","status":"INVALID","reason":f"invalid aspect at index {i}"});continue
                raw.append(dict(a))
        ids=[a["aspect_id"] for a in raw]
        if len(ids)!=len(set(ids)): self.init_issues.append({"slot_id":"input","status":"INVALID","reason":"duplicate aspect_id"})
        self.aspects = {a["aspect_id"]: a for a in raw}
        self.slot_defs = {s["slot_id"]: s for s in frame["slots"]}
        if len(self.slot_defs) != len(frame["slots"]):
            raise ValueError("duplicate slot_id in frame")

    def _participant_count(self, bindings: dict[str, list[str]]) -> int:
        if not isinstance(bindings,dict): return 0
        value=bindings.get("scene.participants", [])
        return len(value) if isinstance(value,list) else 0

    def _condition_active(self, slot: dict[str, Any], bindings: dict[str, list[str]]) -> bool:
        if slot["requirement"] != "conditional":
            return True
        condition = slot.get("condition") or {}
        if condition.get("kind") == "slot_count_gt":
            source = condition.get("slot_id")
            threshold = condition.get("value")
            if source not in self.slot_defs or type(threshold) is not int:
                raise ValueError(f"invalid slot_count_gt condition: {condition!r}")
            return len(bindings.get(source, [])) > threshold
        if condition.get("kind") == "aspect_flag_any":
            source = condition.get("slot_id")
            flag = condition.get("flag")
            if source not in self.slot_defs or not isinstance(flag, str) or not flag:
                raise ValueError(f"invalid aspect_flag_any condition: {condition!r}")
            return any(bool(self.aspects.get(aid, {}).get("properties", {}).get(flag)) for aid in bindings.get(source, []))
        # Legacy prototype condition is accepted for migration compatibility only.
        expr = condition.get("when")
        if isinstance(expr, str) and expr.startswith("participant_count > "):
            try: threshold = int(expr.rsplit(" ", 1)[1])
            except ValueError as exc: raise ValueError(f"unsupported frame condition: {expr!r}") from exc
            return self._participant_count(bindings) > threshold
        raise ValueError(f"unsupported frame condition: {condition!r}")

    @staticmethod
    def _provenance_present(aspect: dict[str, Any]) -> bool:
        prov=aspect.get("provenance")
        return isinstance(prov,list) and bool(prov) and all(isinstance(x,dict) and any(isinstance(v,str) and v.strip() for v in x.values()) for x in prov)

    @staticmethod
    def _finite(value: Any) -> bool:
        if isinstance(value,float): return math.isfinite(value)
        if isinstance(value,dict): return all(isinstance(k,str) and Compiler._finite(v) for k,v in value.items())
        if isinstance(value,list): return all(Compiler._finite(v) for v in value)
        return value is None or isinstance(value,(str,int,bool))

    def _validate_aspect_for_slot(self, slot: dict[str, Any], aspect: dict[str, Any]) -> str | None:
        if not self._finite(aspect): return "aspect contains non-finite or unsupported interchange values"
        if not isinstance(aspect.get("effects",[]),list): return "effects must be a list"
        if aspect.get("family") is not None and not isinstance(aspect.get("family"),str): return "family must be a string"
        if aspect.get("family") is not None and aspect.get("family") != slot.get("family"): return f"aspect family {aspect.get('family')!r} does not match slot family {slot.get('family')!r}"
        if aspect.get("type") not in slot.get("accepts", []):
            return f"incompatible type {aspect.get('type')!r}; accepts {slot.get('accepts', [])!r}"
        compatible = aspect.get("compatible_slots")
        if compatible is not None and slot["slot_id"] not in compatible:
            return "aspect does not declare compatibility with this slot"
        if slot.get("semantic_identity_required") and not aspect.get("semantic_key"):
            return "slot requires explicit semantic_key for duplicate-influence protection"
        if slot.get("lineage_required") and not (aspect.get("lineage") or {}).get("entity_id"):
            return "slot requires explicit entity lineage"
        policy=slot.get("effect_policy") or {}
        allowed_ops=set(policy.get("allowed_operations") or [])
        if allowed_ops:
            bad=[e.get("operation") for e in aspect.get("effects",[]) or [] if e.get("operation") not in allowed_ops]
            if bad:
                return f"effect policy forbids operations {bad!r}; allowed={sorted(allowed_ops)!r}"
        authority = aspect.get("authority", "unknown")
        allowed = set(slot.get("authority_policy") or [])
        if authority not in allowed:
            return f"authority {authority!r} is not permitted; allowed={sorted(allowed)!r}"
        if authority == "host_judgment" and not slot.get("host_inference", False):
            return "host judgment is disabled for this slot"
        if authority in {"owner", "evidence", "derived", "host_judgment"} and not self._provenance_present(aspect):
            return f"authority {authority!r} requires provenance"
        return None

    def compile(self, bindings: dict[str, list[str]], participant_count: int | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = dict(context or {})
        # participant_count is accepted only for compatibility with the earlier
        # prototype. Bound participants are authoritative; a mismatching caller
        # hint is reported rather than trusted.
        bound_participants = self._participant_count(bindings)
        input_issues: list[dict[str, Any]] = list(self.init_issues)
        if not isinstance(bindings,dict):
            bindings={}
            input_issues.append({"slot_id":"input","status":"INVALID","reason":"bindings must be an object"})
        # Frame-level resolution budget prevents unbounded direct-entity expansion.
        budget = self.frame.get("resolution_budget") or {}
        max_direct = budget.get("max_direct_entities")
        if isinstance(max_direct, int) and bound_participants > max_direct:
            input_issues.append({"slot_id":"scene.participants","status":"INVALID","reason":f"resolution budget exceeded: {bound_participants} direct entities > {max_direct}; aggregate or promote by relevance"})
        if participant_count is not None and participant_count != bound_participants:
            input_issues.append({
                "slot_id": "scene.participants",
                "status": "INVALID",
                "reason": f"participant_count hint {participant_count} disagrees with {bound_participants} bound participant(s)",
            })

        slots: list[dict[str, Any]] = []
        unplaced: list[dict[str, Any]] = []
        declared = set(self.slot_defs)

        for sid,value in list(bindings.items()):
            if not isinstance(value,list):
                input_issues.append({"slot_id":sid,"status":"INVALID","reason":"binding value must be a list"});bindings[sid]=[];continue
            if len(value)!=len(set(x for x in value if isinstance(x,str))):
                input_issues.append({"slot_id":sid,"status":"INVALID","reason":"duplicate aspect binding"})
            if sid not in declared:
                unplaced.append({"slot_id": sid, "status": "UNPLACED", "reason": "slot not declared by frame"})

        # Cross-cutting context integrity: branch/time scope and semantic duplicate protection.
        expected_branch = context.get("branch")
        revision = context.get("revision")
        global_semantic = {}
        for sid, ids in bindings.items():
            seen_semantic = {}
            for aid in ids:
                a = self.aspects.get(aid)
                if not a: continue
                key = a.get("semantic_key")
                if key:
                    if key in seen_semantic and seen_semantic[key] != aid:
                        input_issues.append({"slot_id":sid,"status":"INVALID","reason":f"duplicate semantic influence {key!r}: {seen_semantic[key]!r}, {aid!r}"})
                    seen_semantic[key]=aid
                    if key in global_semantic and global_semantic[key] != aid:
                        input_issues.append({"slot_id":sid,"status":"INVALID","reason":f"duplicate semantic influence across slots {key!r}: {global_semantic[key]!r}, {aid!r}"})
                    global_semantic[key]=aid
                scope = a.get("scope") or {}
                abranch = scope.get("branch")
                if expected_branch is not None and abranch is not None and abranch != expected_branch:
                    input_issues.append({"slot_id":sid,"status":"INVALID","reason":f"semantic counterfeit: aspect {aid!r} belongs to branch {abranch!r}, expected {expected_branch!r}"})
                expected_world=context.get("world_id")
                aworld=scope.get("world_id")
                if expected_world is not None and aworld is not None and aworld != expected_world:
                    input_issues.append({"slot_id":sid,"status":"INVALID","reason":f"semantic counterfeit: aspect {aid!r} belongs to world {aworld!r}, expected {expected_world!r}"})
                if (a.get("effects") or []) and not a.get("semantic_key"):
                    input_issues.append({"slot_id":sid,"status":"INVALID","reason":f"effect-bearing aspect {aid!r} requires semantic_key"})
                temporal = a.get("temporal") or {}
                if revision is not None:
                    lo, hi = temporal.get("effective_from_revision"), temporal.get("effective_to_revision")
                    if lo is not None and revision < lo:
                        input_issues.append({"slot_id":sid,"status":"STALE","reason":f"aspect {aid!r} is not effective until revision {lo}"})
                    if hi is not None and revision > hi:
                        input_issues.append({"slot_id":sid,"status":"STALE","reason":f"aspect {aid!r} expired at revision {hi}"})

        # Identity-bound slots must refer to an active participant when they declare a subject.
        participant_refs=set()
        for aid in bindings.get("scene.participants", []):
            a=self.aspects.get(aid,{})
            participant_refs.add(a.get("properties",{}).get("record_id") or a.get("lineage",{}).get("entity_id") or aid)
        for slot in self.frame["slots"]:
            source = slot.get("identity_bound_to")
            if not source: continue
            allowed = participant_refs if source == "scene.participants" else set(bindings.get(source, []))
            for aid in bindings.get(slot["slot_id"], []):
                a=self.aspects.get(aid,{})
                subject=(a.get("lineage") or {}).get("entity_id")
                if subject is not None and subject not in allowed:
                    input_issues.append({"slot_id":slot["slot_id"],"status":"INVALID","reason":f"semantic counterfeit: aspect {aid!r} is bound to entity {subject!r}, not an active participant"})
            if source == "scene.participants" and slot.get("requirement") == "required" and participant_refs:
                covered={(self.aspects.get(aid,{ }).get("lineage") or {}).get("entity_id") for aid in bindings.get(slot["slot_id"],[])}
                missing_subjects=sorted(str(x) for x in participant_refs if x not in covered)
                if missing_subjects:
                    input_issues.append({"slot_id":slot["slot_id"],"status":"INVALID","reason":f"actor-specific coverage missing for {missing_subjects}"})

        for slot in self.frame["slots"]:
            sid = slot["slot_id"]
            active = self._condition_active(slot, bindings)
            if not active:
                supplied=list(bindings.get(sid,[]) or [])
                if supplied:
                    input_issues.append({"slot_id":sid,"status":"INVALID","reason":"input supplied to inactive conditional slot","aspect_ids":supplied})
                slots.append({"slot_id": sid, "status": "NOT_APPLICABLE", "aspect_ids": []})
                continue

            ids = list(bindings.get(sid, []))
            lo = slot["cardinality"]["min"]
            hi = slot["cardinality"].get("max")

            if hi is not None and len(ids) > hi:
                slots.append({
                    "slot_id": sid,
                    "status": "INVALID",
                    "aspect_ids": ids,
                    "reason": f"cardinality violation: maximum {hi}, received {len(ids)}",
                })
                continue

            missing = [x for x in ids if x not in self.aspects]
            if missing:
                slots.append({
                    "slot_id": sid,
                    "status": "UNPLACED",
                    "aspect_ids": ids,
                    "reason": f"unknown aspects: {missing}",
                })
                continue

            violations = []
            for aid in ids:
                reason = self._validate_aspect_for_slot(slot, self.aspects[aid])
                if reason:
                    violations.append({"aspect_id": aid, "reason": reason})
            if violations:
                slots.append({
                    "slot_id": sid,
                    "status": "INVALID",
                    "aspect_ids": ids,
                    "reason": "aspect admission failed",
                    "violations": violations,
                })
                continue

            if len(ids) < lo and slot["requirement"] in ("required", "conditional"):
                slots.append({"slot_id": sid, "status": "UNKNOWN", "aspect_ids": ids, "reason": f"requires >= {lo}"})
                continue

            slots.append({"slot_id": sid, "status": "FILLED" if ids else "NOT_APPLICABLE", "aspect_ids": ids})

        by_id = {s["slot_id"]: s for s in slots}
        # Dependencies are checked after primary admission so the reason can point
        # to the exact upstream slot instead of becoming another generic missing value.
        for slot in self.frame["slots"]:
            current = by_id[slot["slot_id"]]
            if current["status"] == "NOT_APPLICABLE":
                continue
            failed = []
            for dep in slot.get("dependencies", []):
                dep_state = by_id.get(dep)
                if dep_state is None or dep_state["status"] not in RUNNABLE_STATUSES - {"NOT_APPLICABLE"}:
                    failed.append(dep)
            if failed and current["status"] not in BLOCKING_STATUSES:
                current.update(status="INVALID", reason=f"dependency closure failed: {failed}")

        # Dependency definitions themselves must be acyclic.
        dep_graph={x["slot_id"]:list(x.get("dependencies",[])) for x in self.frame["slots"]}
        indeg={k:0 for k in dep_graph}; rev={k:[] for k in dep_graph}
        for k,deps in dep_graph.items():
            for d in deps:
                if d in indeg: indeg[k]+=1;rev[d].append(k)
        queue=[k for k,v in indeg.items() if v==0];seen=0
        while queue:
            n=queue.pop();seen+=1
            for m in rev[n]:
                indeg[m]-=1
                if indeg[m]==0:queue.append(m)
        if seen!=len(indeg): input_issues.append({"slot_id":"dependencies","status":"INVALID","reason":"cyclic slot dependencies"})
        blockers = [x for x in slots if x["status"] in BLOCKING_STATUSES]
        blockers.extend(unplaced)
        blockers.extend(input_issues)
        preserved = [x for x in slots if x["status"] == "CONFLICTED"]

        from .gates import run_gate
        candidate = {
            "frame_id": self.frame["frame_id"],
            "participant_count": bound_participants,
            "slots": slots,
            "unplaced": unplaced,
            "input_issues": input_issues,
            "preserved_conflicts": preserved,
            "blockers": blockers,
        }
        gate_results = [run_gate(name, candidate) for name in self.frame.get("verification", [])]
        gate_blockers = [g for g in gate_results if g["status"] != "pass"]
        candidate["verification"] = {"gates": gate_results, "passed": not gate_blockers}
        candidate["runnable"] = not blockers and not gate_blockers
        if gate_blockers:
            candidate["blockers"] = blockers + [
                {"slot_id": "verification:"+g["gate"], "status": "INVALID", "reason": g.get("reason") or g.get("code")}
                for g in gate_blockers
            ]
        admitted=[]
        for slot in slots:
            if slot.get("status") in {"FILLED","DERIVED","INFERRED"}: admitted.extend(slot.get("aspect_ids",[]) or [])
        candidate["admitted_aspect_ids"] = sorted(set(admitted))
        candidate["input_dispositions"] = {aid:("ADMITTED" if aid in candidate["admitted_aspect_ids"] else "REJECTED_OR_INACTIVE") for aid in self.aspects}
        from .deficits import DeficitPlanner
        candidate["deficits"] = DeficitPlanner(self.frame).plan(candidate)
        return candidate


def load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


if __name__ == "__main__":
    root = Path(__file__).parent
    c = Compiler(load(root / "frames/narrative_scene.json"), load(root / "registry/example_aspects.json"))
    print(json.dumps(c.compile({
        "governing.context": ["will.primordial.twilight"],
        "scene.participants": ["actor.sciel"],
        "actor.configuration": ["actor.sciel.orientation"],
        "actor.epistemic": ["actor.sciel.knowledge"],
    }), indent=2))
