"""Runtime Smoothness and Configuration Tuner Plugin for OptiForge."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import psutil

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact
from optiforge.core.plugin_base import AnalyzerPlugin
from optiforge.core.target import Target, TargetKind

logger = logging.getLogger("optiforge.runtime_tuner")


class RuntimeTunerPlugin(AnalyzerPlugin):
    """Analyzes runtime configuration, worker pool sizing, async blocking patterns, and caching opportunities."""

    name = "runtime_tuner"
    description = "Detects synchronous blocking calls in async code, evaluates server thread/worker sizing, and recommends caching/pooling."
    target_kinds = [TargetKind.CODEBASE, TargetKind.SYSTEM]

    def can_handle(self, target: Target) -> bool:
        return target.kind in (TargetKind.CODEBASE, TargetKind.SYSTEM)

    def analyze(self, target: Target, config: OptiConfig) -> List[Finding]:
        findings: List[Finding] = []

        if target.kind == TargetKind.CODEBASE and target.path:
            root_p = target.path if target.path.is_dir() else target.path.parent
            findings.extend(self._audit_async_blocking_calls(root_p, config))
            findings.extend(self._audit_package_scripts(root_p, config))
            findings.extend(self._audit_server_configs(root_p, config))
        elif target.kind == TargetKind.SYSTEM:
            findings.extend(self._audit_system_tuning(config))

        return findings

    def _audit_async_blocking_calls(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Detects synchronous blocking I/O calls inside async functions or event loop handlers."""
        findings: List[Finding] = []

        # Python: time.sleep() inside async def
        async_def_pattern = re.compile(r"async\s+def\s+([a-zA-Z0-9_]+)\s*\(")
        time_sleep_pattern = re.compile(r"\btime\.sleep\s*\(")
        sync_requests_pattern = re.compile(r"\brequests\.(?:get|post|put|delete)\s*\(")

        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_dir = os.path.relpath(dirpath, root_path)
            if config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                if f.endswith(".py"):
                    full_p = Path(dirpath) / f
                    rel_p = full_p.relative_to(root_path)
                    try:
                        content = full_p.read_text(encoding="utf-8", errors="ignore")
                        lines = content.splitlines()
                        in_async_func = False
                        async_func_name = ""

                        for idx, line in enumerate(lines, 1):
                            async_match = async_def_pattern.search(line)
                            if async_match:
                                in_async_func = True
                                async_func_name = async_match.group(1)
                            elif in_async_func and line and not line.startswith((" ", "\t")):
                                in_async_func = False

                            if in_async_func:
                                if time_sleep_pattern.search(line):
                                    findings.append(Finding(
                                        id=f"OPT-ASYNC-BLOCK-{abs(hash(f'{rel_p}:{idx}')) % 10000:04d}",
                                        category=Category.RUNTIME_SMOOTHNESS,
                                        title=f"Blocking 'time.sleep()' in Async Function '{async_func_name}'",
                                        description=(
                                            f"Synchronous 'time.sleep()' invoked at line {idx} in 'async def {async_func_name}()'. "
                                            "This freezes the entire asyncio event loop, blocking all concurrent requests and degrading throughput."
                                        ),
                                        impact=Impact.HIGH,
                                        effort=Effort.TRIVIAL,
                                        confidence=Confidence.SAFE,
                                        target_entity=f"{rel_p}:{idx}",
                                        target_path=full_p,
                                        exact_fix="Replace 'time.sleep(...)' with 'await asyncio.sleep(...)'.",
                                        plugin_name=self.name,
                                    ))
                                elif sync_requests_pattern.search(line):
                                    findings.append(Finding(
                                        id=f"OPT-ASYNC-REQ-{abs(hash(f'{rel_p}:{idx}')) % 10000:04d}",
                                        category=Category.RUNTIME_SMOOTHNESS,
                                        title=f"Synchronous 'requests' Call in Async Function '{async_func_name}'",
                                        description=(
                                            f"Blocking HTTP call using 'requests' at line {idx} in 'async def {async_func_name}()'. "
                                            "Synchronous socket calls block the event loop while waiting for network I/O."
                                        ),
                                        impact=Impact.HIGH,
                                        effort=Effort.EASY,
                                        confidence=Confidence.LIKELY,
                                        target_entity=f"{rel_p}:{idx}",
                                        target_path=full_p,
                                        exact_fix="Use an asynchronous HTTP client such as 'httpx.AsyncClient()' or 'aiohttp.ClientSession()'.",
                                        plugin_name=self.name,
                                    ))
                    except Exception:
                        continue

                # JS/TS: fs.readFileSync inside async function or express handler
                elif f.endswith((".js", ".ts", ".mjs")):
                    full_p = Path(dirpath) / f
                    rel_p = full_p.relative_to(root_path)
                    try:
                        content = full_p.read_text(encoding="utf-8", errors="ignore")
                        if "fs.readFileSync" in content or "fs.writeFileSync" in content:
                            if "async" in content or "app.get(" in content or "app.post(" in content:
                                findings.append(Finding(
                                    id=f"OPT-NODE-BLOCK-{abs(hash(str(rel_p))) % 10000:04d}",
                                    category=Category.RUNTIME_SMOOTHNESS,
                                    title=f"Synchronous Filesystem I/O in Async Handler in '{rel_p}'",
                                    description=(
                                        f"File '{rel_p}' uses 'fs.readFileSync' or 'fs.writeFileSync' in an asynchronous server context. "
                                        "Synchronous disk I/O blocks the single-threaded Node.js event loop."
                                    ),
                                    impact=Impact.HIGH,
                                    effort=Effort.EASY,
                                    confidence=Confidence.LIKELY,
                                    target_entity=str(rel_p),
                                    target_path=full_p,
                                    exact_fix="Replace with 'await fs.promises.readFile(...)' or non-blocking async callbacks.",
                                    plugin_name=self.name,
                                ))
                    except Exception:
                        continue

        return findings

    def _audit_package_scripts(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Checks for missing memory and performance flags in Node package.json scripts."""
        findings: List[Finding] = []
        pkg_file = root_path / "package.json"
        if not pkg_file.exists():
            return findings

        try:
            import json
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            build_script = scripts.get("build", "")

            # Check if large builds lack NODE_OPTIONS memory tuning
            if "webpack" in build_script or "next build" in build_script:
                if "--max-old-space-size" not in build_script and "NODE_OPTIONS" not in build_script:
                    findings.append(Finding(
                        id="OPT-NODE-MEM-001",
                        category=Category.CONFIG_TUNING,
                        title="Build Script Missing V8 Heap Memory Tuning",
                        description="Complex web builds (Webpack, Next.js) often crash or suffer GC thrashing. Setting '--max-old-space-size=4096' prevents out-of-memory errors and reduces GC pause times.",
                        impact=Impact.MEDIUM,
                        effort=Effort.TRIVIAL,
                        confidence=Confidence.SAFE,
                        target_entity="package.json:scripts.build",
                        target_path=pkg_file,
                        exact_fix="Add 'NODE_OPTIONS=--max-old-space-size=4096' to your build script.",
                        plugin_name=self.name,
                    ))
        except Exception:
            pass

        return findings

    def _audit_server_configs(self, root_path: Path, config: OptiConfig) -> List[Finding]:
        """Audits concurrency and worker configuration for Python and Node servers."""
        findings: List[Finding] = []
        cores = psutil.cpu_count(logical=True) or 4
        rec_workers = (2 * cores) + 1

        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_dir = os.path.relpath(dirpath, root_path)
            if config.is_path_ignored(rel_dir):
                dirnames[:] = []
                continue

            for f in filenames:
                if f in ("gunicorn.conf.py", "wsgi.py", "uvicorn.conf.py", "supervisord.conf"):
                    full_p = Path(dirpath) / f
                    rel_p = full_p.relative_to(root_path)
                    try:
                        content = full_p.read_text(encoding="utf-8", errors="ignore")
                        match = re.search(r"workers\s*=\s*([0-9]+)", content)
                        if match:
                            configured_workers = int(match.group(1))
                            if configured_workers == 1:
                                findings.append(Finding(
                                    id=f"OPT-CONF-WORKER-{abs(hash(str(rel_p))) % 10000:04d}",
                                    category=Category.CONFIG_TUNING,
                                    title=f"Suboptimal Worker Concurrency (workers=1) in '{rel_p}'",
                                    description=(
                                        f"WSGI/ASGI server in '{rel_p}' is configured with a single worker process on a {cores}-core machine. "
                                        f"Recommended concurrency for I/O-bound web services is (2 * cores) + 1 = {rec_workers} workers."
                                    ),
                                    impact=Impact.HIGH,
                                    effort=Effort.TRIVIAL,
                                    confidence=Confidence.SAFE,
                                    target_entity=str(rel_p),
                                    target_path=full_p,
                                    metrics={"current_workers": 1, "recommended_workers": rec_workers, "cores": cores},
                                    exact_fix=f"Set workers = {rec_workers} in {rel_p}.",
                                    plugin_name=self.name,
                                ))
                    except Exception:
                        continue

        return findings

    def _audit_system_tuning(self, config: OptiConfig) -> List[Finding]:
        """Provides host OS configuration tuning suggestions."""
        findings: List[Finding] = []
        cores = psutil.cpu_count(logical=True) or 4
        mem_gb = (psutil.virtual_memory().total) / (1024**3)

        # Recommendation for high memory server
        if mem_gb >= 16:
            findings.append(Finding(
                id="OPT-TUNE-SYS-001",
                category=Category.CONFIG_TUNING,
                title=f"Host Configuration Advice for High-Performance Workloads ({cores} Cores, {mem_gb:.0f} GB RAM)",
                description=(
                    f"Machine possesses abundant resources ({cores} logical cores, {mem_gb:.0f} GB RAM). "
                    "Ensure database connection pools and web servers are tuned to utilize available memory and connection concurrency."
                ),
                impact=Impact.LOW,
                effort=Effort.TRIVIAL,
                confidence=Confidence.SAFE,
                target_entity="System Host",
                plugin_name=self.name,
            ))

        return findings
