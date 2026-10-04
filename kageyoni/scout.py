"""
kageyoni.scout: Universal Static Carrier & AST Organ Scout.

Extracts capability manifests, class hierarchies, method signatures,
and docstrings across constellation codebases using pure AST parsing
without executing untrusted code.
"""

from __future__ import annotations
import ast
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


DEFAULT_EXCLUDES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "temp_venv",
    "node_modules",
    ".agents",
}


@dataclass
class FunctionSignature:
    """Signature and metadata for an inspected function or method."""
    name: str
    args: List[str]
    docstring: str
    line_number: int


@dataclass
class CarrierManifest:
    """Static capability manifest representing a parsed Python source file."""
    file_path: str
    relative_path: str
    classes: Dict[str, List[FunctionSignature]]
    functions: List[FunctionSignature]
    module_docstring: str
    sha256: str
    line_count: int

    def summary(self) -> str:
        cls_count = len(self.classes)
        fn_count = len(self.functions)
        return f"{self.relative_path} ({cls_count} classes, {fn_count} functions, {self.line_count} lines)"


class CarrierScout:
    """
    AST organ scout for static capability discovery.
    """

    def __init__(self, manifests: Optional[List[CarrierManifest]] = None):
        self.manifests: List[CarrierManifest] = manifests or []

    def scan_file(self, file_path: Path, relative_to: Optional[Path] = None) -> Optional[CarrierManifest]:
        """
        Parses a single Python file into a CarrierManifest.
        Fails safely and returns None if syntax or decode errors occur.
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            return None

        try:
            raw_bytes = path.read_bytes()
        except OSError:
            return None

        hasher = hashlib.sha256(raw_bytes)
        file_sha256 = hasher.hexdigest()

        try:
            source = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                source = raw_bytes.decode("latin-1")
            except Exception:
                return None

        try:
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, ValueError):
            return None

        line_count = len(source.splitlines())
        mod_docstring = ast.get_docstring(tree) or ""

        classes: Dict[str, List[FunctionSignature]] = {}
        functions: List[FunctionSignature] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._parse_function(node))
            elif isinstance(node, ast.ClassDef):
                cls_methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        cls_methods.append(self._parse_function(item))
                classes[node.name] = cls_methods

        rel_path = str(path.relative_to(relative_to)) if relative_to and path.is_relative_to(relative_to) else str(path)

        manifest = CarrierManifest(
            file_path=str(path),
            relative_path=rel_path,
            classes=classes,
            functions=functions,
            module_docstring=mod_docstring,
            sha256=file_sha256,
            line_count=line_count,
        )
        return manifest

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionSignature:
        args: List[str] = []
        for a in node.args.posonlyargs:
            args.append(a.arg)
        for a in node.args.args:
            args.append(a.arg)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        for a in node.args.kwonlyargs:
            args.append(a.arg)
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        doc = ast.get_docstring(node) or ""
        return FunctionSignature(
            name=node.name,
            args=args,
            docstring=doc,
            line_number=node.lineno,
        )

    def scout_directory(
        self,
        root: Path,
        max_depth: int = 4,
        exclude_dirs: Optional[Set[str]] = None,
    ) -> List[CarrierManifest]:
        """
        Recursively discovers all Python files up to max_depth, ignoring excluded directories.
        """
        root_path = Path(root).resolve()
        excludes = set(exclude_dirs) if exclude_dirs else DEFAULT_EXCLUDES
        manifests: List[CarrierManifest] = []

        for dirpath, dirnames, filenames in os.walk(root_path):
            current_dir = Path(dirpath)
            depth = len(current_dir.relative_to(root_path).parts)
            if depth > max_depth:
                dirnames.clear()
                continue

            # In-place directory exclusion
            dirnames[:] = [d for d in dirnames if d not in excludes and not d.startswith(".")]

            for fn in filenames:
                if fn.endswith(".py"):
                    fpath = current_dir / fn
                    man = self.scan_file(fpath, relative_to=root_path)
                    if man:
                        manifests.append(man)

        self.manifests = manifests
        return manifests

    def find_capability(
        self,
        query: str,
        manifests: Optional[List[CarrierManifest]] = None,
        top_k: int = 5,
    ) -> List[Tuple[CarrierManifest, float]]:
        """
        Ranks manifests by relevance to search keywords using multi-field AST token weighting.
        """
        candidates = manifests if manifests is not None else self.manifests
        terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        if not terms:
            return []

        scored: List[Tuple[CarrierManifest, float]] = []

        for man in candidates:
            score = 0.0
            path_str = man.relative_path.lower()
            mod_doc = man.module_docstring.lower()

            for term in terms:
                # Path relevance
                if term in path_str:
                    score += 3.0
                # Module docstring
                if term in mod_doc:
                    score += 2.0

                # Classes & methods
                for cls_name, methods in man.classes.items():
                    if term in cls_name.lower():
                        score += 4.0
                    for m in methods:
                        if term in m.name.lower():
                            score += 3.5
                        if term in m.docstring.lower():
                            score += 1.5

                # Top-level functions
                for fn in man.functions:
                    if term in fn.name.lower():
                        score += 3.5
                    if term in fn.docstring.lower():
                        score += 1.5

            if score > 0.0:
                scored.append((man, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
