"""Input Auto-Detection Service for OptiForge.

Automatically classifies user input (folders, files, images, snippets, URLs,
processes, or system) into a unified OptiForge Target.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Union

from optiforge.core.target import Target, TargetKind


@dataclass
class DetectedInput:
    """Encapsulates the detected target along with human-friendly metadata."""
    target: Target
    input_type: str  # 'website' | 'folder' | 'files' | 'image' | 'snippet' | 'process' | 'system'
    friendly_label: str
    item_count: int = 1
    estimated_size_bytes: int = 0
    raw_input: Any = None
    language: Optional[str] = None


class InputDetector:
    """Auto-detects and classifies arbitrary user input into an OptiForge Target."""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".svg", ".tiff", ".gif"}
    CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".sh"}

    @classmethod
    def detect(cls, raw_input: Union[str, Path, List[Union[str, Path]]], scratch_dir: Optional[Path] = None) -> DetectedInput:
        """Analyzes raw input and creates a clean Target with friendly metadata."""
        if scratch_dir is None:
            scratch_dir = Path.cwd() / ".optiforge" / "scratch"

        # Case 1: Multiple files passed as a list
        if isinstance(raw_input, (list, tuple)):
            paths = [Path(p).resolve() for p in raw_input if Path(p).exists()]
            if not paths:
                # Fallback to current directory
                target = Target.from_string(".")
                return DetectedInput(target=target, input_type="folder", friendly_label="Current Project Folder", raw_input=raw_input)

            total_size = sum(p.stat().st_size for p in paths if p.is_file())
            is_all_images = all(p.suffix.lower() in cls.IMAGE_EXTENSIONS for p in paths)

            common_parent = Path(os.path.commonpath([str(p) for p in paths])) if len(paths) > 1 else paths[0].parent
            target = Target(
                kind=TargetKind.CODEBASE,
                identifier=f"{len(paths)} selected files",
                path=common_parent,
                metadata={"selected_files": [str(p) for p in paths], "is_multi_file": True}
            )

            if is_all_images:
                label = f"{len(paths)} Images for Optimization"
                itype = "image"
            else:
                label = f"{len(paths)} Selected Files ({common_parent.name})"
                itype = "files"

            return DetectedInput(
                target=target,
                input_type=itype,
                friendly_label=label,
                item_count=len(paths),
                estimated_size_bytes=total_size,
                raw_input=raw_input,
            )

        # Case 2: String or single Path
        input_str = str(raw_input).strip()

        # Check for system target
        if input_str.lower() in ("system", "machine", "localhost_sys", "os"):
            target = Target(kind=TargetKind.SYSTEM, identifier="system", metadata={"scope": "machine"})
            return DetectedInput(target=target, input_type="system", friendly_label="Host Computer System", raw_input=raw_input)

        # Check if URL
        parsed = urllib.parse.urlparse(input_str)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            target = Target(kind=TargetKind.WEBSITE, identifier=input_str, url=input_str, metadata={"host": parsed.netloc})
            return DetectedInput(target=target, input_type="website", friendly_label=f"Website ({parsed.netloc})", raw_input=raw_input)

        # Check if process ID (numeric or pid:1234)
        if input_str.isdigit() or input_str.startswith("pid:"):
            pid = int(input_str.split(":")[-1])
            target = Target(kind=TargetKind.PROCESS, identifier=f"pid:{pid}", pid=pid, metadata={"pid": pid})
            return DetectedInput(target=target, input_type="process", friendly_label=f"Running Process (PID: {pid})", raw_input=raw_input)

        # Check if process name (proc:...)
        if input_str.startswith(("proc:", "process:")):
            pname = input_str.split(":", 1)[1]
            target = Target(kind=TargetKind.PROCESS, identifier=input_str, process_name=pname, metadata={"process_name": pname})
            return DetectedInput(target=target, input_type="process", friendly_label=f"Process '{pname}'", raw_input=raw_input)

        # Check if an existing filesystem path (directory or file)
        candidate_path = Path(input_str)
        if candidate_path.exists():
            resolved = candidate_path.resolve()
            if resolved.is_dir():
                total_size = sum(f.stat().st_size for f in resolved.rglob("*") if f.is_file() and not f.name.startswith("."))
                target = Target(kind=TargetKind.CODEBASE, identifier=str(resolved), path=resolved, metadata={"is_directory": True})
                return DetectedInput(
                    target=target,
                    input_type="folder",
                    friendly_label=f"Project Folder ({resolved.name})",
                    estimated_size_bytes=total_size,
                    raw_input=raw_input,
                )
            else:
                ext = resolved.suffix.lower()
                fsize = resolved.stat().st_size
                target = Target(kind=TargetKind.CODEBASE, identifier=str(resolved), path=resolved, metadata={"is_file": True})

                if ext in cls.IMAGE_EXTENSIONS:
                    return DetectedInput(
                        target=target,
                        input_type="image",
                        friendly_label=f"Picture ({resolved.name})",
                        item_count=1,
                        estimated_size_bytes=fsize,
                        raw_input=raw_input,
                    )
                else:
                    return DetectedInput(
                        target=target,
                        input_type="files",
                        friendly_label=f"Single File ({resolved.name})",
                        item_count=1,
                        estimated_size_bytes=fsize,
                        raw_input=raw_input,
                        language=ext[1:] if ext else None,
                    )

        # Case 3: Pasted text, code snippet, or raw configuration
        if len(input_str) > 0 and ("\n" in input_str or " " in input_str or "{" in input_str or ";" in input_str or "def " in input_str or "<" in input_str):
            lang, ext = cls._detect_snippet_language(input_str)
            scratch_dir.mkdir(parents=True, exist_ok=True)
            snippet_file = scratch_dir / f"snippet{ext}"
            snippet_file.write_text(input_str, encoding="utf-8")

            target = Target(
                kind=TargetKind.CODEBASE,
                identifier="Pasted Code Snippet",
                path=snippet_file,
                metadata={"is_snippet": True, "language": lang, "lines": len(input_str.splitlines())}
            )
            return DetectedInput(
                target=target,
                input_type="snippet",
                friendly_label=f"Pasted {lang} Snippet ({len(input_str.splitlines())} lines)",
                item_count=1,
                estimated_size_bytes=len(input_str.encode("utf-8")),
                raw_input=raw_input,
                language=lang,
            )

        # Fallback: treat as codebase directory candidate
        target = Target.from_string(input_str)
        return DetectedInput(
            target=target,
            input_type="folder" if target.kind == TargetKind.CODEBASE else target.kind.value,
            friendly_label=f"Target ({input_str})",
            raw_input=raw_input,
        )

    @classmethod
    def _detect_snippet_language(cls, text: str) -> tuple[str, str]:
        """Infers programming language from snippet content."""
        lower = text.lower()
        if "<!doctype html" in lower or "<html" in lower or "</div>" in lower:
            return "HTML", ".html"
        if "def " in text or "import " in text or "print(" in text or "elif " in text:
            return "Python", ".py"
        if "console.log" in text or "const " in text or "let " in text or "function" in text or "=>" in text:
            return "JavaScript", ".js"
        if "{" in text and "}" in text and (":" in text and (";" in text or "px" in text or "color" in text)):
            return "CSS", ".css"
        if text.strip().startswith("{") and text.strip().endswith("}"):
            return "JSON", ".json"
        return "Code", ".txt"
