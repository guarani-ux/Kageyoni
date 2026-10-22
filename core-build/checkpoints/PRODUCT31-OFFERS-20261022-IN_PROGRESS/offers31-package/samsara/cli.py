"""Explicit startup, trusted supervision and ordinary user commands."""
import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
from .client import Client, exchange
from .console import execute
from .protocol import Fault, decode, encoded


def main():
    parser = argparse.ArgumentParser(prog='samsara')
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve'); serve.add_argument('--workspace', required=True); serve.add_argument('--new-synthetic', action='store_true')
    stdio = sub.add_parser('stdio'); stdio.add_argument('--workspace', required=True); stdio.add_argument('--new-synthetic', action='store_true'); stdio.add_argument('--actor', default='visitor'); stdio.add_argument('--role', choices=['operator','player','worker'], default='player'); stdio.add_argument('--activity')
    init = sub.add_parser('init'); init.add_argument('--workspace', required=True)
    open_ = sub.add_parser('open'); open_.add_argument('--workspace', required=True); open_.add_argument('--actor', default='visitor'); open_.add_argument('--plain', action='store_true'); open_.add_argument('--do')
    open_.add_argument('--operator', action='store_true')
    call = sub.add_parser('call'); call.add_argument('--workspace', required=True); call.add_argument('--input', required=True)
    call.add_argument('--actor', default='visitor'); call.add_argument('--activity'); call.add_argument('--operator', action='store_true')
    host = sub.add_parser('host'); host.add_argument('--workspace', required=True); host.add_argument('--actor', required=True); host.add_argument('--activity', required=True); host.add_argument('action', choices=['packet', 'act', 'return', 'call']); host.add_argument('--choice'); host.add_argument('--file'); host.add_argument('--checks')
    inspect = sub.add_parser('inspect'); inspect.add_argument('--workspace', required=True); inspect.add_argument('--offline', action='store_true', required=True)
    intake = sub.add_parser('intake'); intake.add_argument('--workspace', required=True); intake.add_argument('--manifest', required=True); intake.add_argument('--source-directory')
    continuation = sub.add_parser('continue-copy', help='Explicit local operator continuation to a NEW disposable directory')
    continuation.add_argument('--source', required=True)
    continuation.add_argument('--destination')
    continuation.add_argument('--expected-preview')
    admission = sub.add_parser('continuation-admission', help='Local operator control of NEW activity admission in a continued workspace')
    admission.add_argument('--workspace', required=True)
    admission.add_argument('--state', choices=['enabled', 'disabled'], required=True)
    for client_parser in (open_, call, host):
        client_parser.add_argument('--transport', choices=['unix','stdio'], default='stdio')
    args = parser.parse_args()
    try:
        if args.command == 'continuation-admission':
            from .compatibility import set_admission
            print(encoded(set_admission(args.workspace, args.state == 'enabled')))
            return
        if args.command == 'continue-copy':
            from .compatibility import preview, continue_copy
            if args.destination is None:
                if args.expected_preview is not None:
                    raise Fault('INVALID')
                result = preview(args.source)
            else:
                if args.expected_preview is None:
                    raise Fault('INVALID')
                result = continue_copy(args.source, args.destination, args.expected_preview)
            print(encoded(result))
            return
        if args.command in ('serve', 'stdio'):
            from .owner import Owner
            owner = Owner(args.workspace, args.new_synthetic, listen=args.command == 'serve')
            def stop(*_):
                owner.running = False
            signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
            try:
                if args.command == 'stdio':
                    context, output_root = owner.app.bind(args.role, None if args.role == 'operator' else args.actor, args.activity)
                    owner.run_stdio(context, output_root)
                else:
                    print(encoded({'owner': 'ready', 'workspace_id': owner.app.workspace_id, 'synthetic': True}), flush=True)
                    owner.run()
            finally:
                owner.close()
            return
        if args.command == 'init':
            client = Client.session(args.workspace, role='operator', new=True)
            try:
                print(encoded(client.view()))
            finally:
                client.close()
            return
        if args.command == 'inspect':
            from .owner import private_root
            root = private_root(args.workspace)
            path = root / 'world.sqlite'
            if path.is_symlink():
                raise Fault('UNAVAILABLE')
            db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
            try:
                db.execute('PRAGMA query_only=ON')
                print(encoded({'branches': db.execute('SELECT id,revision FROM branches').fetchall(),
                    'activities': db.execute('SELECT activity_id,state,outcome,version FROM activity_runs ORDER BY activity_id').fetchall(),
                    'scope': 'trusted local operator offline inspection; no Application construction or migration'}))
            finally:
                db.close()
            return
        if args.command == 'intake':
            # An explicit trusted launcher action, never a worker-stream flag.
            manifest_path = Path(args.manifest).absolute()
            operation = decode(manifest_path.read_bytes())
            client = Client.session(args.workspace, role='operator')
            try:
                client.view()
                print(encoded(client.admit(operation, args.source_directory or manifest_path.parent)))
            finally:
                client.close()
            return
        if args.command == 'call':
            if args.operator:
                client = Client.session(args.workspace, role='operator') if args.transport == 'stdio' else Client.operator(args.workspace)
            else:
                role = 'worker' if args.activity else 'player'
                client = Client.session(args.workspace, args.actor, role, args.activity) if args.transport == 'stdio' else Client.participant(args.workspace, args.actor, role, args.activity)
            try:
                request = decode(Path(args.input).read_bytes())
                print(encoded(client.call(request)))
            finally:
                client.close()
            return
        role = 'worker' if args.command == 'host' else 'operator' if args.operator else 'player'
        activity_id = args.activity if role == 'worker' else None
        client = Client.session(args.workspace, args.actor, role, activity_id) if args.transport == 'stdio' else Client.participant(args.workspace, args.actor, role, activity_id)
        try:
            client.view()
            if args.command == 'host':
                if args.action == 'packet':
                    packet, ref = client.prepared(args.activity)
                    print(encoded({'packet': packet, 'input_ref': ref, 'output_root': str(client.output_root), 'binding_id': client.binding_id}))
                elif args.action == 'act':
                    if not args.choice:
                        raise Fault('INVALID')
                    print(encoded(client.act(args.activity, args.choice)))
                elif args.action == 'return':
                    packet, ref = client.prepared(args.activity)
                    if not args.file:
                        raise Fault('INVALID')
                    checks = json.loads(Path(args.checks).read_text()) if args.checks else []
                    output_ref = client.submit_file(packet, Path(args.file).absolute())
                    print(encoded(client.receive(packet, ref, [output_ref], checks)))
                elif args.action == 'call':
                    if not args.file:
                        raise Fault('INVALID')
                    print(encoded(client.call(decode(Path(args.file).read_bytes()))))
            elif args.do:
                print(execute(client, args.do, args.actor))
            elif args.plain:
                print(execute(client, 'view', args.actor))
                while True:
                    try:
                        text = input('samsara> ')
                    except EOFError:
                        break
                    if text in ('quit', '/quit'):
                        break
                    try:
                        print(execute(client, text, args.actor))
                    except (Fault, ValueError, StopIteration) as exc:
                        print(exc.code if isinstance(exc, Fault) else 'INVALID')
            else:
                from .terminal import SamsaraTerminal
                SamsaraTerminal(client, args.actor).run()
        finally:
            client.close()
    except (Fault, OSError, ValueError) as exc:
        print(encoded({'error': exc.code if isinstance(exc, Fault) else 'UNAVAILABLE'}),
              file=sys.stdout if args.command == 'stdio' else sys.stderr, flush=True)
        raise SystemExit(1)
