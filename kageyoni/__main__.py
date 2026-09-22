import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .engine import Engine, Rejected
from .model import DOMAINS, REQUIRED, schema
from .seed import seed
from .workflows import Workflows


def _read_input(path):
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def main():
    parser = argparse.ArgumentParser(description="Local Kageyoni causal world-state engine; no network access")
    parser.add_argument("--db", default="build/kageyoni.sqlite")
    parser.add_argument(
        "operation",
        choices=[
            "engine-init", "operate",
            "learning-init", "outcome-record", "outcome-read", "outcome-list", "lesson-propose", "lesson-revise", "lesson-review", "lesson-read", "lesson-list", "methods-init", "method-create", "method-revise", "method-assign", "method-read", "method-list", "expression-prepare", "contribute", "contribution-read", "contribution-list", "node-init", "node-bind", "node-read", "node-list", "init", "schema", "seed", "context", "apply", "preview", "verify", "fork",
            "roll", "backup", "restore", "export", "history", "sources", "contract", "workflow",
            "session", "properties", "processes", "advance", "simulate", "consequences",
            "replay", "dependencies", "registry", "snapshot", "opportunities", "maintain",
            "will-prepare", "will-apply", "will-contract",
            "character-create", "character-read", "character-readiness",
            "decision-propose", "decision-commit", "decision-read",
            "decision-settle", "writing-brief", "writing-publish", "dialogue-receive",
            "personality-context", "personality-evaluate", "personality-record", "dialogue-propose",
        ],
    )
    parser.add_argument("--input", help="JSON file; - reads stdin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--domain")
    parser.add_argument("--viewer")
    parser.add_argument("--scene")
    parser.add_argument("--output")
    parser.add_argument("--source-dir", default="sources")
    parser.add_argument("--property-id")
    parser.add_argument("--kind")
    parser.add_argument("--stable-id")
    parser.add_argument("--version")
    args = parser.parse_args()

    if args.operation == "schema":
        print(schema())
        return
    if args.operation == "contract":
        print(json.dumps({
            "api_version": 3,
            "character_schema": "1",
            "personality_interface": "1",
            "domains": DOMAINS,
            "required": REQUIRED,
            "stages": ["permission", "probability", "magnitude", "cost", "timing", "consequences"],
            "will_contract_version": "will-contract/0.1",
            "entry_skills": ["Kageyoni Play", "Kageyoni Maintain"],
        }, ensure_ascii=False, indent=2))
        return

    if args.operation == "restore":
        data = _read_input(args.input)
        source = data.get("source") if data else args.output
        destination = data.get("destination") if data else None
        if not source or not destination:
            raise SystemExit("restore requires JSON source and destination")
        print(json.dumps(Engine.restore(source, destination), ensure_ascii=False, indent=2, default=str))
        return

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    engine = Engine(args.db)
    try:
        data = _read_input(args.input)
        if args.operation == "init":
            result = engine.verify()
        elif args.operation in ('engine-init','operate'):
            if args.viewer:
                raise Rejected('daily operation requires the trusted owner view')
            if args.operation=='engine-init':
                from .application import Application
                result=Application(engine,migrate_all=True).operations.status()
            else:
                from .console import dispatch
                result=dispatch(engine,data)
        elif args.operation in ('learning-init','outcome-record','outcome-read','outcome-list','lesson-propose','lesson-revise','lesson-review','lesson-read','lesson-list'):
            from .application import Application
            if args.operation in ('learning-init','outcome-record','lesson-propose','lesson-revise','lesson-review') and args.viewer:
                raise Rejected('learning authoring requires owner view')
            app=Application(engine,migrate_learning=args.operation=='learning-init')
            if args.operation=='learning-init':
                result={'learning_interface':'1','installed':True,'world_revision':engine.branch(args.branch)['revision']}
            else:
                data.setdefault('branch',args.branch)
                data['viewer']=args.viewer
                operation={'outcome-record':'record_outcome','outcome-read':'read_outcome','outcome-list':'list_outcomes',
                           'lesson-propose':'propose','lesson-revise':'revise','lesson-review':'review','lesson-read':'read','lesson-list':'list'}[args.operation]
                result=getattr(app.learning,operation)(**data)
        elif args.operation in ('methods-init','method-create','method-revise','method-assign','method-read','method-list','expression-prepare','contribute','contribution-read','contribution-list'):
            from .application import Application
            if args.operation in ('methods-init','method-create','method-revise','method-assign') and args.viewer:
                raise Rejected('method authoring requires owner view')
            app=Application(engine,migrate_methods=args.operation=='methods-init')
            if args.operation=='methods-init':
                result={'method_interface':'1','contribution_interface':'1','installed':True,'world_revision':engine.branch(args.branch)['revision']}
            else:
                data.setdefault('branch',args.branch)
                data['viewer']=args.viewer
                if args.operation.startswith('method-'):
                    result=getattr(app.methods,args.operation.removeprefix('method-'))(**data)
                elif args.operation=='expression-prepare':result=app.expression.prepare(**data)
                elif args.operation=='contribute':result=app.contributions.run(**data)
                elif args.operation=='contribution-read':result=app.contributions.read(**data)
                else:result=app.contributions.list(**data)
        elif args.operation.startswith('node-'):
            from .application import Application
            if args.operation in ('node-init','node-bind') and args.viewer:
                raise Rejected('node maintenance requires owner view')
            app=Application(engine,migrate=args.operation=='node-init')
            if args.operation=='node-init':result={'node_interface':'1','installed':True,'world_revision':engine.branch(args.branch)['revision']}
            elif args.operation=='node-list':result=app.nodes.list(args.branch,viewer=args.viewer)
            else:
                data.setdefault('branch',args.branch)
                data['viewer']=args.viewer
                result=getattr(app.nodes,'bind' if args.operation=='node-bind' else 'read')(**data)
        elif args.operation in ('writing-brief','writing-publish','dialogue-receive'):
            if args.viewer: raise Rejected('writing authoring requires trusted GM context; read delivered records through context')
            data.setdefault('branch',args.branch)
            result=getattr(Workflows(engine),args.operation.replace('-','_'))(**data)
        elif args.operation.startswith('personality-') or args.operation == 'dialogue-propose':
            data.setdefault('branch',args.branch)
            if args.viewer and args.operation != 'personality-context':
                raise Rejected('personality evaluation and authoring require trusted GM context')
            if args.viewer:
                data['viewer']=args.viewer
            result=getattr(Workflows(engine),args.operation.replace('-','_'))(**data)
        elif args.operation.startswith('decision-'):
            data.setdefault('branch',args.branch)
            if args.viewer and args.operation != 'decision-read':
                raise Rejected('decision authoring requires trusted GM context')
            if args.viewer:
                data['viewer']=args.viewer
            result=getattr(Workflows(engine),args.operation.replace('-','_'))(**data)
        elif args.operation.startswith("character-"):
            from . import characters
            data.setdefault('branch', args.branch)
            if args.operation == 'character-create':
                if args.viewer:
                    raise Rejected('character creation requires GM authority')
                result = characters.create(engine, **data)
            else:
                if args.viewer:
                    data['viewer'] = args.viewer
                fn = characters.read if args.operation == 'character-read' else characters.readiness
                result = fn(engine, **data)
        elif args.operation == "seed":
            result = seed(engine, args.source_dir)
        elif args.operation == "context":
            result = engine.context(args.branch, args.domain, viewer=args.viewer, scene=args.scene)
        elif args.operation in ("apply", "preview"):
            result = engine.apply(data, preview=args.operation == "preview")
        elif args.operation == "workflow":
            result = Workflows(engine).prepare(**data)
        elif args.operation == "will-prepare":
            attempt = data.get("attempt", data)
            result = engine.prepare_will_attempt(data.get("branch", args.branch), attempt)
        elif args.operation == "will-apply":
            result = engine.apply_will_attempt(
                data.get("branch", args.branch), data["attempt_id"], data["request_id"],
                data["actor"], data["narrative"], data.get("expected_revision"),
            )
        elif args.operation == "will-contract":
            result = engine.get_will_contract(
                data.get("branch", args.branch), data["domain"], data["record_id"], data.get("version"),
            )
        elif args.operation == "session":
            result = Workflows(engine).open_session(
                data.get("branch", args.branch), data.get("viewer", args.viewer),
                data.get("scene", args.scene), data.get("attention_for"),
            )
        elif args.operation == "verify":
            result = engine.verify()
        elif args.operation == "fork":
            result = engine.fork(**data)
        elif args.operation == "roll":
            result = engine.roll(**data)
        elif args.operation == "backup":
            destination = args.output or data.get("destination")
            if not destination:
                raise Rejected("--output or destination required")
            result = {"backup": engine.backup(destination)}
        elif args.operation == "export":
            result = engine.context(args.branch)
        elif args.operation == "history":
            if args.viewer:
                raise Rejected("history is GM-only; use filtered context")
            result = [dict(r) for r in engine.causal_history(args.branch, data.get("event_id"))]
        elif args.operation == "sources":
            if args.viewer:
                raise Rejected("source archive is GM-only")
            result = [dict(r) for r in engine.db.execute("SELECT id,path,sha256 FROM sources")]
        elif args.operation == "properties":
            result = engine.properties(args.branch, data.get("entity_id"), args.viewer or data.get("viewer"), args.property_id or data.get("property_id"))
        elif args.operation == "processes":
            result = engine.list_processes(args.branch, args.viewer or data.get("viewer"))
        elif args.operation == "advance":
            result = Workflows(engine).prepare("advance_time", args.branch, data["request_id"], data["actor"], data["narrative"], clock=data["clock"], tick=data["tick"])
        elif args.operation == "simulate":
            result = engine.advance_simulation(**data)
        elif args.operation == "consequences":
            result = engine.apply_consequences(**data)
        elif args.operation == "replay":
            result = engine.replay(data.get("branch", args.branch))
        elif args.operation == "dependencies":
            result = Workflows(engine).inspect_dependencies(
                property_id=args.property_id or data.get("property_id"),
                kind=args.kind or data.get("kind"),
                stable_id=args.stable_id or data.get("stable_id"),
                version=args.version or data.get("version"),
            )
        elif args.operation == "registry":
            result = engine.validate_registry()
        elif args.operation == "snapshot":
            result = engine.register_snapshot(data.get("branch", args.branch), data.get("snapshot_id"))
        elif args.operation == "opportunities":
            result = engine.opportunities(data.get("branch", args.branch), data.get("actor"), viewer=args.viewer or data.get("viewer"), scene=args.scene or data.get("scene"))
        elif args.operation == "maintain":
            operation = data.pop("operation", None)
            if not operation:
                raise Rejected("maintain requires operation")
            result = Workflows(engine).maintain(operation, **data)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False, default=str))
    except (Rejected, sqlite3.Error, ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        sys.exit(2)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
