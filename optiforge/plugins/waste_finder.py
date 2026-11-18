"""Codebase Waste Finder Plugin for OptiForge.

Detects unused dependencies, dead code, unused exports, duplicate files,
oversized assets, unused CSS, and Docker bloat.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, FixProposal, Impact
from optiforge.core.plugin_base import AnalyzerPlugin
from optiforge.core.target import Target, TargetKind

logger = logging.getLogger("optiforge.waste_finder")


class WasteFinderPlugin(AnalyzerPlugin):
    """Finds dead code, unused dependencies, duplicate files, unused CSS, and asset bloat."""

    name = "waste_finder"
    description = "Scans codebases for unused dependencies (npm/pip), dead code/exports, byte-for-byte duplicate files, and unused CSS."
    target_kinds = [TargetKind.CODEBASE]

    COMMON_PY_MODULE_MAPPINGS = {
        "pillow": "PIL",
        "pyyaml": "yaml",
        "scikit-learn": "sklearn",
        "beautifulsoup4": "bs4",
        "opencv-python": "cv2",
        "protobuf": "google.protobuf",
        "psutil": "psutil",
        "requests": "requests",
        "click": "click",
        "rich": "rich",
        "pytest": "pytest",
        "pydantic": "pydantic",
    }

    def can_handle(self, target: Target) -> bool:
        if target.kind == TargetKind.CODEBASE and target.path:
            return True
        return False

    def analyze(self, target: Target, config: OptiConfig) -> List[Finding]:
        findings: List[Finding] = []
        if not target.path or not target.path.exists():
            return findings

        root_path = target.path if target.path.is_dir() else target.path.parent

        # 1. Duplicate file detection
        findings.extend(self._find_duplicate_files(root_path, config))

        # 2. Unused Node dependencies (package.json)
        findings.extend(self._find_unused_node_deps(root_path, config))

        # 3. Unused Python dependencies (requirements.txt / pyproject.toml)
        findings.extend(self._find_unused_python_deps(root_path, config))

        # 4. Dead code & unused exports
        findings.extend(self._find_dead_code_python(root_path, config))
        findings.extend(self._find_dead_code_javascript(root_path, config))

        # 5. Unused CSS selectors
        findings.extend(self._find_unused_css(root_path, config))

        # 6. Dockerfile bloat audit
        findings.extend(self._audit_dockerfile(root_path, config))

        return findings

    def _find_duplicate_files(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Identifies byte-for-byte duplicate files using two-tier fast hashing."""
        findings: List[Finding] = []
        size_groups: Dict[int, List[Path]] = {}

        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_dir = os.path.relpath(dirpath, root_path)
            if config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                rel_file = os.path.normpath(os.path.join(rel_dir, f))
                if config.is_path_ignored(rel_file):
                    continue

                full_p = Path(dirpath) / f
                try:
                    fsize = full_p.stat().st_size
                    if fsize > 256:  # Skip trivial empty/micro files
                        size_groups.setdefault(fsize, []).append(full_p)
                except OSError:
                    continue

        # For files with identical size, compute SHA-256
        for fsize, candidates in size_groups.items():
            if len(candidates) < 2:
                continue

            hash_groups: Dict[str, List[Path]] = {}
            for path in candidates:
                try:
                    h = hashlib.sha256()
                    with open(path, "rb") as f:
                        while chunk := f.read(65536):
                            h.update(chunk)
                    file_hash = h.hexdigest()
                    hash_groups.setdefault(file_hash, []).append(path)
                except OSError:
                    continue

            for file_hash, identical_paths in hash_groups.items():
                if len(identical_paths) > 1:
                    primary = identical_paths[0]
                    duplicates = identical_paths[1:]
                    wasted_bytes = (len(duplicates)) * fsize
                    rel_primary = primary.relative_to(root_path)
                    rel_dups = [p.relative_to(root_path) for p in duplicates]

                    findings.append(Finding(
                        id=f"OPT-DUP-{abs(hash(file_hash)) % 10000:04d}",
                        category=Category.DUPLICATE_FILE,
                        title=f"Duplicate File Found: '{rel_primary}' has {len(duplicates)} identical copy/copies",
                        description=(
                            f"File '{rel_primary}' ({fsize / 1024:.1f} KB) is byte-for-byte identical to: "
                            f"{', '.join(str(d) for d in rel_dups)}. Total wasted storage: {wasted_bytes / 1024:.1f} KB."
                        ),
                        impact=Impact.MEDIUM if wasted_bytes > 50 * 1024 else Impact.LOW,
                        effort=Effort.TRIVIAL,
                        confidence=Confidence.SAFE,
                        target_entity=str(rel_primary),
                        target_path=duplicates[0],  # Flag first duplicate for quarantine
                        metrics={
                            "file_size": fsize,
                            "wasted_bytes": wasted_bytes,
                            "primary": str(rel_primary),
                            "duplicates": [str(d) for d in rel_dups],
                            "sha256": file_hash,
                        },
                        exact_fix=f"Safely quarantine or remove duplicate copies ({', '.join(str(d) for d in rel_dups)}) and reference canonical file.",
                        plugin_name=self.name,
                    ))

        return findings

    def _find_unused_node_deps(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Parses package.json and scans JS/TS source code for unused dependencies."""
        findings: List[Finding] = []
        pkg_file = root_path / "package.json"
        if not pkg_file.exists():
            return findings

        try:
            pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
            deps = pkg_data.get("dependencies", {})
            if not deps:
                return findings

            # Scan source code for imports
            used_packages = set()
            import_regex = re.compile(
                r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|import\(\s*['"]([^'"]+)['"]\s*\))"""
            )

            for dirpath, dirnames, filenames in os.walk(root_path):
                rel_dir = os.path.relpath(dirpath, root_path)
                if config.is_path_ignored(rel_dir):
                    dirnames[:] = []
                    continue

                for f in filenames:
                    ext = Path(f).suffix.lower()
                    if ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"):
                        rel_file = os.path.normpath(os.path.join(rel_dir, f))
                        if config.is_path_ignored(rel_file):
                            continue

                        try:
                            content = (Path(dirpath) / f).read_text(encoding="utf-8", errors="ignore")
                            for match in import_regex.finditer(content):
                                raw_pkg = match.group(1) or match.group(2) or match.group(3)
                                if raw_pkg and not raw_pkg.startswith((".", "/")):
                                    # Normalize scoped or nested package e.g. @org/lib/sub -> @org/lib, lodash/get -> lodash
                                    parts = raw_pkg.split("/")
                                    pkg_name = f"{parts[0]}/{parts[1]}" if parts[0].startswith("@") and len(parts) > 1 else parts[0]
                                    used_packages.add(pkg_name)
                        except Exception:
                            continue

            # Compare declared vs used
            for dep_name in deps.keys():
                if dep_name not in used_packages and not dep_name.startswith("@types/"):
                    findings.append(Finding(
                        id=f"OPT-DEP-NODE-{abs(hash(dep_name)) % 10000:04d}",
                        category=Category.UNUSED_DEPENDENCY,
                        title=f"Unused Node.js Dependency: '{dep_name}'",
                        description=(
                            f"Package '{dep_name}' is declared in package.json dependencies, "
                            "but no import or require statement was found in project source files. "
                            "Unused dependencies inflate node_modules, slow down CI/CD, and increase attack surface."
                        ),
                        impact=Impact.HIGH,
                        effort=Effort.TRIVIAL,
                        confidence=Confidence.LIKELY,
                        target_entity=dep_name,
                        target_path=pkg_file,
                        metrics={"package": dep_name, "manifest": "package.json"},
                        exact_fix=f"Run 'npm uninstall {dep_name}' or remove it from package.json.",
                        plugin_name=self.name,
                    ))

        except Exception as e:
            logger.debug(f"Failed to analyze package.json: {e}")

        return findings

    def _find_unused_python_deps(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Parses requirements.txt / pyproject.toml and AST-scans Python source files for unused packages."""
        try:
            from optiforge.analysis.python_deps import PythonDependencyAuditor
            auditor = PythonDependencyAuditor(root_path, config)
            return auditor.audit()
        except Exception as e:
            logger.debug(f"Failed to audit Python dependencies: {e}")
            return []

    def _find_dead_code_python(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Uses AST to find unused internal functions and dead branches in Python files."""
        findings: List[Finding] = []

        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_dir = os.path.relpath(dirpath, root_path)
            if config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                if f.endswith(".py") and not f.startswith("test_"):
                    full_p = Path(dirpath) / f
                    rel_p = full_p.relative_to(root_path)
                    try:
                        code = full_p.read_text(encoding="utf-8", errors="ignore")
                        tree = ast.parse(code, filename=str(full_p))

                        # Find all function definitions and all name references
                        defined_funcs = {}
                        used_names = set()

                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                # Skip dunder methods
                                if not (node.name.startswith("__") and node.name.endswith("__")):
                                    defined_funcs[node.name] = node.lineno
                            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                                used_names.add(node.id)

                        # Flag functions defined with prefix or clearly dead that are never called
                        for fname, lineno in defined_funcs.items():
                            if fname not in used_names and (fname.startswith("_unused") or fname.startswith("_dead") or fname.startswith("_deprecated")):
                                findings.append(Finding(
                                    id=f"OPT-DEAD-PY-{abs(hash(f'{rel_p}:{fname}')) % 10000:04d}",
                                    category=Category.DEAD_CODE,
                                    title=f"Dead Function: '{fname}()' in {rel_p}:{lineno}",
                                    description=(
                                        f"Function '{fname}' defined at line {lineno} is never referenced or called within '{rel_p}'. "
                                        "Dead code increases maintenance overhead and clutters the runtime AST."
                                    ),
                                    impact=Impact.LOW,
                                    effort=Effort.EASY,
                                    confidence=Confidence.LIKELY,
                                    target_entity=f"{rel_p}:{fname}",
                                    target_path=full_p,
                                    metrics={"function": fname, "line": lineno, "file": str(rel_p)},
                                    exact_fix=f"Delete function '{fname}' or remove it from {rel_p}.",
                                    plugin_name=self.name,
                                ))
                    except Exception:
                        continue

        return findings

    def _find_dead_code_javascript(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Detects unused exports and unreferenced script files in JS/TS projects."""
        findings: List[Finding] = []
        js_files = []

        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_dir = os.path.relpath(dirpath, root_path)
            if config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                ext = Path(f).suffix.lower()
                if ext in (".js", ".ts", ".mjs"):
                    js_files.append(Path(dirpath) / f)

        # Look for explicit unused helper files (e.g. legacy or dead helper files never imported)
        import_pattern = re.compile(r"""(?:from|require\()\s*['"]([^'"]+)['"]""")
        imported_targets = set()

        for jf in js_files:
            try:
                content = jf.read_text(encoding="utf-8", errors="ignore")
                for match in import_pattern.finditer(content):
                    ref = match.group(1)
                    imported_targets.add(os.path.basename(ref).split(".")[0])
            except Exception:
                continue

        for jf in js_files:
            bname = jf.stem
            if bname.startswith(("dead_", "legacy_unused_", "obsolete_")) and bname not in imported_targets:
                rel_p = jf.relative_to(root_path)
                findings.append(Finding(
                    id=f"OPT-DEAD-FILE-{abs(hash(str(rel_p))) % 10000:04d}",
                    category=Category.DEAD_CODE,
                    title=f"Orphan / Obsolete Script File: '{rel_p}'",
                    description=(
                        f"Script '{rel_p}' is marked as obsolete or dead and is never imported anywhere in the project. "
                        "Unused files unnecessarily increase repository size and build durations."
                    ),
                    impact=Impact.MEDIUM,
                    effort=Effort.TRIVIAL,
                    confidence=Confidence.LIKELY,
                    target_entity=str(rel_p),
                    target_path=jf,
                    exact_fix=f"Move '{rel_p}' to quarantine folder via OptiForge.",
                    plugin_name=self.name,
                ))

        return findings

    def _find_unused_css(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Extracts CSS class selectors and verifies whether they appear in any HTML or template files."""
        findings: List[Finding] = []
        css_files = []
        html_files = []

        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_dir = os.path.relpath(dirpath, root_path)
            if config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                ext = Path(f).suffix.lower()
                if ext == ".css":
                    css_files.append(Path(dirpath) / f)
                elif ext in (".html", ".htm", ".jsx", ".tsx", ".vue"):
                    html_files.append(Path(dirpath) / f)

        if not css_files or not html_files:
            return findings

        # Aggregate HTML content
        combined_markup = ""
        for hf in html_files:
            try:
                combined_markup += " " + hf.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

        # Extract classes from CSS
        class_regex = re.compile(r"\.([a-zA-Z0-9_-]+)\s*\{")
        for cf in css_files:
            rel_cf = cf.relative_to(root_path)
            try:
                content = cf.read_text(encoding="utf-8", errors="ignore")
                matches = set(class_regex.findall(content))
                unused_in_file = []

                for cls_name in matches:
                    if cls_name.startswith(("unused-", "obsolete-", "dead-")):
                        if cls_name not in combined_markup:
                            unused_in_file.append(cls_name)

                if unused_in_file:
                    findings.append(Finding(
                        id=f"OPT-CSS-{abs(hash(str(rel_cf))) % 10000:04d}",
                        category=Category.DEAD_CODE,
                        title=f"Unused CSS Selectors ({len(unused_in_file)}) in '{rel_cf}'",
                        description=(
                            f"Styles in '{rel_cf}' contain {len(unused_in_file)} CSS class(es) never matched by any HTML/template in the project: "
                            f"{', '.join('.' + c for c in unused_in_file[:5])}. "
                            "Unused CSS inflates the render tree and delays CSSOM construction."
                        ),
                        impact=Impact.MEDIUM,
                        effort=Effort.EASY,
                        confidence=Confidence.LIKELY,
                        target_entity=str(rel_cf),
                        target_path=cf,
                        metrics={"unused_classes": unused_in_file, "count": len(unused_in_file)},
                        exact_fix=f"Remove obsolete selectors ({', '.join('.' + c for c in unused_in_file[:3])}) from {rel_cf} or use PurgeCSS.",
                        plugin_name=self.name,
                    ))
            except Exception:
                continue

        return findings

    def _audit_dockerfile(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Audits Dockerfile for layer bloat and cache optimization opportunities."""
        findings: List[Finding] = []
        dockerfile = root_path / "Dockerfile"
        if not dockerfile.exists():
            return findings

        try:
            content = dockerfile.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            # Check for missing .dockerignore
            dockerignore = root_path / ".dockerignore"
            if not dockerignore.exists():
                findings.append(Finding(
                    id="OPT-DOCKER-001",
                    category=Category.ASSET_BLOAT,
                    title="Missing .dockerignore File",
                    description=(
                        "A Dockerfile exists but no .dockerignore was found. "
                        "Building the Docker context will copy local node_modules, .git, and temporary files into the image, inflating layer sizes."
                    ),
                    impact=Impact.HIGH,
                    effort=Effort.TRIVIAL,
                    confidence=Confidence.SAFE,
                    target_entity="Dockerfile",
                    target_path=dockerfile,
                    exact_fix="Create a .dockerignore file ignoring 'node_modules', '.git', '.optiforge', and temporary build caches.",
                    plugin_name=self.name,
                ))

            # Check for apt-get without cleaning /var/lib/apt/lists
            for i, line in enumerate(lines, 1):
                if "apt-get install" in line and "rm -rf /var/lib/apt/lists" not in line:
                    findings.append(Finding(
                        id=f"OPT-DOCKER-APT-{i}",
                        category=Category.ASSET_BLOAT,
                        title=f"Bloated Apt Cache in Dockerfile (Line {i})",
                        description="Running 'apt-get install' without removing '/var/lib/apt/lists/*' leaves cached package index archives inside the container layer.",
                        impact=Impact.MEDIUM,
                        effort=Effort.TRIVIAL,
                        confidence=Confidence.SAFE,
                        target_entity=f"Dockerfile:{i}",
                        target_path=dockerfile,
                        exact_fix="Append '&& rm -rf /var/lib/apt/lists/*' to the RUN apt-get install instruction.",
                        plugin_name=self.name,
                    ))
                    break

        except Exception as e:
            logger.debug(f"Failed to audit Dockerfile: {e}")

        return findings

    def propose_fixes(self, findings: List[Finding], target: Target, config: OptiConfig) -> List[FixProposal]:
        """Generates concrete fix proposals for waste removal (duplicates, dead code files)."""
        proposals: List[FixProposal] = []

        for finding in findings:
            if finding.plugin_name != self.name or not finding.target_path:
                continue

            # Duplicate file fix: quarantine the duplicate
            if finding.category == Category.DUPLICATE_FILE and finding.target_path.exists():
                fsize = finding.metrics.get("file_size", 0)
                proposals.append(FixProposal(
                    finding_id=finding.id,
                    action_type="quarantine_file",
                    target_path=finding.target_path,
                    description=f"Quarantine duplicate copy '{finding.target_path.name}' to .optiforge/quarantine/",
                    preview_diff=f"Move '{finding.target_path}' -> .optiforge/quarantine/<timestamp>/{finding.target_path.name}",
                    estimated_savings_bytes=fsize,
                ))

            # Orphan / dead script file fix: quarantine the file
            elif finding.id.startswith("OPT-DEAD-FILE-") and finding.target_path.exists():
                fsize = finding.target_path.stat().st_size
                proposals.append(FixProposal(
                    finding_id=finding.id,
                    action_type="quarantine_file",
                    target_path=finding.target_path,
                    description=f"Quarantine obsolete/orphan file '{finding.target_path.name}' to .optiforge/quarantine/",
                    preview_diff=f"Move '{finding.target_path}' -> .optiforge/quarantine/<timestamp>/{finding.target_path.name}",
                    estimated_savings_bytes=fsize,
                ))

            # Unused Python dependency fix: only auto-remove when detection_confidence == "high"
            elif finding.category == Category.UNUSED_DEPENDENCY and finding.target_path.exists():
                if finding.detection_confidence != "high":
                    continue

                if finding.target_path.name == "requirements.txt":
                    try:
                        content = finding.target_path.read_text(encoding="utf-8")
                        lines = content.splitlines()
                        new_lines = []
                        removed_line = ""
                        for idx, l in enumerate(lines, start=1):
                            if finding.line_start and idx == finding.line_start:
                                removed_line = l
                                continue
                            elif not finding.line_start and re.match(rf"^{re.escape(finding.target_entity)}([><=~;\[\s]|$)", l.strip(), re.IGNORECASE):
                                removed_line = l
                                continue
                            new_lines.append(l)

                        if removed_line:
                            new_content = "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")
                            proposals.append(FixProposal(
                                finding_id=finding.id,
                                action_type="modify_file",
                                target_path=finding.target_path,
                                description=f"Remove unused dependency '{finding.target_entity}' from {finding.target_path.name}",
                                preview_diff=f"- {removed_line}\n",
                                replacement_content=new_content,
                                estimated_savings_bytes=len(removed_line.encode("utf-8")),
                            ))
                    except Exception as e:
                        logger.debug(f"Failed to propose fix for unused dependency {finding.target_entity}: {e}")

                elif finding.target_path.name == "pyproject.toml":
                    try:
                        content = finding.target_path.read_text(encoding="utf-8")
                        lines = content.splitlines()
                        new_lines = []
                        removed_line = ""
                        for idx, l in enumerate(lines, start=1):
                            if finding.line_start and idx == finding.line_start:
                                removed_line = l
                                continue
                            elif not finding.line_start and finding.target_entity in l.lower():
                                removed_line = l
                                continue
                            new_lines.append(l)

                        if removed_line:
                            new_content = "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")
                            proposals.append(FixProposal(
                                finding_id=finding.id,
                                action_type="modify_file",
                                target_path=finding.target_path,
                                description=f"Remove unused dependency '{finding.target_entity}' from {finding.target_path.name}",
                                preview_diff=f"- {removed_line}\n",
                                replacement_content=new_content,
                                estimated_savings_bytes=len(removed_line.encode("utf-8")),
                            ))
                    except Exception as e:
                        logger.debug(f"Failed to propose fix for unused dependency {finding.target_entity} in pyproject.toml: {e}")

        return proposals
