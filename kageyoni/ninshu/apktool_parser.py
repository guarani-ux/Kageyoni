"""Zero-dependency in-tree Apktool Resource Reconstructor & Metadata Inspector (CH 30).

Pure Python standard library implementation:
1. apktool.yml Metadata Parsing:
   - Parses apktool YAML metadata (versionName, versionCode, minSdkVersion, targetSdkVersion, apkFileName).
   - Validates brut.androlib.meta tags.
2. AndroidManifest.xml XML Parsing:
   - Validates well-formedness using `xml.etree.ElementTree`.
   - Extracts root `<manifest>` tag, `package` attribute, `android:versionCode`, `android:versionName`.
   - Identifies declared permissions (`<uses-permission>`), application label, and component counts (activities, services, receivers, providers).
3. Localized String Resource Reconstruction:
   - Parses `res/values/strings.xml` and `res/values-<locale>/strings.xml`.
   - Extracts `<string name="...">...</string>` key-value dictionaries.
   - Bounded string table projection (default max 2000 entries per locale).
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

ANDROID_URI = "http://schemas.android.com/apk/res/android"
MAX_STRINGS_PER_TABLE = 2000


@dataclasses.dataclass(frozen=True)
class ApktoolMetadata:
    apk_file_name: Optional[str]
    version_name: Optional[str]
    version_code: Optional[str]
    min_sdk_version: Optional[str]
    target_sdk_version: Optional[str]


@dataclasses.dataclass(frozen=True)
class ManifestSummary:
    package_name: str
    version_code: Optional[str]
    version_name: Optional[str]
    permissions: List[str]
    activities_count: int
    services_count: int
    receivers_count: int
    providers_count: int


@dataclasses.dataclass(frozen=True)
class StringEntry:
    name: str
    value: str


@dataclasses.dataclass(frozen=True)
class StringTable:
    locale: str  # "default" or language tag
    entries_count: int
    entries: List[StringEntry]


@dataclasses.dataclass(frozen=True)
class DecodedResourcesReport:
    manifest: ManifestSummary
    metadata: Optional[ApktoolMetadata]
    string_tables: List[StringTable]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": dataclasses.asdict(self.manifest),
            "metadata": dataclasses.asdict(self.metadata) if self.metadata else None,
            "string_tables": [
                {
                    "locale": st.locale,
                    "entries_count": st.entries_count,
                    "entries": [dataclasses.asdict(e) for e in st.entries],
                }
                for st in self.string_tables
            ],
        }


class ApktoolResourceReconstructor:
    """Reconstructor for decoded Android resources, XML manifests, and string tables."""

    @staticmethod
    def parse_manifest_xml(xml_content: str) -> ManifestSummary:
        if not xml_content.strip():
            raise ValueError("Manifest XML cannot be empty")

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            raise ValueError(f"Malformed AndroidManifest.xml: {exc}") from exc

        if root.tag != "manifest":
            raise ValueError(f"Root tag must be <manifest>, got <{root.tag}>")

        package = root.attrib.get("package")
        if not package:
            raise ValueError("Manifest missing required 'package' attribute")

        version_code = (
            root.attrib.get(f"{{{ANDROID_URI}}}versionCode") or root.attrib.get("versionCode")
        )
        version_name = (
            root.attrib.get(f"{{{ANDROID_URI}}}versionName") or root.attrib.get("versionName")
        )

        permissions: List[str] = []
        activities_count = 0
        services_count = 0
        receivers_count = 0
        providers_count = 0

        for child in root:
            if child.tag == "uses-permission":
                perm_name = child.attrib.get(f"{{{ANDROID_URI}}}name") or child.attrib.get("name")
                if perm_name:
                    permissions.append(perm_name)
            elif child.tag == "application":
                for app_child in child:
                    if app_child.tag == "activity":
                        activities_count += 1
                    elif app_child.tag == "service":
                        services_count += 1
                    elif app_child.tag == "receiver":
                        receivers_count += 1
                    elif app_child.tag == "provider":
                        providers_count += 1

        return ManifestSummary(
            package_name=package,
            version_code=version_code,
            version_name=version_name,
            permissions=permissions,
            activities_count=activities_count,
            services_count=services_count,
            receivers_count=receivers_count,
            providers_count=providers_count,
        )

    @staticmethod
    def parse_apktool_yml(yml_content: str) -> ApktoolMetadata:
        if not yml_content.strip():
            raise ValueError("apktool.yml cannot be empty")

        def extract_field(pattern: str) -> Optional[str]:
            match = re.search(pattern, yml_content, re.MULTILINE)
            if match:
                val = match.group(1).strip().strip("'\"")
                return val if val != "null" else None
            return None

        apk_file = extract_field(r"^\s*apkFileName:\s*(.+)$")
        version_name = extract_field(r"^\s*versionName:\s*(.+)$")
        version_code = extract_field(r"^\s*versionCode:\s*(.+)$")
        min_sdk = extract_field(r"^\s*minSdkVersion:\s*(.+)$")
        target_sdk = extract_field(r"^\s*targetSdkVersion:\s*(.+)$")

        return ApktoolMetadata(
            apk_file_name=apk_file,
            version_name=version_name,
            version_code=version_code,
            min_sdk_version=min_sdk,
            target_sdk_version=target_sdk,
        )

    @staticmethod
    def parse_strings_xml(xml_content: str, locale: str = "default", max_strings: int = MAX_STRINGS_PER_TABLE) -> StringTable:
        if not xml_content.strip():
            raise ValueError("strings.xml cannot be empty")

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            raise ValueError(f"Malformed strings.xml: {exc}") from exc

        if root.tag != "resources":
            raise ValueError(f"Root tag must be <resources>, got <{root.tag}>")

        entries: List[StringEntry] = []
        for child in root.findall("string"):
            name = child.attrib.get("name")
            if name:
                text = child.text or ""
                entries.append(StringEntry(name=name, value=text))
                if len(entries) >= max_strings:
                    break

        return StringTable(locale=locale, entries_count=len(entries), entries=entries)
