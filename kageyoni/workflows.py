"""Structured host workflows for the Kageyoni engine.

These helpers route play intent to one engine command. They never invent
unsupported mechanics; unresolved semantics remain recorded GM judgments.
"""
from __future__ import annotations

from .engine import Rejected, require


class Workflows:
    def __init__(self, engine):
        self.engine = engine
        from .agency_workflows import AgencyWorkflows
        self.agency = AgencyWorkflows(engine)

    def coliseum_open(self, **params):
        from .coliseum import open_match
        return open_match(self.engine, **params)

    def coliseum_exchange(self, **params):
        from .coliseum import exchange
        return exchange(self.engine, **params)

    def writing_brief(self, interface_version='1', **params):
        from .writing import brief
        require(str(interface_version)=='1','unsupported writing interface')
        return brief(self.engine, **params)

    def writing_publish(self, **params):
        from .writing import publish
        return publish(self.engine, **params)

    def dialogue_receive(self, **params):
        from .writing import receive
        return receive(self.engine, **params)

    def _personality_version(self, interface_version):
        require(str(interface_version)=='1', 'unsupported personality interface')

    def personality_context(self, interface_version='1', **params):
        from .personality import brief
        self._personality_version(interface_version)
        return brief(self.engine, **params)

    def personality_evaluate(self, interface_version='1', **params):
        from .personality import evaluate
        self._personality_version(interface_version)
        return evaluate(self.engine, **params)

    def personality_record(self, interface_version='1', **params):
        from .personality import record
        self._personality_version(interface_version)
        return record(self.engine, **params)

    def dialogue_propose(self, interface_version='1', **params):
        from .personality import dialogue_propose
        self._personality_version(interface_version)
        return dialogue_propose(self.engine, **params)

    def character_create(self, **params):
        from .characters import create
        return create(self.engine, **params)

    def decision_propose(self, branch, spec):
        from .decisions import propose
        return propose(self.engine, branch, spec)

    def decision_commit(self, **params):
        from .decisions import commit
        return commit(self.engine, **params)

    def decision_read(self, **params):
        from .decisions import inspect
        return inspect(self.engine, **params)

    def decision_settle(self, **params):
        from .decisions import settle
        return settle(self.engine, **params)

    def character_read(self, **params):
        from .characters import read
        return read(self.engine, **params)

    def character_readiness(self, **params):
        from .characters import readiness
        return readiness(self.engine, **params)

    def open_session(self, branch="main", viewer=None, scene=None, attention_for=None):
        from .writing import CONTRACT
        meta = self.engine.branch(branch)
        runtime = {
            r["component"]: r["version"]
            for r in self.engine.db.execute("SELECT component,version FROM engine_versions")
        }
        required = {"runtime_schema": "4", "workflow_api": "3", "property_registry": "1", "resolution_rules": "1", "story_state": "1"}
        compatibility = {
            "ok": all(str(runtime.get(k)) == str(v) for k, v in required.items()),
            "required": required,
            "runtime": runtime,
        }
        return {
            "branch": branch,
            "revision": meta["revision"],
            "runtime": runtime,
            "writing_contract": CONTRACT,
            "compatibility": compatibility,
            "context": self.engine.context(branch, viewer=viewer, scene=scene, attention_for=attention_for),
            "decision_interface": runtime.get('decision_interface'),
            "personality_interface": runtime.get('personality_interface'),
            "pending_decisions": [
                {"id":r['id'],"instruction":"Use decision-read; reassess if state changed."}
                for r in self.engine.db.execute('SELECT id,spec_json FROM decision_proposals WHERE branch=?',(branch,))
                if viewer is None
            ],
            "pending_consequences": [
                dict(r) for r in self.engine.db.execute(
                    "SELECT id,subject_id,status,trigger_json FROM consequences WHERE branch=? AND status='pending' ORDER BY id",
                    (branch,),
                )
            ] if viewer is None else [],
            "pending_processes": [
                p for p in self.engine.list_processes(branch, viewer=viewer)
                if p["state"] in ("due", "blocked")
            ],
        }

    def prepare(self, name, branch, request_id, actor, narrative, **params):
        e = self.engine
        meta = e.branch(branch)
        if name in ("will", "will_attempt", "resolve_will"):
            attempt = dict(params)
            attempt.update(request_id=request_id, actor=actor)
            if "expected_revision" not in attempt:
                attempt["expected_revision"] = meta["revision"]
            result = e.prepare_will_attempt(branch, attempt)
            result["workflow"] = "will_prepare"
            result["narrative"] = narrative
            return result
        evidence = [{"note": params.pop("evidence_note", "GM-proposed outcome; review interpretation against scene and canon.")}]
        changes = []
        kind = "action"
        extras = {}
        properties = params.pop("properties", [])
        consequences = params.pop("consequences", [])
        dependencies = params.pop("dependencies", [])
        choice = params.pop("choice", None)
        resolution = params.pop("resolution", None)
        processes = params.pop("processes", [])
        observations = params.pop("observations", [])
        def patch(record_id, data):
            row = e.get(branch, record_id)
            require(row is not None, "record not found")
            return {"op": "patch", "id": record_id, "expected_version": row["version"], "data": data, "evidence": evidence}
        if name == "transfer_item":
            item = params.pop("item"); recipient = params.pop("recipient")
            slot = params.pop("slot", "carried"); equipped = params.pop("equipped", 0)
            rows = [r for r in e.state(branch) if r["domain"] == "loadout" and r["data"]["item"] == item]
            require(len(rows) == 1, "item must have exactly one custody record")
            changes.append(patch(rows[0]["id"], {"holder": recipient, "slot": slot, "equipped": equipped}))
            for r in e.state(branch):
                if r["domain"] == "loot" and r["data"]["item"] == item and r["data"]["discovery"] == "claimed":
                    changes.append(patch(r["id"], {"claimant": recipient}))
        elif name in ("advance_time", "advance_simulation"):
            clock_id = params.pop("clock"); tick = params.pop("tick")
            c = e.get(branch, clock_id)
            require(c is not None and c["domain"] == "clock", "clock required")
            require(tick >= c["data"]["tick"], "advance cannot rewind")
            if name == "advance_time":
                changes.append(patch(clock_id, {"tick": tick}))
                kind = "advance_time"; extras.update(clock_id=clock_id, tick=tick)
                for r in e.state(branch):
                    if r["domain"] == "schedule" and r["data"]["clock"] == clock_id and r["data"]["phase"] == "pending" and r["data"]["due"] <= tick:
                        changes.append(patch(r["id"], {"phase": "due"}))
            else:
                return e.advance_simulation(
                    branch, clock_id, tick, request_id, actor, narrative,
                    expected_revision=meta["revision"], limit=params.pop("limit", 100),
                )
        elif name in ("resolve_turn", "record_decision", "develop_character", "political_change", "record_history", "correct_continuity", "rewind", "resolve_world_event", "record_discovery"):
            changes = params.pop("changes", [])
            kind = {"record_decision": "decision", "correct_continuity": "correction", "rewind": "rewind", "resolve_world_event": "world_event", "record_discovery": "observation"}.get(name, "action")
            for key in ("causes", "clock_id", "tick", "roll_ids", "judgment", "assumptions"):
                if key in params:
                    extras[key] = params.pop(key)
        elif name in ("combat", "travel", "discovery", "training", "social", "downtime"):
            # Activity names are routing metadata; the actual mechanic is a
            # versioned resolution supplied by the engine/GM.
            action_spec = params.pop("action_spec", params.pop("resolution", None))
            require(action_spec is not None, "activity requires action_spec")
            resolution = e.resolve_action(branch, action_spec) if "feasible" not in action_spec else action_spec
            require(resolution.get("feasible") is not False, "action is not permitted")
            changes = params.pop("changes", [])
            kind = "action"
            module_id = f"kageyoni.{name}"
            dependencies.append({"kind": "module", "ref_id": module_id, "version": "1", "usage": "reads"})
            for rule in action_spec.get("rules", []):
                if isinstance(rule, dict) and {"id", "version"} <= set(rule):
                    dependencies.append({"kind": "rule", "ref_id": rule["id"], "version": str(rule["version"]), "usage": "reads"})
            extras["roll_ids"] = [resolution["roll"]["id"]] if resolution.get("roll") else []
        else:
            raise Rejected("unknown workflow")
        require(not params, "unknown workflow parameters")
        command = dict(
            api_version=2, branch=branch, expected_revision=meta["revision"],
            request_id=request_id, actor=actor, narrative=narrative, kind=kind,
            changes=changes, properties=properties, processes=processes,
            observations=observations, dependencies=dependencies,
            consequences=consequences, choice=choice, resolution=resolution,
            **extras,
        )
        preview = e.apply(command, preview=True)
        return {
            "workflow": name, "command": command, "preview": preview,
            "next": "Review semantic consequences, then apply the unchanged command.",
        }

    def propose_action(self, branch, request_id, actor, narrative, action_spec, changes=None, **extra):
        meta = self.engine.branch(branch)
        resolution = self.engine.resolve_action(branch, action_spec)
        if not resolution.get("feasible"):
            return {"workflow": "propose_action", "resolution": resolution, "command": None}
        command = {
            "api_version": 2, "branch": branch, "expected_revision": meta["revision"],
            "request_id": request_id, "kind": extra.pop("kind", "action"),
            "actor": actor, "narrative": narrative, "changes": changes or [],
            "resolution": resolution, "roll_ids": [resolution["roll"]["id"]] if resolution.get("roll") else [],
            **extra,
        }
        for rule in action_spec.get("rules", []):
            if isinstance(rule, dict) and {"id", "version"} <= set(rule):
                command.setdefault("dependencies", []).append({"kind": "rule", "ref_id": rule["id"], "version": str(rule["version"]), "usage": "reads"})
        preview = self.engine.apply(command, preview=True)
        return {"workflow": "propose_action", "resolution": resolution, "command": command, "preview": preview}

    def will_prepare(self, branch, attempt):
        return self.engine.prepare_will_attempt(branch, attempt)

    def will_apply(self, branch, attempt_id, request_id, actor, narrative, expected_revision=None):
        return self.engine.apply_will_attempt(branch, attempt_id, request_id, actor, narrative, expected_revision)

    def inspect_opportunities(self, branch="main", actor=None, viewer=None, scene=None):
        return self.engine.opportunities(branch, actor, viewer=viewer, scene=scene)

    def record_discovery(self, branch, request_id, actor, observer_id, subject_id, assertion, certainty="observed", visibility="restricted", audience=None, narrative="Discovery recorded", expected_revision=None):
        meta = self.engine.branch(branch)
        command = {
            "api_version": 2, "branch": branch, "expected_revision": meta["revision"] if expected_revision is None else expected_revision,
            "request_id": request_id, "kind": "observation", "actor": actor, "narrative": narrative,
            "changes": [], "observations": [{
                "id": f"observation:{request_id}", "observer_id": observer_id,
                "subject_id": subject_id, "assertion": assertion, "certainty": certainty,
                "visibility": visibility, "audience": audience or [observer_id],
            }],
        }
        return {"command": command, "preview": self.engine.apply(command, preview=True)}

    def apply_consequences(self, branch, request_id, actor, narrative, expected_revision=None, limit=50):
        return self.engine.apply_consequences(branch, request_id, actor, narrative, expected_revision, limit)

    def inspect_dependencies(self, property_id=None, kind=None, stable_id=None, version=None):
        if property_id is not None:
            return self.engine.impact("property", property_id, str(version) if version is not None else None)
        require(kind is not None and stable_id is not None, "dependency target required")
        return self.engine.impact(kind, stable_id, str(version) if version is not None else None)

    def advance_time(self, branch, request_id, actor, narrative, clock, tick, expected_revision=None):
        return self.prepare("advance_time", branch, request_id, actor, narrative, clock=clock, tick=tick)["command"]

    def maintain(self, operation, **params):
        if operation == "validate_registry":
            return self.engine.validate_registry()
        if operation == "dependencies":
            return self.inspect_dependencies(**params)
        if operation == "backup":
            return {"backup": self.engine.backup(params["destination"])}
        if operation == "snapshot":
            return self.engine.register_snapshot(params.get("branch", "main"), params.get("snapshot_id"))
        if operation == "replay":
            return self.engine.replay(params.get("branch", "main"))
        if operation == "verify":
            return self.engine.verify()
        if operation == "will_contract":
            return self.engine.get_will_contract(params["branch"], params["domain"], params["record_id"], params.get("version"))
        if operation == "will_prepare":
            return self.engine.prepare_will_attempt(params.get("branch", "main"), params["attempt"])
        if operation == "will_apply":
            return self.engine.apply_will_attempt(params.get("branch", "main"), params["attempt_id"], params["request_id"], params["actor"], params["narrative"], params.get("expected_revision"))
        if operation == "define_property":
            return self.engine.define_property(**params)
        if operation == "revise_property":
            return self.engine.revise_property(**params)
        if operation == "retire_property":
            return self.engine.retire_property(**params)
        if operation == "add_rule":
            return self.engine.add_rule(**params)
        if operation == "register_module":
            return self.engine.register_module(**params)
        if operation == "registry_dependency":
            return self.engine.add_registry_dependency(**params)
        raise Rejected("unknown maintenance operation")
