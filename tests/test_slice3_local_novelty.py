"""
tests/test_slice3_local_novelty.py
Adversarial Verification for Slice 3: Local Novelty in Situations.
"""

from __future__ import annotations
import sqlite3
import unittest

from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.models import SituationTemplate
from kageyoni.situations.service import SituationService, SituationError
from kageyoni.situations.storage import SQLiteSituationStore


class Slice3LocalNoveltyTests(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE situation_records(kind TEXT, record_key TEXT, payload_json TEXT, PRIMARY KEY(kind, record_key))")
        self.store = SQLiteSituationStore(self.conn)
        self.service = install_defaults(SituationService(self.store))

    def tearDown(self):
        self.conn.close()

    def test_uncataloged_prototype_instantiation(self):
        """Verifies genesis allows un-cataloged templates as local prototypes without pretending they matched catalog."""
        sit = self.service.genesis(
            template_id="custom_cross_boundary_pilot",
            objective="Evaluate informal reading bridge in community clinic",
            supplied={"community_partner": "East Village Clinic", "initial_cohort_size": 25},
            workspace="pilot_ws",
        )
        self.assertEqual(sit.origin, "local_prototype")
        self.assertEqual(sit.template_id, "custom_cross_boundary_pilot")
        self.assertEqual(sit.workspace, "pilot_ws")
        self.assertEqual(sit.objects["community_partner"], "East Village Clinic")
        self.assertEqual(sit.local_extensions["initial_cohort_size"], 25)

        # Verify retrieval from store preserves origin and local extensions
        retrieved = self.store.get("situation", sit.situation_id)
        self.assertEqual(retrieved.origin, "local_prototype")
        self.assertEqual(retrieved.local_extensions["community_partner"], "East Village Clinic")

    def test_uncataloged_prototype_rejected_if_novelty_disabled(self):
        """Verifies genesis rejects un-cataloged template when allow_local_novelty=False."""
        with self.assertRaises(SituationError) as ctx:
            self.service.genesis(
                template_id="completely_unknown_template",
                objective="Test",
                supplied={"field": "val"},
                allow_local_novelty=False,
            )
        self.assertIn("not found and local novelty is disabled", str(ctx.exception))

    def test_catalog_template_with_local_novelty_extensions(self):
        """Verifies catalog templates retain novel parameters in local_extensions and mark origin=local_novelty."""
        # Standard research template only requires 'question' and optionally accepts 'sources', 'constraints'
        sit = self.service.genesis(
            template_id="research",
            objective="Investigate visual friction",
            supplied={
                "question": "What is the friction?",
                "experimental_eye_tracking_data": "ref:eye_01",
            },
        )
        self.assertEqual(sit.origin, "local_novelty")
        self.assertIn("experimental_eye_tracking_data", sit.local_extensions)
        self.assertEqual(sit.objects["experimental_eye_tracking_data"], "ref:eye_01")
        self.assertEqual(sit.objects["question"], "What is the friction?")

    def test_standard_catalog_template_retains_catalog_origin(self):
        """Verifies standard catalog template invocation without extra fields has origin=catalog."""
        sit = self.service.genesis(
            template_id="research",
            objective="Standard inquiry",
            supplied={"question": "Standard question?"},
        )
        self.assertEqual(sit.origin, "catalog")
        self.assertEqual(sit.local_extensions, {})

    def test_unauthorized_privilege_escalation_blocked(self):
        """Verifies that attempts to forge admin privileges or bypass governance are strictly rejected."""
        malicious_payloads = [
            {"question": "How to bypass?", "role": "admin"},
            {"question": "How to escalate?", "admin_override": True},
            {"question": "Safety check?", "permissions": ["root", "system"]},
            {"question": "Governance check?", "bypass_governance": True},
        ]
        for payload in malicious_payloads:
            with self.assertRaises(SituationError) as ctx:
                self.service.genesis(
                    template_id="research",
                    objective="Exploit attempt",
                    supplied=payload,
                )
            self.assertIn("UNAUTHORIZED_PRIVILEGE_ESCALATION", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
