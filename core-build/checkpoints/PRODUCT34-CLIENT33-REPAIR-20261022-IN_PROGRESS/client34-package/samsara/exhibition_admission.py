"""Selected exhibition anchors and immutable native activation provenance.

Internal equipment for ContentSets, never a participant snapshot/attach API.
No record, artifact, consent or registry write is performed here. The native
Contests history reader remains the one authority for local historical images.
Missing inherited/local history refuses reload rather than guessing an image.
"""
from copy import deepcopy
import re

from kageyoni.engine import Rejected
from kageyoni.contests import Contests
from .contentsets import parse, require, shape, text, validate_relational_uniqueness
from .protocol import Fault, digest

FORMAT = 'samsara-authored-exhibition/1'
ACTOR = 'content-operator'
NARRATIVE = ('Activate explicitly authored synthetic content; preserve existing '
             'anchors and all prior history.')


def selected_refs(carrier):
    """Validate reference identities before making any native lookup."""
    require(isinstance(carrier, dict) and carrier.get('format') == FORMAT)
    refs = carrier.get('existing_refs')
    require(type(refs) is list and len(refs) <= 256)
    seen = set()
    for ref in refs:
        shape(ref, ('id', 'domain', 'record_revision', 'snapshot_hash'))
        text(ref['id'], 128); text(ref['domain'], 128)
        require(ref['id'] not in seen)
        seen.add(ref['id'])
        require(type(ref['record_revision']) is int and ref['record_revision'] > 0
                and type(ref['snapshot_hash']) is str
                and re.fullmatch('[0-9a-f]{64}', ref['snapshot_hash']) is not None)
    return refs


class ExhibitionAdmission:
    def __init__(self, app):
        self.app, self.engine, self.db = app, app.engine, app.db
        self.history = Contests(self.engine)

    @staticmethod
    def enabled(blob):
        value = parse(blob)
        return isinstance(value, dict) and value.get('format') == FORMAT

    def _matched(self, ref, image):
        require(isinstance(image, dict) and image.get('branch') == self.app.branch
                and image.get('id') == ref['id'] and image.get('domain') == ref['domain']
                and image.get('version') == ref['record_revision']
                and digest(image) == ref['snapshot_hash'], 'DEPENDENCY')
        return deepcopy(image)

    def current_anchors(self, carrier):
        """Preparation/admission uses today's exact selected native images."""
        return {ref['id']: self._matched(ref, self.engine.get(self.app.branch, ref['id']))
                for ref in selected_refs(carrier)}

    def command(self, carrier, preparation_ref, expected_revision):
        require(type(expected_revision) is int and expected_revision >= 0)
        require(type(carrier.get('native_records')) is list
                and 0 < len(carrier['native_records']) <= 5000)
        return {'api_version': 3, 'branch': self.app.branch,
                'request_id': self.app.key('content-activate-records', preparation_ref),
                'expected_revision': expected_revision, 'actor': ACTOR,
                'kind': 'maintenance', 'narrative': NARRATIVE,
                'changes': deepcopy(carrier['native_records'])}

    def provenance(self, carrier, preparation_ref, expected_revision, receipt):
        """Build only from the actual returned native receipt, then verify it."""
        value = {'branch': self.app.branch, 'expected_revision': expected_revision,
                 'native_receipt': deepcopy(receipt)}
        self.historical_anchors(carrier, preparation_ref, value)
        return value

    def historical_anchors(self, carrier, preparation_ref, activation):
        """Reload uses the verified activation boundary, never current versions.

        The locator and preparation artifacts must already have their original
        private operator grants and consumer pins checked by ContentSets. This
        proof checks the actual local native command, receipt and CREATE images.
        Public hashes by themselves grant no authoring or actor authority.
        """
        refs = selected_refs(carrier)
        shape(activation, ('branch', 'expected_revision', 'native_receipt'))
        expected = activation['expected_revision']; receipt = activation['native_receipt']
        require(activation['branch'] == self.app.branch
                and type(expected) is int and expected >= 0
                and isinstance(receipt, dict), 'DEPENDENCY')
        try:
            event, command, recorded = self.history._event(self.app.branch, receipt['event_id'])
            require(recorded == receipt and receipt['replayed'] is False
                    and receipt['revision'] == expected + 1
                    and command == self.command(carrier, preparation_ref, expected), 'DEPENDENCY')
            changes = carrier['native_records']
            ids = [change['id'] for change in changes]
            require(len(ids) == len(set(ids)) and receipt['changed'] == ids, 'DEPENDENCY')
            # Require each create to have its actual local before=None image;
            # an unrelated event or a patch cannot stand in for admission.
            for change in changes:
                require(change['op'] == 'create', 'DEPENDENCY')
                before, after = self.history._historical_record(event['id'], change['id'])
                require(before is None and after['branch'] == self.app.branch
                        and after['updated_event'] == event['id'] and after['version'] == 1
                        and after['domain'] == change['domain'], 'DEPENDENCY')
            return {ref['id']: self._matched(ref, self.history._image_before(
                    self.app.branch, ref['id'], expected)) for ref in refs}
        except (Rejected, KeyError, TypeError, ValueError):
            raise Fault('DEPENDENCY') from None

    def definitions(self, carrier):
        # Late import avoids a compiler/ContentSets module cycle. Only the
        # root-validated immutable profile is projected into fixed wrappers.
        from .exhibition_profiles import authored_encounters
        return authored_encounters(carrier)

    def validate(self, blob, *, conflicts=False, preparation_ref=None, activation=None):
        from .exhibition_profiles import validate_profile
        carrier = parse(blob)
        anchors = (self.current_anchors(carrier) if activation is None else
                   self.historical_anchors(carrier, preparation_ref, activation))
        value = validate_profile(blob, anchor_images=anchors,
                                 validate_native_record=self.engine._validate_record)
        validate_relational_uniqueness(value['native_records'],
            self.engine.state(self.app.branch) if conflicts else ())
        if conflicts:
            for record in value['native_records']:
                require(self.engine.get(self.app.branch, record['id']) is None, 'CONFLICT')
            for encounter in self.definitions(value):
                require(self.db.execute('SELECT 1 FROM encounter_definitions '
                    'WHERE definition_id=? AND version=?',
                    (encounter['id'], encounter['version'])).fetchone() is None, 'CONFLICT')
        return value
