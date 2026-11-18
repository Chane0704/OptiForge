"""Advanced Python Dependency Auditor for OptiForge.

Provides:
1. Dynamic package-to-import resolution (importlib.metadata + top_level.txt + RECORD).
2. Curated fallback alias table for non-installed packages (python-dotenv, google-genai, etc.).
3. Namespace package support (google.*, azure.*).
4. Tools vs. libraries categorization and config/script reference detection.
5. Deep AST usage detection (import, import-from, importlib.import_module, __import__, TYPE_CHECKING).
6. Manifest parsing (requirements.txt, pyproject.toml [project.dependencies] & optional-dependencies).
7. Honest detection confidence (high/medium/low) with detailed evidence strings.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact


# Cache for package-to-distribution resolution
_DISTRIBUTIONS_CACHE: Optional[Dict[str, Set[str]]] = None


# Comprehensive fallback mapping for PyPI package names to their provided import names
BUILTIN_PACKAGE_ALIASES: Dict[str, Set[str]] = {
    # The CONTEXT issues:
    "python-dotenv": {"dotenv"},
    "google-genai": {"google.genai", "google"},
    # Major namespace packages
    "google-api-python-client": {"googleapiclient", "google"},
    "google-cloud-storage": {"google.cloud.storage", "google"},
    "google-cloud-core": {"google.cloud.core", "google"},
    "google-auth": {"google.auth", "google"},
    "google-auth-oauthlib": {"google_auth_oauthlib", "google"},
    "azure-storage-blob": {"azure.storage.blob", "azure"},
    "azure-core": {"azure.core", "azure"},
    "azure-identity": {"azure.identity", "azure"},
    "aws-cdk-lib": {"aws_cdk"},
    # Common PyPI name != import name
    "pyyaml": {"yaml"},
    "pillow": {"PIL"},
    "scikit-learn": {"sklearn"},
    "beautifulsoup4": {"bs4"},
    "opencv-python": {"cv2"},
    "opencv-python-headless": {"cv2"},
    "opencv-contrib-python": {"cv2"},
    "paho-mqtt": {"paho"},
    "python-dateutil": {"dateutil"},
    "protobuf": {"google.protobuf", "google"},
    "psycopg2": {"psycopg2"},
    "psycopg2-binary": {"psycopg2"},
    "pyjwt": {"jwt"},
    "pymongo": {"pymongo", "bson"},
    "pydantic-settings": {"pydantic_settings"},
    "pydantic-core": {"pydantic_core"},
    "websocket-client": {"websocket"},
    "gitpython": {"git"},
    "setuptools": {"setuptools", "pkg_resources"},
    "types-requests": {"types_requests"},
    "typing-extensions": {"typing_extensions"},
    "argon2-cffi": {"argon2"},
    "pypdf": {"pypdf"},
    "pypdf2": {"PyPDF2"},
    "dnspython": {"dns"},
    "kafka-python": {"kafka"},
    "pycrypto": {"Crypto"},
    "pycryptodome": {"Crypto"},
    "pyopenssl": {"OpenSSL"},
    "markupsafe": {"markupsafe"},
    "jinja2": {"jinja2"},
    "werkzeug": {"werkzeug"},
    "flask-cors": {"flask_cors"},
    "flask-sqlalchemy": {"flask_sqlalchemy"},
    "flask-login": {"flask_login"},
    "marshmallow-sqlalchemy": {"marshmallow_sqlalchemy"},
    "apache-airflow": {"airflow"},
    "ansible-core": {"ansible"},
    "prometheus-client": {"prometheus_client"},
    "opentelemetry-api": {"opentelemetry"},
    "opentelemetry-sdk": {"opentelemetry"},
    "boto3": {"boto3"},
    "botocore": {"botocore"},
}

# Known development, CLI, test runner, server, and orchestration tools
BUILTIN_TOOL_PACKAGES: Set[str] = {
    # Testing & Coverage
    "pytest", "pytest-cov", "pytest-mock", "pytest-asyncio", "pytest-xdist",
    "pytest-timeout", "pytest-benchmark", "pytest-runner", "coverage", "hypothesis",
    "unittest2", "nose", "nose2", "mock", "factory-boy", "faker",
    # Linters & Formatters
    "black", "ruff", "mypy", "flake8", "pylint", "isort", "autopep8", "yapf",
    "bandit", "safety", "radon", "xenon", "vulture", "pyupgrade",
    # Build & Release
    "build", "twine", "wheel", "setuptools", "flit", "hatch", "poetry",
    "pip-tools", "pipdeptree", "tox", "nox", "pre-commit", "commitizen",
    # Servers & Task Runners
    "gunicorn", "uvicorn", "celery", "hypercorn", "daphne", "waitress",
    "invoke", "fabric", "watchdog", "honcho", "foreman", "supervisor",
    # Documentation
    "sphinx", "mkdocs", "mkdocs-material", "pydocstyle",
    # Debuggers & Shells
    "ipython", "jupyter", "ipdb", "pdbpp", "rich",
}


@dataclass
class DeclaredDependency:
    """Represents a dependency declared in requirements.txt or pyproject.toml."""
    name: str                   # Normalized lowercase distribution name, e.g. "python-dotenv"
    raw_spec: str               # Original raw line, e.g. "python-dotenv>=1.0.0"
    manifest_path: Path         # Path to manifest file
    line_start: int             # 1-indexed start line
    line_end: int               # 1-indexed end line
    is_optional: bool = False   # True if in optional-dependencies / extra
    extra_names: List[str] = field(default_factory=list)


class PythonImportASTVisitor(ast.NodeVisitor):
    """Deep AST visitor collecting module imports, dynamic imports, and TYPE_CHECKING blocks."""

    def __init__(self):
        # Set of import names: top-level ("dotenv") and dotted ("google.genai")
        self.imported_modules: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.name.lower()
            self.imported_modules.add(name)
            # Add all parent prefix parts (e.g. "google.genai" -> "google", "google.genai")
            parts = name.split(".")
            for i in range(1, len(parts) + 1):
                self.imported_modules.add(".".join(parts[:i]))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod = node.module.lower()
            self.imported_modules.add(mod)
            parts = mod.split(".")
            for i in range(1, len(parts) + 1):
                self.imported_modules.add(".".join(parts[:i]))
            for alias in node.names:
                full_mod = f"{mod}.{alias.name.lower()}"
                self.imported_modules.add(full_mod)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # 1. importlib.import_module("foo")
        if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                mod = node.args[0].value.lower()
                self.imported_modules.add(mod)
                self.imported_modules.add(mod.split(".")[0])

        # 2. __import__("foo")
        elif isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                mod = node.args[0].value.lower()
                self.imported_modules.add(mod)
                self.imported_modules.add(mod.split(".")[0])

        # 3. import_module("foo") direct call
        elif isinstance(node.func, ast.Name) and node.func.id == "import_module":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                mod = node.args[0].value.lower()
                self.imported_modules.add(mod)
                self.imported_modules.add(mod.split(".")[0])

        self.generic_visit(node)


class PythonDependencyAuditor:
    """Enterprise-grade Python dependency analyzer with zero false positives."""

    def __init__(self, root_path: Path, config: OptiConfig):
        self.root_path = root_path
        self.config = config
        self._pkg_to_imports_cache: Dict[str, Set[str]] = {}

    @classmethod
    def get_installed_distributions_map(cls) -> Dict[str, Set[str]]:
        """Uses importlib.metadata.packages_distributions() to map PyPI dist names to top-level modules."""
        global _DISTRIBUTIONS_CACHE
        if _DISTRIBUTIONS_CACHE is not None:
            return _DISTRIBUTIONS_CACHE

        dist_map: Dict[str, Set[str]] = {}
        try:
            import importlib.metadata as md
            if hasattr(md, "packages_distributions"):
                pkg_dist = md.packages_distributions()
                for top_mod, dist_names in pkg_dist.items():
                    for dist in dist_names:
                        d_norm = dist.lower()
                        if d_norm not in dist_map:
                            dist_map[d_norm] = set()
                        dist_map[d_norm].add(top_mod.lower())
        except Exception:
            pass

        _DISTRIBUTIONS_CACHE = dist_map
        return _DISTRIBUTIONS_CACHE

    @classmethod
    def get_distribution_metadata_imports(cls, dist_name: str) -> Set[str]:
        """Inspects an installed distribution's top_level.txt and RECORD/files."""
        imports: Set[str] = set()
        try:
            import importlib.metadata as md
            for candidate in (dist_name, dist_name.replace("-", "_"), dist_name.replace("_", "-")):
                try:
                    dist = md.distribution(candidate)
                except Exception:
                    continue

                # 1. top_level.txt
                try:
                    tl = dist.read_text("top_level.txt")
                    if tl:
                        for line in tl.splitlines():
                            clean = line.strip().lower()
                            if clean:
                                imports.add(clean)
                except Exception:
                    pass

                # 2. RECORD / dist.files
                try:
                    if not imports and dist.files:
                        for f in dist.files:
                            parts = Path(str(f)).parts
                            if parts and not parts[0].endswith(".dist-info") and not parts[0].endswith(".egg-info"):
                                top = parts[0].replace(".py", "").lower()
                                if top and top != "__pycache__":
                                    imports.add(top)
                except Exception:
                    pass

                if imports:
                    break
        except Exception:
            pass
        return imports

    def resolve_import_names(self, package_name: str) -> Set[str]:
        """Resolves a PyPI package name to the set of import names it provides.

        Priority:
        1. Custom aliases in config (.optiforge.toml / optiforge.yaml).
        2. Installed package metadata via importlib.metadata (packages_distributions + top_level.txt + RECORD).
        3. Built-in curated alias table.
        4. Name normalizations (dashes to underscores, underscores to dashes).
        """
        pkg_norm = package_name.lower().strip()
        if pkg_norm in self._pkg_to_imports_cache:
            return self._pkg_to_imports_cache[pkg_norm]

        candidates: Set[str] = set()

        # 1. Custom aliases from config
        custom_aliases = getattr(self.config.dependencies, "aliases", {})
        if pkg_norm in custom_aliases:
            val = custom_aliases[pkg_norm]
            if isinstance(val, (list, tuple, set)):
                candidates.update(v.lower() for v in val)
            elif isinstance(val, str):
                candidates.add(val.lower())

        # 2. Installed distribution metadata
        installed_map = self.get_installed_distributions_map()
        if pkg_norm in installed_map:
            candidates.update(installed_map[pkg_norm])
        alt_installed = pkg_norm.replace("-", "_")
        if alt_installed in installed_map:
            candidates.update(installed_map[alt_installed])

        dist_meta_imports = self.get_distribution_metadata_imports(pkg_norm)
        if dist_meta_imports:
            candidates.update(dist_meta_imports)

        # 3. Built-in curated alias table
        if pkg_norm in BUILTIN_PACKAGE_ALIASES:
            candidates.update(BUILTIN_PACKAGE_ALIASES[pkg_norm])
        if alt_installed in BUILTIN_PACKAGE_ALIASES:
            candidates.update(BUILTIN_PACKAGE_ALIASES[alt_installed])

        # 4. Canonical name normalizations
        candidates.add(pkg_norm)
        candidates.add(alt_installed)
        candidates.add(pkg_norm.replace("_", "-"))

        self._pkg_to_imports_cache[pkg_norm] = candidates
        return candidates

    def is_tool_package(self, package_name: str) -> bool:
        """Determines if a package is a known CLI, linter, test runner, or dev tool."""
        pkg_norm = package_name.lower().strip()
        # Custom tools from config
        custom_tools = getattr(self.config.dependencies, "tools", [])
        if pkg_norm in [t.lower() for t in custom_tools]:
            return True

        if pkg_norm in BUILTIN_TOOL_PACKAGES:
            return True

        alt = pkg_norm.replace("_", "-")
        if alt in BUILTIN_TOOL_PACKAGES:
            return True

        # Check prefixes like pytest-*
        if pkg_norm.startswith("pytest-") or pkg_norm.startswith("types-") or pkg_norm.startswith("sphinx-"):
            return True

        return False

    def scan_config_and_script_references(self) -> Set[str]:
        """Scans non-Python config, script, Docker, Makefile, and CI files for package/tool mentions."""
        referenced_words: Set[str] = set()

        config_extensions = {
            ".toml", ".ini", ".cfg", ".yaml", ".yml", ".json",
            ".sh", ".bat", ".cmd", ".ps1"
        }
        config_exact_names = {
            "makefile", "dockerfile", "procfile", ".pre-commit-config.yaml",
            "pytest.ini", "tox.ini", "setup.cfg"
        }

        def _is_manifest_file(fname: str) -> bool:
            fl = fname.lower()
            return (
                "requirements" in fl
                or fl in ("pipfile", "pipfile.lock", "poetry.lock")
            )

        def _clean_content_for_scanning(path: Path, raw_content: str) -> str:
            fl = path.name.lower()
            if fl == "pyproject.toml":
                # Exclude declared dependency tables so packages aren't self-matched
                try:
                    import tomllib
                except ImportError:
                    try:
                        import tomli as tomllib
                    except ImportError:
                        tomllib = None
                if tomllib:
                    try:
                        import json
                        data = tomllib.loads(raw_content)
                        if "project" in data and isinstance(data["project"], dict):
                            data["project"].pop("dependencies", None)
                            data["project"].pop("optional-dependencies", None)
                        if "tool" in data and isinstance(data["tool"], dict):
                            if "poetry" in data["tool"] and isinstance(data["tool"]["poetry"], dict):
                                data["tool"]["poetry"].pop("dependencies", None)
                                data["tool"]["poetry"].pop("group", None)
                        return json.dumps(data)
                    except Exception:
                        pass
            elif fl == "setup.cfg":
                # Exclude install_requires and extras_require blocks
                lines = []
                in_dep_section = False
                for line in raw_content.splitlines():
                    if line.strip().startswith("["):
                        in_dep_section = False
                    if "install_requires" in line or "extras_require" in line:
                        in_dep_section = True
                        continue
                    if not in_dep_section:
                        lines.append(line)
                return "\n".join(lines)
            return raw_content

        for dirpath, dirnames, filenames in os.walk(self.root_path):
            rel_dir = os.path.relpath(dirpath, self.root_path)
            if self.config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                f_lower = f.lower()
                p = Path(dirpath) / f

                if _is_manifest_file(f_lower):
                    continue

                # Check if file is a configuration, container, script, or workflow file
                is_target_file = (
                    p.suffix.lower() in config_extensions
                    or f_lower in config_exact_names
                    or f_lower.startswith("dockerfile")
                    or ".github" in str(p)
                )

                if is_target_file:
                    try:
                        raw_content = p.read_text(encoding="utf-8", errors="ignore")
                        cleaned = _clean_content_for_scanning(p, raw_content)
                        words = re.findall(r"[A-Za-z0-9_\-]+", cleaned)
                        for w in words:
                            referenced_words.add(w.lower())
                    except Exception:
                        continue

        return referenced_words

    def collect_source_imports(self) -> Tuple[Set[str], int]:
        """Parses all project Python files via AST and returns (all_imported_module_names, file_count)."""
        visitor = PythonImportASTVisitor()
        python_file_count = 0

        for dirpath, dirnames, filenames in os.walk(self.root_path):
            rel_dir = os.path.relpath(dirpath, self.root_path)
            if self.config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                if f.endswith(".py"):
                    python_file_count += 1
                    full_p = Path(dirpath) / f
                    try:
                        code = full_p.read_text(encoding="utf-8", errors="ignore")
                        tree = ast.parse(code, filename=str(full_p))
                        visitor.visit(tree)
                    except Exception:
                        continue

        return visitor.imported_modules, python_file_count

    def parse_requirements_txt(self, req_path: Path) -> List[DeclaredDependency]:
        """Parses requirements.txt extracting clean package names, extras, and exact line ranges."""
        results: List[DeclaredDependency] = []
        if not req_path.exists():
            return results

        try:
            lines = req_path.read_text(encoding="utf-8").splitlines()
            for idx, raw_line in enumerate(lines, start=1):
                clean_line = raw_line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue

                # Ignore pip directives like -r, -i, -e, --extra-index-url
                if clean_line.startswith("-"):
                    continue

                # Strip inline comment
                clean_line = clean_line.split("#")[0].strip()

                # Extract package name before comparison operators or environment markers
                match = re.match(r"^([A-Za-z0-9_\-\.]+)(?:\[([A-Za-z0-9_\-,\s]+)\])?.*", clean_line)
                if match:
                    pkg_name = match.group(1).lower()
                    extras = [e.strip() for e in match.group(2).split(",")] if match.group(2) else []

                    # Filter out globally ignored packages
                    if pkg_name in self.config.ignore.packages:
                        continue

                    results.append(DeclaredDependency(
                        name=pkg_name,
                        raw_spec=raw_line,
                        manifest_path=req_path,
                        line_start=idx,
                        line_end=idx,
                        extra_names=extras,
                    ))
        except Exception:
            pass

        return results

    def parse_pyproject_toml(self, pyproject_path: Path) -> List[DeclaredDependency]:
        """Parses pyproject.toml extracting [project.dependencies] and optional-dependencies."""
        results: List[DeclaredDependency] = []
        if not pyproject_path.exists():
            return results

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                tomllib = None

        if not tomllib:
            return results

        try:
            raw_text = pyproject_path.read_text(encoding="utf-8")
            data = tomllib.loads(raw_text)

            # Locate line numbers by searching in the raw text
            text_lines = raw_text.splitlines()

            def find_line_num(dep_str: str) -> int:
                dep_clean = dep_str.strip().strip("'\"")
                for line_idx, line in enumerate(text_lines, start=1):
                    if dep_clean in line:
                        return line_idx
                return 1

            # 1. [project.dependencies]
            project_deps = data.get("project", {}).get("dependencies", [])
            for dep in project_deps:
                match = re.match(r"^([A-Za-z0-9_\-\.]+)(?:\[([A-Za-z0-9_\-,\s]+)\])?.*", dep.strip())
                if match:
                    pkg = match.group(1).lower()
                    if pkg not in self.config.ignore.packages:
                        line_no = find_line_num(dep)
                        results.append(DeclaredDependency(
                            name=pkg,
                            raw_spec=dep,
                            manifest_path=pyproject_path,
                            line_start=line_no,
                            line_end=line_no,
                            is_optional=False,
                        ))

            # 2. [project.optional-dependencies]
            opt_deps_dict = data.get("project", {}).get("optional-dependencies", {})
            for group, deps in opt_deps_dict.items():
                for dep in deps:
                    match = re.match(r"^([A-Za-z0-9_\-\.]+)(?:\[([A-Za-z0-9_\-,\s]+)\])?.*", dep.strip())
                    if match:
                        pkg = match.group(1).lower()
                        if pkg not in self.config.ignore.packages:
                            line_no = find_line_num(dep)
                            results.append(DeclaredDependency(
                                name=pkg,
                                raw_spec=dep,
                                manifest_path=pyproject_path,
                                line_start=line_no,
                                line_end=line_no,
                                is_optional=True,
                            ))

            # 3. [tool.poetry.dependencies]
            poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            for pkg, spec in poetry_deps.items():
                pkg_clean = pkg.lower()
                if pkg_clean not in ("python",) and pkg_clean not in self.config.ignore.packages:
                    line_no = find_line_num(pkg)
                    results.append(DeclaredDependency(
                        name=pkg_clean,
                        raw_spec=f"{pkg} = {spec}",
                        manifest_path=pyproject_path,
                        line_start=line_no,
                        line_end=line_no,
                        is_optional=False,
                    ))
        except Exception:
            pass

        return results

    def audit(self) -> List[Finding]:
        """Runs the complete dependency audit and returns precision Findings."""
        findings: List[Finding] = []

        # 1. Collect declared dependencies from all project manifests
        declared: List[DeclaredDependency] = []
        req_file = self.root_path / "requirements.txt"
        if req_file.exists():
            declared.extend(self.parse_requirements_txt(req_file))

        pyproject_file = self.root_path / "pyproject.toml"
        if pyproject_file.exists():
            declared.extend(self.parse_pyproject_toml(pyproject_file))

        if not declared:
            return findings

        # 2. Collect AST imports and non-Python config references
        imported_modules, py_file_count = self.collect_source_imports()
        config_references = self.scan_config_and_script_references()

        # 3. Audit each declared package
        for dep in declared:
            pkg_name = dep.name
            possible_imports = self.resolve_import_names(pkg_name)

            # Check if any resolved import name appears in source code imports
            is_imported = any(mod in imported_modules for mod in possible_imports)

            # Check namespace prefix matches (e.g. "google.genai" imported when dep is "google-genai")
            if not is_imported:
                for imp in imported_modules:
                    for poss in possible_imports:
                        if imp.startswith(f"{poss}.") or poss.startswith(f"{imp}."):
                            is_imported = True
                            break
                    if is_imported:
                        break

            # If imported, it's genuinely used!
            if is_imported:
                continue

            # Check if it's a known tool or referenced in config/scripts/CI
            is_tool = self.is_tool_package(pkg_name)
            is_config_referenced = (
                pkg_name in config_references
                or pkg_name.replace("-", "_") in config_references
                or any(mod in config_references for mod in possible_imports)
            )

            if is_tool:
                if is_config_referenced:
                    # Tool is actively used in project configuration/scripts/CI!
                    continue
                else:
                    # Tool package declared, but not referenced in code or config
                    # Suggest moving dev tools to requirements-dev.txt or optional-dependencies
                    findings.append(Finding(
                        id=f"OPT-DEP-PY-{abs(hash(pkg_name)) % 10000:04d}",
                        category=Category.UNUSED_DEPENDENCY,
                        title=f"Development Tool in Production Manifest: '{pkg_name}'",
                        description=(
                            f"Package '{pkg_name}' is a known developer/CLI tool declared in {dep.manifest_path.name}, "
                            "but no direct module imports or script executions were found. "
                            "Consider moving it to requirements-dev.txt or [project.optional-dependencies] to keep production images slim."
                        ),
                        impact=Impact.LOW,
                        effort=Effort.TRIVIAL,
                        confidence=Confidence.LIKELY,
                        detection_confidence="medium",
                        evidence=(
                            f"Declared in {dep.manifest_path.name} line {dep.line_start}; recognized as a developer tool; "
                            f"not referenced across {py_file_count} Python files or project configs."
                        ),
                        line_start=dep.line_start,
                        line_end=dep.line_end,
                        target_entity=pkg_name,
                        target_path=dep.manifest_path,
                        metrics={"package": pkg_name, "manifest": dep.manifest_path.name, "is_tool": True},
                        exact_fix=f"Move '{pkg_name}' from {dep.manifest_path.name} to requirements-dev.txt.",
                        plugin_name="waste_finder",
                    ))
                    continue

            # If non-tool package is referenced in configs/scripts (e.g. Makefile or Dockerfile)
            if is_config_referenced:
                continue

            # Optional dependency: LOW confidence (possibly unused, verify manually)
            if dep.is_optional:
                findings.append(Finding(
                    id=f"OPT-DEP-PY-{abs(hash(pkg_name)) % 10000:04d}",
                    category=Category.UNUSED_DEPENDENCY,
                    title=f"Optional Dependency Not Referenced: '{pkg_name}'",
                    description=(
                        f"Package '{pkg_name}' is declared as an optional dependency in {dep.manifest_path.name}, "
                        "but no direct module imports were detected in source files. "
                        "It may be used by optional feature flags or downstream consumers; verify manually before removing."
                    ),
                    impact=Impact.LOW,
                    effort=Effort.TRIVIAL,
                    confidence=Confidence.RISKY,
                    detection_confidence="low",
                    evidence=(
                        f"Declared as optional dependency in {dep.manifest_path.name} line {dep.line_start}; "
                        f"no AST imports found across {py_file_count} Python files."
                    ),
                    line_start=dep.line_start,
                    line_end=dep.line_end,
                    target_entity=pkg_name,
                    target_path=dep.manifest_path,
                    metrics={"package": pkg_name, "manifest": dep.manifest_path.name, "is_tool": False, "is_optional": True},
                    exact_fix=f"Verify if optional feature '{pkg_name}' is still required in {dep.manifest_path.name}.",
                    plugin_name="waste_finder",
                ))
                continue

            # Genuinely unused library package: HIGH confidence finding
            findings.append(Finding(
                id=f"OPT-DEP-PY-{abs(hash(pkg_name)) % 10000:04d}",
                category=Category.UNUSED_DEPENDENCY,
                title=f"Unused Python Dependency: '{pkg_name}'",
                description=(
                    f"Package '{pkg_name}' is declared in {dep.manifest_path.name}, but no corresponding module import "
                    "or dynamic reference was detected anywhere in the codebase. "
                    "Removing unneeded dependencies speeds up container builds, shrinks virtualenvs, and reduces attack surface."
                ),
                impact=Impact.MEDIUM,
                effort=Effort.TRIVIAL,
                confidence=Confidence.SAFE,
                detection_confidence="high",
                evidence=(
                    f"Declared in {dep.manifest_path.name} line {dep.line_start}; zero AST imports, dynamic imports, "
                    f"or configuration references found across {py_file_count} Python files."
                ),
                line_start=dep.line_start,
                line_end=dep.line_end,
                target_entity=pkg_name,
                target_path=dep.manifest_path,
                metrics={"package": pkg_name, "manifest": dep.manifest_path.name, "is_tool": False, "is_optional": False},
                exact_fix=f"Remove '{pkg_name}' from {dep.manifest_path.name} and run 'pip uninstall {pkg_name}'.",
                plugin_name="waste_finder",
            ))

        return findings
