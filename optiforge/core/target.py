"""Target abstractions for OptiForge."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.parse


class TargetKind(str, Enum):
    WEBSITE = "website"
    PROCESS = "process"
    CODEBASE = "codebase"
    SYSTEM = "system"


class Target:
    """Represents an optimization target (website, process, codebase, or system)."""

    def __init__(
        self,
        kind: TargetKind,
        identifier: str,
        path: Optional[Path] = None,
        url: Optional[str] = None,
        pid: Optional[int] = None,
        process_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.kind = kind
        self.identifier = identifier
        self.path = Path(path).resolve() if path else None
        self.url = url
        self.pid = pid
        self.process_name = process_name
        self.metadata = metadata or {}

    @classmethod
    def from_string(cls, raw: str) -> "Target":
        raw = raw.strip()

        # Check for system target
        if raw.lower() in ("system", "localhost", "os", "machine", "self"):
            return cls(
                kind=TargetKind.SYSTEM,
                identifier="system",
                metadata={"scope": "machine"}
            )

        # Check if URL
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return cls(
                kind=TargetKind.WEBSITE,
                identifier=raw,
                url=raw,
                metadata={"host": parsed.netloc, "scheme": parsed.scheme}
            )

        # Check if process ID (numeric)
        if raw.isdigit():
            pid = int(raw)
            return cls(
                kind=TargetKind.PROCESS,
                identifier=f"pid:{pid}",
                pid=pid,
                metadata={"pid": pid}
            )

        # Check if process name (e.g. pid:1234 or proc:node or process:python)
        if raw.startswith("pid:"):
            pid_val = int(raw.split(":", 1)[1])
            return cls(
                kind=TargetKind.PROCESS,
                identifier=raw,
                pid=pid_val,
                metadata={"pid": pid_val}
            )
        if raw.startswith(("proc:", "process:")):
            pname = raw.split(":", 1)[1]
            return cls(
                kind=TargetKind.PROCESS,
                identifier=raw,
                process_name=pname,
                metadata={"process_name": pname}
            )

        # Check if local directory / file path
        path_candidate = Path(raw)
        if path_candidate.exists() or raw in (".", "./", "../") or "/" in raw or "\\" in raw:
            resolved = path_candidate.resolve()
            if resolved.is_dir() or not resolved.exists():
                return cls(
                    kind=TargetKind.CODEBASE,
                    identifier=str(resolved),
                    path=resolved,
                    metadata={"is_directory": True}
                )
            else:
                return cls(
                    kind=TargetKind.CODEBASE,
                    identifier=str(resolved),
                    path=resolved,
                    metadata={"is_file": True}
                )

        # Default fallback to codebase directory if relative or exists
        return cls(
            kind=TargetKind.CODEBASE,
            identifier=str(path_candidate.resolve()),
            path=path_candidate.resolve(),
            metadata={"inferred": True}
        )

    def __repr__(self) -> str:
        return f"Target(kind={self.kind.value}, identifier='{self.identifier}')"
