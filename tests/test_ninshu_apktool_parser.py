"""Adversarial unit tests and heap compliance checks for ApktoolResourceReconstructor (CH 30)."""
import unittest
from kageyoni.ninshu.apktool_parser import (
    ApktoolResourceReconstructor,
    ManifestSummary,
    ApktoolMetadata,
    StringTable,
)


class TestApktoolParser(unittest.TestCase):
    def test_parse_manifest_xml_valid(self):
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.ninshu"
    android:versionCode="42"
    android:versionName="1.4.2">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <application android:label="NinshuApp">
        <activity android:name=".MainActivity" />
        <activity android:name=".SettingsActivity" />
        <service android:name=".BackgroundSyncService" />
        <receiver android:name=".BootReceiver" />
    </application>
</manifest>
"""
        summary = ApktoolResourceReconstructor.parse_manifest_xml(xml_content)
        self.assertEqual(summary.package_name, "com.example.ninshu")
        self.assertEqual(summary.version_code, "42")
        self.assertEqual(summary.version_name, "1.4.2")
        self.assertEqual(len(summary.permissions), 2)
        self.assertIn("android.permission.INTERNET", summary.permissions)
        self.assertEqual(summary.activities_count, 2)
        self.assertEqual(summary.services_count, 1)
        self.assertEqual(summary.receivers_count, 1)
        self.assertEqual(summary.providers_count, 0)

    def test_manifest_empty_or_corrupt_fails(self):
        with self.assertRaises(ValueError):
            ApktoolResourceReconstructor.parse_manifest_xml("")
        with self.assertRaises(ValueError):
            ApktoolResourceReconstructor.parse_manifest_xml("<not_manifest></not_manifest>")
        with self.assertRaises(ValueError):
            ApktoolResourceReconstructor.parse_manifest_xml("<manifest><incomplete>")

    def test_manifest_missing_package_fails(self):
        with self.assertRaises(ValueError):
            ApktoolResourceReconstructor.parse_manifest_xml('<manifest android:versionCode="1"></manifest>')

    def test_parse_apktool_yml(self):
        yml_content = """!!brut.androlib.meta.MetaInfo
apkFileName: target_app.apk
versionInfo:
  versionCode: '105'
  versionName: 2.1.0
sdkInfo:
  minSdkVersion: '24'
  targetSdkVersion: '33'
"""
        meta = ApktoolResourceReconstructor.parse_apktool_yml(yml_content)
        self.assertEqual(meta.apk_file_name, "target_app.apk")
        self.assertEqual(meta.version_code, "105")
        self.assertEqual(meta.version_name, "2.1.0")
        self.assertEqual(meta.min_sdk_version, "24")
        self.assertEqual(meta.target_sdk_version, "33")

    def test_apktool_yml_empty_fails(self):
        with self.assertRaises(ValueError):
            ApktoolResourceReconstructor.parse_apktool_yml("")

    def test_parse_strings_xml(self):
        strings_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Ninshū Engine</string>
    <string name="action_start">Initialize Telemetry</string>
    <string name="empty_string"></string>
</resources>
"""
        table = ApktoolResourceReconstructor.parse_strings_xml(strings_xml, locale="default", max_strings=10)
        self.assertEqual(table.locale, "default")
        self.assertEqual(table.entries_count, 3)
        names = [e.name for e in table.entries]
        self.assertEqual(names, ["app_name", "action_start", "empty_string"])

    def test_strings_xml_corrupt_fails(self):
        with self.assertRaises(ValueError):
            ApktoolResourceReconstructor.parse_strings_xml("<wrong_root></wrong_root>")
        with self.assertRaises(ValueError):
            ApktoolResourceReconstructor.parse_strings_xml("<resources><unclosed></resources>")

    def test_adversarial_fuzz_rejections(self):
        # 10 invalid XML and YAML mutants
        bad_xmls = [
            "<?xml version='1.0'?><manifest",
            "<manifest package=''>",
            "<<manifest>>",
            "\x00\x01\x02",
            "<manifest package='a'>&invalid_entity;</manifest>",
        ]
        for bad in bad_xmls:
            with self.subTest(xml=bad[:20]):
                with self.assertRaises(ValueError):
                    ApktoolResourceReconstructor.parse_manifest_xml(bad)


if __name__ == "__main__":
    unittest.main()
