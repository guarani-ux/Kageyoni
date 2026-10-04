"""Read-only legacy snapshot export into the supplementary evidence ledger.

This preserves source rows and their timestamp fields. It does not migrate
application identity, permissions, replay semantics, or domain schemas.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from kageyoni.engine import digest, encoded
from kageyoni.ledger import EvidenceLedger
from kageyoni.persistence.unit_of_work import UnitOfWork


def _identifier(name):
    return '"' + name.replace('"', '""') + '"'


def _json_value(value):
    if isinstance(value, bytes):
        return {'sqlite_blob_hex': value.hex()}
    return value


def _timestamp(row):
    for key in ('created_at', 'timestamp', 'date_recorded', 'time'):
        value = row.get(key)
        if value is None or value == '': continue
        try:
            return float(value), key
        except (TypeError, ValueError):
            try:
                parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    # Do not invent a timezone for an ambiguous historical time.
                    return None, key
                return parsed.timestamp(), key
            except ValueError:
                return None, key
    return None, None


class DatabaseMigrator:
    """Compatibility name for an atomic, idempotent snapshot exporter."""
    def __init__(self, target_ledger): self.ledger = target_ledger

    def migrate_from_connection(self, source_conn):
        if source_conn is self.ledger.conn:
            raise ValueError('source and target must differ')
        owns_read = not source_conn.in_transaction
        if owns_read: source_conn.execute('BEGIN')
        try:
            extracted = []
            tables = source_conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            for table, ddl in tables:
                name = _identifier(table)
                schema = source_conn.execute('PRAGMA table_info(' + name + ')').fetchall()
                columns = [c[1] for c in schema]
                primary = [c[1] for c in sorted(schema, key=lambda c: c[5]) if c[5]]
                rows = source_conn.execute('SELECT * FROM ' + name).fetchall()
                normalized = [dict(zip(columns, map(_json_value, row))) for row in rows]
                normalized.sort(key=encoded)
                for ordinal, row in enumerate(normalized):
                    identity = {k: row[k] for k in primary} if primary else {'snapshot_ordinal': ordinal}
                    timestamp, timestamp_field = _timestamp(row)
                    kind = next((k for k in ('scar','outcome','dispatch','assessment') if k+'_id' in row), 'event')
                    extracted.append(dict(table=table, schema=ddl, identity=identity, row=row,
                        timestamp=timestamp, timestamp_field=timestamp_field, kind=kind,
                        actor=str(row.get('actor_id') or row.get('participant_id') or 'unknown'),
                        topic=str(row.get('topic') or row.get('encounter_id') or table)))
        finally:
            if owns_read: source_conn.rollback()
        snapshot = digest(extracted)
        # Known times first; unknown times retain a deterministic storage order,
        # not a claimed chronology. Source fields are never replaced by now().
        extracted.sort(key=lambda e: (e['timestamp'] is None, e['timestamp'] or 0,
                                     e['table'], encoded(e['identity'])))
        count = 0
        with UnitOfWork(self.ledger.conn):
            valid, error = self.ledger.verify_integrity()
            if not valid: raise RuntimeError('Target ledger integrity failure: ' + str(error))
            for item in extracted:
                event_id = 'export:' + digest({'snapshot':snapshot, 'table':item['table'], 'identity':item['identity']})
                payload = {'source_row':item['row'], 'source_schema':item['schema'],
                           'source_snapshot_digest':snapshot, 'source_table':item['table'],
                           'source_identity':item['identity'], 'source_timestamp':item['timestamp'],
                           'source_timestamp_field':item['timestamp_field'],
                           'scope':'legacy snapshot export; domain migration not performed'}
                prior = self.ledger.conn.execute('SELECT payload_json FROM '+self.ledger.table_name+' WHERE event_id=?', (event_id,)).fetchone()
                if prior:
                    if digest(json.loads(prior[0])) != digest(payload):
                        raise RuntimeError('Conflicting export identity')
                    continue
                self.ledger.record(kind=item['kind'], actor_id=item['actor'], topic=item['topic'],
                                   payload=payload, event_id=event_id)
                count += 1
            valid, error = self.ledger.verify_integrity()
            if not valid: raise RuntimeError('Post-export integrity failure: ' + str(error))
        return count


def migrate_files(source_path, target_path):
    source_path, target_path = Path(source_path).resolve(), Path(target_path).resolve()
    if source_path == target_path: raise ValueError('source and target must differ')
    source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
    target = sqlite3.connect(target_path)
    try:
        return DatabaseMigrator(EvidenceLedger(target)).migrate_from_connection(source)
    finally:
        source.close(); target.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export a legacy SQLite snapshot to EvidenceLedger.')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--target', required=True, type=Path)
    args = parser.parse_args()
    print(f'Exported {migrate_files(args.source, args.target)} new snapshot records to {args.target}')
