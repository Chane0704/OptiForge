"""System and Process Resource Profiler plugin for OptiForge."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional
import psutil

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact
from optiforge.core.plugin_base import AnalyzerPlugin
from optiforge.core.target import Target, TargetKind

logger = logging.getLogger("optiforge.system_profiler")


class SystemProfilerPlugin(AnalyzerPlugin):
    """Profiles CPU, RAM, Disk I/O, Network, and Process behavior."""

    name = "system_profiler"
    description = "Profiles system and process resource utilization, leaks, hot loops, and idle waste."
    target_kinds = [TargetKind.PROCESS, TargetKind.SYSTEM]

    def can_handle(self, target: Target) -> bool:
        return target.kind in (TargetKind.PROCESS, TargetKind.SYSTEM)

    def analyze(self, target: Target, config: OptiConfig) -> List[Finding]:
        findings: List[Finding] = []
        profiler_cfg = config.plugins.get(self.name, {})
        duration = float(profiler_cfg.get("sampling_duration_sec", 1.5))
        interval = float(profiler_cfg.get("sampling_interval_sec", 0.25))

        if target.kind == TargetKind.PROCESS:
            findings.extend(self._analyze_process(target, config, duration, interval))
        elif target.kind == TargetKind.SYSTEM:
            findings.extend(self._analyze_system(config, duration, interval))

        return findings

    def _resolve_process(self, target: Target) -> Optional[psutil.Process]:
        """Resolves target into a psutil.Process instance."""
        if target.pid:
            try:
                return psutil.Process(target.pid)
            except psutil.NoSuchProcess:
                logger.error(f"Process with PID {target.pid} not found.")
                return None
        elif target.process_name:
            pname = target.process_name.lower()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if pname in proc.info['name'].lower():
                        return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return None

    def _analyze_process(
        self,
        target: Target,
        config: OptiConfig,
        duration: float,
        interval: float
    ) -> List[Finding]:
        findings: List[Finding] = []
        proc = self._resolve_process(target)

        if not proc:
            findings.append(Finding(
                id="OPT-PROC-000",
                category=Category.RESOURCE_LEAK,
                title="Target Process Not Found",
                description=f"Could not locate active process matching '{target.identifier}'.",
                impact=Impact.LOW,
                effort=Effort.TRIVIAL,
                confidence=Confidence.SAFE,
                target_entity=target.identifier,
                plugin_name=self.name,
            ))
            return findings

        # Sample process metrics over time
        samples_count = max(2, int(duration / interval))
        cpu_samples: List[float] = []
        rss_samples: List[int] = []
        vms_samples: List[int] = []

        try:
            # First call to cpu_percent needs a baseline
            proc.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        for _ in range(samples_count):
            time.sleep(interval)
            try:
                if not proc.is_running():
                    break
                cpu_samples.append(proc.cpu_percent())
                mem_info = proc.memory_info()
                rss_samples.append(mem_info.rss)
                vms_samples.append(mem_info.vms)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

        if not cpu_samples or not rss_samples:
            return findings

        avg_cpu = sum(cpu_samples) / len(cpu_samples)
        max_cpu = max(cpu_samples)
        initial_rss_mb = rss_samples[0] / (1024 * 1024)
        final_rss_mb = rss_samples[-1] / (1024 * 1024)
        rss_delta_mb = final_rss_mb - initial_rss_mb
        peak_rss_mb = max(rss_samples) / (1024 * 1024)

        try:
            num_threads = proc.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            num_threads = 1

        try:
            num_handles = proc.num_handles() if hasattr(proc, "num_handles") else (
                len(proc.open_files()) if hasattr(proc, "open_files") else 0
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            num_handles = 0

        # Store telemetry in target metadata
        target.metadata.update({
            "pid": proc.pid,
            "name": proc.name(),
            "avg_cpu_percent": round(avg_cpu, 1),
            "max_cpu_percent": round(max_cpu, 1),
            "rss_mb": round(final_rss_mb, 2),
            "peak_rss_mb": round(peak_rss_mb, 2),
            "rss_growth_mb": round(rss_delta_mb, 2),
            "num_threads": num_threads,
            "num_handles": num_handles,
        })

        # 1. Check for Hot Loops / High CPU
        if avg_cpu >= config.thresholds.cpu_hot_percent:
            findings.append(Finding(
                id=f"OPT-HOT-001",
                category=Category.HOT_LOOP,
                title=f"Sustained High CPU Usage ({avg_cpu:.1f}%) in {proc.name()} (PID {proc.pid})",
                description=(
                    f"Process average CPU usage was {avg_cpu:.1f}% (peak: {max_cpu:.1f}%), "
                    f"exceeding the threshold of {config.thresholds.cpu_hot_percent}%. "
                    "This usually indicates a busy wait, tight compute loop without yielding, or un-throttled polling."
                ),
                impact=Impact.HIGH,
                effort=Effort.MODERATE,
                confidence=Confidence.SAFE,
                target_entity=f"{proc.name()} [PID: {proc.pid}]",
                metrics={
                    "avg_cpu": avg_cpu,
                    "max_cpu": max_cpu,
                    "threshold": config.thresholds.cpu_hot_percent,
                },
                exact_fix="Introduce non-blocking sleep/yield (e.g. asyncio.sleep, time.sleep(0.01), or event-driven listeners) or offload computation to a worker pool.",
                plugin_name=self.name,
            ))
        elif avg_cpu >= config.thresholds.cpu_idle_high_percent and avg_cpu < config.thresholds.cpu_hot_percent:
            findings.append(Finding(
                id=f"OPT-IDLE-001",
                category=Category.HIGH_IDLE,
                title=f"Elevated Background/Idle CPU Usage ({avg_cpu:.1f}%) in {proc.name()}",
                description=(
                    f"Process is consuming {avg_cpu:.1f}% CPU while idling. "
                    "Frequent timer ticks, aggressive polling intervals, or background watchers may be wasting CPU cycles."
                ),
                impact=Impact.MEDIUM,
                effort=Effort.EASY,
                confidence=Confidence.LIKELY,
                target_entity=f"{proc.name()} [PID: {proc.pid}]",
                metrics={"avg_cpu": avg_cpu, "threshold": config.thresholds.cpu_idle_high_percent},
                exact_fix="Increase polling intervals or switch from polling loops to OS filesystem event watchers (e.g., ReadDirectoryChangesW, inotify, kqueue).",
                plugin_name=self.name,
            ))

        # 2. Check for Memory Leaks (Monotonic growth)
        # Check if samples show consistent upward trajectory
        is_strictly_growing = len(rss_samples) >= 3 and all(rss_samples[i] <= rss_samples[i+1] for i in range(len(rss_samples)-1))
        if rss_delta_mb >= config.thresholds.memory_leak_growth_mb or (is_strictly_growing and rss_delta_mb > 5.0):
            growth_rate_kb_s = (rss_delta_mb * 1024) / max(0.1, duration)
            findings.append(Finding(
                id="OPT-LEAK-001",
                category=Category.RESOURCE_LEAK,
                title=f"Potential Memory Leak: Continuous Growth of +{rss_delta_mb:.1f} MB in {proc.name()}",
                description=(
                    f"Process memory climbed from {initial_rss_mb:.1f} MB to {final_rss_mb:.1f} MB "
                    f"(+{rss_delta_mb:.1f} MB, ~{growth_rate_kb_s:.0f} KB/s) during observation. "
                    "Continuous monotonic memory expansion without garbage collection indicates unreleased references, unbounded caches, or buffer leaks."
                ),
                impact=Impact.HIGH,
                effort=Effort.MODERATE,
                confidence=Confidence.LIKELY,
                target_entity=f"{proc.name()} [PID: {proc.pid}]",
                metrics={
                    "initial_mb": initial_rss_mb,
                    "final_mb": final_rss_mb,
                    "growth_mb": rss_delta_mb,
                    "peak_mb": peak_rss_mb,
                },
                exact_fix="Profile heap allocations using memory profilers (e.g. tracemalloc for Python, clinic/v8-profiler for Node). Clear unbound collections or implement an LRU cache with strict maxsize.",
                plugin_name=self.name,
            ))

        # 3. Check for Handle / File Descriptor Bloat
        if num_handles > 800:
            findings.append(Finding(
                id="OPT-RES-002",
                category=Category.RESOURCE_LEAK,
                title=f"Excessive Handle Count ({num_handles} handles) in {proc.name()}",
                description=(
                    f"Process holds {num_handles} open OS handles/descriptors. "
                    "Unclosed sockets, database connections, or file streams lead to resource exhaustion."
                ),
                impact=Impact.MEDIUM,
                effort=Effort.EASY,
                confidence=Confidence.SAFE,
                target_entity=f"{proc.name()} [PID: {proc.pid}]",
                metrics={"handles": num_handles},
                exact_fix="Ensure all files and sockets are closed in 'with' context managers or 'try...finally' blocks.",
                plugin_name=self.name,
            ))

        return findings

    def _analyze_system(self, config: OptiConfig, duration: float, interval: float) -> List[Finding]:
        """Analyzes host machine-wide resource pressure and top consumers."""
        findings: List[Finding] = []

        # CPU
        cpu_count = psutil.cpu_count(logical=True)
        cpu_percent_per_core = psutil.cpu_percent(interval=duration, percpu=True)
        overall_cpu = sum(cpu_percent_per_core) / len(cpu_percent_per_core) if cpu_percent_per_core else 0.0

        # Memory
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk I/O
        disk_usage = psutil.disk_usage(os.path.abspath(os.sep))
        disk_io = psutil.disk_io_counters()

        # Network
        net_io = psutil.net_io_counters()

        # Top processes by memory and CPU
        top_procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                top_procs.append({
                    "pid": p.info['pid'],
                    "name": p.info['name'],
                    "cpu": p.info['cpu_percent'] or 0.0,
                    "rss_mb": (p.info['memory_info'].rss / (1024 * 1024)) if p.info.get('memory_info') else 0.0,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        top_by_cpu = sorted(top_procs, key=lambda x: x["cpu"], reverse=True)[:5]
        top_by_mem = sorted(top_procs, key=lambda x: x["rss_mb"], reverse=True)[:5]

        # Check for system memory pressure
        if mem.percent > 85.0:
            findings.append(Finding(
                id="OPT-SYS-MEM-001",
                category=Category.RESOURCE_LEAK,
                title=f"System Memory Saturation: {mem.percent:.1f}% RAM Used",
                description=(
                    f"Host system RAM is at {mem.percent:.1f}% utilization "
                    f"({mem.used / (1024**3):.1f} GB of {mem.total / (1024**3):.1f} GB used, {mem.available / (1024**3):.1f} GB available). "
                    f"Top consumer: {top_by_mem[0]['name']} ({top_by_mem[0]['rss_mb']:.1f} MB)."
                ),
                impact=Impact.HIGH,
                effort=Effort.EASY,
                confidence=Confidence.SAFE,
                target_entity="System RAM",
                metrics={"ram_used_percent": mem.percent, "top_consumers": top_by_mem[:3]},
                exact_fix=f"Reduce memory allocation of top processes or terminate unnecessary background services like '{top_by_mem[0]['name']}'.",
                plugin_name=self.name,
            ))

        # Check for CPU bottleneck
        if overall_cpu > 80.0:
            findings.append(Finding(
                id="OPT-SYS-CPU-001",
                category=Category.HOT_LOOP,
                title=f"Host CPU Saturation: {overall_cpu:.1f}% Overall Load across {cpu_count} cores",
                description=(
                    f"System-wide CPU load is {overall_cpu:.1f}%. "
                    f"Top CPU consumer: {top_by_cpu[0]['name']} (PID {top_by_cpu[0]['pid']} at {top_by_cpu[0]['cpu']:.1f}%)."
                ),
                impact=Impact.HIGH,
                effort=Effort.MODERATE,
                confidence=Confidence.SAFE,
                target_entity="System CPU",
                metrics={"cpu_percent": overall_cpu, "cores": cpu_count, "top_cpu": top_by_cpu[:3]},
                exact_fix="Throttle background worker threads or prioritize foreground interactive processes.",
                plugin_name=self.name,
            ))

        # Check for disk space warning
        if disk_usage.percent > 90.0:
            findings.append(Finding(
                id="OPT-SYS-DISK-001",
                category=Category.ASSET_BLOAT,
                title=f"Disk Storage Saturation: {disk_usage.percent:.1f}% Used on root drive",
                description=f"Primary drive has only {disk_usage.free / (1024**3):.1f} GB remaining out of {disk_usage.total / (1024**3):.1f} GB.",
                impact=Impact.HIGH,
                effort=Effort.EASY,
                confidence=Confidence.SAFE,
                target_entity="Root Storage Drive",
                metrics={"disk_used_percent": disk_usage.percent, "free_gb": disk_usage.free / (1024**3)},
                exact_fix="Clean up temporary build caches (.optiforge, npm cache, pip cache, docker images).",
                plugin_name=self.name,
            ))

        return findings
