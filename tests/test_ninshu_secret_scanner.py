"""Unit & Adversarial Verification Suite for Ninshū Fast Token & Secret Regex Radar (CH 38).

Tests:
1. Valid detections for AWS Access Key & Secret Key, GitHub PATs, Google API Keys, Slack Tokens, Private Keys, JWTs.
2. Masking verification & preview safety (never leaks raw token in preview).
3. Shannon entropy gate: filters low-entropy / repetitive candidate tokens.
4. Fail-closed invariants: empty input, null-byte injection, oversized payload (>64 KB), malformed UTF-8.
5. Thermodynamic profiling (heap ceiling <= 64 KB via ThermodynamicProfiler).
6. Adversarial fuzz vectors: binary data, massive repetitive tokens, catastrophic backtracking protection.
"""
import hashlib
import time
import unittest

from kageyoni.ninshu.secret_scanner import (
    SecretScanner,
    SecretMatch,
    SecretScanSummary,
    InvalidInputError,
    calculate_shannon_entropy,
    mask_secret,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestSecretScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = SecretScanner()

    def test_aws_access_key_detection(self):
        content = "Configuring AWS: export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE in bashrc."
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "aws_access_key_id" for m in matches))
        match = next(m for m in matches if m.token_type == "aws_access_key_id")
        self.assertEqual(match.rule_id, "SEC001_AWS_ACCESS_KEY")
        self.assertTrue(match.raw_preview_masked.startswith("AKIA"))
        self.assertTrue(match.raw_preview_masked.endswith("MPLE"))
        self.assertNotIn("FODNN7EXA", match.raw_preview_masked)
        self.assertEqual(
            match.sha256_hash,
            hashlib.sha256(b"AKIAIOSFODNN7EXAMPLE").hexdigest(),
        )

    def test_aws_secret_key_detection(self):
        content = "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "aws_secret_access_key" for m in matches))
        match = next(m for m in matches if m.token_type == "aws_secret_access_key")
        self.assertEqual(match.rule_id, "SEC002_AWS_SECRET_KEY")
        self.assertTrue(match.raw_preview_masked.startswith("wJal"))
        self.assertTrue(match.raw_preview_masked.endswith("EKEY"))

    def test_github_pat_classic(self):
        # ghp_ + 36 characters = 40 characters
        token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        content = f"Authorization: token {token}"
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "github_pat_classic" for m in matches))
        match = next(m for m in matches if m.token_type == "github_pat_classic")
        self.assertEqual(match.rule_id, "SEC003_GITHUB_PAT_CLASSIC")
        self.assertTrue(match.raw_preview_masked.startswith("ghp_"))
        self.assertNotIn("abcdefgh", match.raw_preview_masked)

    def test_github_pat_fine_grained(self):
        # github_pat_ (11 chars) + 82 characters = 93 characters
        token = "github_pat_" + "11ABCD1234_abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ012345678"
        self.assertEqual(len(token), 93)
        content = f"repo clone with token: {token}"
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "github_pat_fine_grained" for m in matches))
        match = next(m for m in matches if m.token_type == "github_pat_fine_grained")
        self.assertEqual(match.rule_id, "SEC004_GITHUB_PAT_FINE_GRAINED")
        self.assertTrue(match.raw_preview_masked.startswith("gith"))

    def test_github_oauth_token(self):
        token = "gho_1234567890abcdefghijklmnopqrstuvwxyz"
        content = f"oauth callback token: {token}"
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "github_oauth_token" for m in matches))

    def test_google_api_key(self):
        token = "AIzaSyD-1234567890abcdefghijklmnopqrstu"
        content = f"https://maps.googleapis.com/maps/api/js?key={token}&callback=initMap"
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "google_api_key" for m in matches))
        match = next(m for m in matches if m.token_type == "google_api_key")
        self.assertEqual(match.rule_id, "SEC006_GOOGLE_API_KEY")
        self.assertTrue(match.raw_preview_masked.startswith("AIza"))

    def test_slack_api_token(self):
        token = "xoxb-123456789012-345678901234-abcdefghijklmnopqrstuvwx"
        content = f"SLACK_BOT_TOKEN = '{token}'"
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "slack_api_token" for m in matches))
        match = next(m for m in matches if m.token_type == "slack_api_token")
        self.assertEqual(match.rule_id, "SEC007_SLACK_TOKEN")

    def test_generic_private_key(self):
        content = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Y3w8...fake...content\n"
            "-----END RSA PRIVATE KEY-----"
        )
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "private_key_header" for m in matches))

    def test_jwt_token(self):
        # eyJ header + eyJ payload + signature
        token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        content = f"Bearer {token}"
        matches = self.scanner.scan(content)
        self.assertTrue(any(m.token_type == "json_web_token" for m in matches))
        match = next(m for m in matches if m.token_type == "json_web_token")
        self.assertEqual(match.rule_id, "SEC009_JWT_TOKEN")
        self.assertTrue(match.entropy > 4.2)

    def test_shannon_entropy_gate_rejects_repetitive_tokens(self):
        repetitive_aws = "AKIAAAAAAAAAAAAAAAAA"
        content = f"Invalid dummy test key: {repetitive_aws}"
        matches = self.scanner.scan(content)
        self.assertFalse(any(m.token_type == "aws_access_key_id" for m in matches))

    def test_masking_helper(self):
        self.assertEqual(mask_secret(""), "****")
        self.assertEqual(mask_secret("123"), "****")
        self.assertEqual(mask_secret("1234"), "****")
        self.assertEqual(mask_secret("12345"), "1***5")
        self.assertEqual(mask_secret("1234567890"), "1234**7890")
        masked = mask_secret("AKIAIOSFODNN7EXAMPLE", 4, 4)
        self.assertEqual(masked, "AKIA************MPLE")

    def test_fail_closed_empty_and_nulls(self):
        with self.assertRaises(InvalidInputError):
            self.scanner.scan("")

        with self.assertRaises(InvalidInputError):
            self.scanner.scan(b"")

        with self.assertRaises(InvalidInputError):
            self.scanner.scan("Some prefix\x00with null byte")

        with self.assertRaises(InvalidInputError):
            self.scanner.scan(b"\xff\xfe\xfa\xbc")

    def test_fail_closed_memory_ceiling_exceeded(self):
        oversized = "A" * (65536 + 1)
        with self.assertRaises(InvalidInputError):
            self.scanner.scan(oversized)

        oversized_bytes = b"A" * (65536 + 1)
        with self.assertRaises(InvalidInputError):
            self.scanner.scan(oversized_bytes)

    def test_catastrophic_backtracking_protection(self):
        adversarial_input = "xoxb-" + "A" * 5000 + "!"
        start_time = time.perf_counter()
        matches = self.scanner.scan(adversarial_input)
        elapsed = time.perf_counter() - start_time
        self.assertLess(elapsed, 0.5, "Regex engine succumbed to backtracking delay!")
        self.assertEqual(len(matches), 0)

    def test_thermodynamic_heap_ceiling(self):
        payload = (
            b"AKIAIOSFODNN7EXAMPLE "
            b"ghp_1234567890abcdefghijklmnopqrstuvwxyz "
            b"AIzaSyD-1234567890abcdefghijklmnopqrstu "
        )
        summary, receipt = ThermodynamicProfiler.profile_callable(
            SecretScanner.parse_bytes,
            payload,
            candidate_id="secret_scanner_ch38",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertGreaterEqual(summary.matches_count, 3)

    def test_adversarial_mutant_fuzzing(self):
        base_payload = (
            b"AKIAIOSFODNN7EXAMPLE "
            b"ghp_1234567890abcdefghijklmnopqrstuvwxyz "
            b"AIzaSyD-1234567890abcdefghijklmnopqrstu"
        )
        mutants = AdversarialMutator.generate_adversarial_suite(base_payload)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = SecretScanner.parse_bytes(m.payload)
                self.assertIsInstance(summary.matches_count, int)
            except InvalidInputError:
                pass
            except Exception as e:
                self.fail(f"Unexpected exception {type(e).__name__} on mutant {m.mutant_id}: {e}")


if __name__ == "__main__":
    unittest.main()
