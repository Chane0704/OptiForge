"""Input Auto-Detection Service for OptiForge.

Accurately classifies user input (folders, files, images, snippets, URLs,
processes, or system) into a unified OptiForge Target. Never confuses local
HTML files or folders with live websites.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Union

from optiforge.core.target import Target, TargetKind


@dataclass
class DetectedInput:
    """Encapsulates the detected target along with human-friendly, measured metadata."""
    target: Target
    input_type: str  # 'folder' | 'files' | 'image' | 'website' | 'snippet' | 'process' | 'system'
    friendly_label: str
    target_path: str = ""
    item_count: int = 1
    estimated_size_bytes: int = 0
    raw_input: Any = None
    language: Optional[str] = None
    detected_tech_stack: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "input_type": self.input_type,
            "friendly_label": self.friendly_label,
            "target_path": self.target_path,
            "item_count": self.item_count,
            "estimated_size_bytes": self.estimated_size_bytes,
            "language": self.language,
            "tech_stack": self.detected_tech_stack,
        }


class InputDetector:
    """Auto-detects and classifies user input into an OptiForge Target."""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".svg", ".tiff", ".gif", ".ico"}
    CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".json", ".yaml", ".yml", ".md", ".sh", ".sql"}

    @classmethod
    def detect(cls, raw_input: Union[str, Path, List[Union[str, Path]]], scratch_dir: Optional[Path] = None) -> DetectedInput:
        """Analyzes raw input and creates a clean Target with measured metadata."""
        if scratch_dir is None:
            scratch_dir = Path.cwd() / ".optiforge" / "scratch"

        # Case 1: Multiple files passed as a list
        if isinstance(raw_input, (list, tuple)):
            paths = [Path(p).resolve() for p in raw_input if Path(p).exists()]
            if not paths:
                raise FileNotFoundError("None of the selected files could be found on disk.")

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
                target_path=str(common_parent),
                item_count=len(paths),
                estimated_size_bytes=total_size,
                raw_input=raw_input,
                language="Images" if is_all_images else "Mixed Files",
            )

        # Case 2: String or single Path
        input_str = str(raw_input).strip()
        if not input_str:
            raise ValueError("No input provided to analyze.")

        # Check for system target
        if input_str.lower() in ("system", "machine", "localhost_sys", "os"):
            target = Target(kind=TargetKind.SYSTEM, identifier="system", metadata={"scope": "machine"})
            return DetectedInput(
                target=target,
                input_type="system",
                friendly_label="Host Computer System",
                target_path="localhost",
                raw_input=raw_input,
            )

        # Check if process ID (numeric or pid:1234)
        if input_str.isdigit() or (input_str.startswith("pid:") and input_str[4:].isdigit()):
            pid = int(input_str.split(":")[-1])
            target = Target(kind=TargetKind.PROCESS, identifier=f"pid:{pid}", pid=pid, metadata={"pid": pid})
            return DetectedInput(
                target=target,
                input_type="process",
                friendly_label=f"Running Process (PID: {pid})",
                target_path=f"PID {pid}",
                raw_input=raw_input,
            )

        # Check if process name (proc:...)
        if input_str.startswith(("proc:", "process:")):
            pname = input_str.split(":", 1)[1]
            target = Target(kind=TargetKind.PROCESS, identifier=input_str, process_name=pname, metadata={"process_name": pname})
            return DetectedInput(
                target=target,
                input_type="process",
                friendly_label=f"Process '{pname}'",
                target_path=pname,
                raw_input=raw_input,
            )

        # STRICT URL CHECK:
        # ONLY treat as a website if it starts with http:// or https:// and does NOT contain newlines
        # (avoid classifying code snippets containing URLs as websites).
        is_standalone_url = (
            "\n" not in input_str and
            " " not in input_str and
            input_str.lower().startswith(("http://", "https://"))
        )
        if is_standalone_url:
            parsed = urllib.parse.urlparse(input_str)
            if parsed.netloc:
                target = Target(kind=TargetKind.WEBSITE, identifier=input_str, url=input_str, metadata={"host": parsed.netloc})
                return DetectedInput(
                    target=target,
                    input_type="website",
                    friendly_label=f"Website ({parsed.netloc})",
                    target_path=input_str,
                    raw_input=raw_input,
                )

        # Dynamic sample project resolver (handles installed app running in Program Files/AppData)
        candidate_path = Path(input_str)
        if not candidate_path.exists() and input_str in ("sample_bloated_project", "sample", "sample_project"):
            for cand in [
                Path.cwd() / "sample_bloated_project",
                Path(sys.executable).parent / "sample_bloated_project",
                Path(sys.executable).parent / "_internal" / "sample_bloated_project",
                Path(__file__).resolve().parent.parent.parent / "sample_bloated_project",
            ]:
                if cand.exists():
                    candidate_path = cand
                    break

        # Check if an existing filesystem path (directory or file)
        if candidate_path.exists():
            resolved = candidate_path.resolve()
            if resolved.is_dir():
                all_files = [f for f in resolved.rglob("*") if f.is_file() and not f.name.startswith(".")]
                total_size = sum(f.stat().st_size for f in all_files)
                extensions = {f.suffix.lower() for f in all_files}

                detected_tech = []
                if any(ext in (".py", ".pyw") for ext in extensions):
                    detected_tech.append("Python")
                if any(ext in (".js", ".ts", ".jsx", ".tsx", ".mjs") for ext in extensions):
                    detected_tech.append("JavaScript/TypeScript")
                if any(ext in (".html", ".htm", ".css", ".scss") for ext in extensions):
                    detected_tech.append("HTML/CSS")
                if any(ext in (".sql", ".db", ".sqlite") for ext in extensions):
                    detected_tech.append("Database/SQL")
                if any(ext in cls.IMAGE_EXTENSIONS for ext in extensions):
                    detected_tech.append("Images")
                if not detected_tech:
                    detected_tech.append("Files")

                tech_str = ", ".join(detected_tech)
                target = Target(
                    kind=TargetKind.CODEBASE,
                    identifier=str(resolved),
                    path=resolved,
                    metadata={
                        "is_directory": True,
                        "total_files": len(all_files),
                        "tech_stack": detected_tech,
                        "resolved_path": str(resolved),
                    }
                )
                return DetectedInput(
                    target=target,
                    input_type="folder",
                    friendly_label=f"{resolved.name}",
                    target_path=str(resolved),
                    item_count=len(all_files),
                    estimated_size_bytes=total_size,
                    raw_input=raw_input,
                    language=tech_str,
                    detected_tech_stack=detected_tech,
                )
            else:
                ext = resolved.suffix.lower()
                fsize = resolved.stat().st_size
                target = Target(kind=TargetKind.CODEBASE, identifier=str(resolved), path=resolved, metadata={"is_file": True})

                if ext in cls.IMAGE_EXTENSIONS:
                    return DetectedInput(
                        target=target,
                        input_type="image",
                        friendly_label=f"Picture: {resolved.name}",
                        target_path=str(resolved),
                        item_count=1,
                        estimated_size_bytes=fsize,
                        raw_input=raw_input,
                        language="Image",
                        detected_tech_stack=["Image"],
                    )
                else:
                    lang_name = ext[1:].upper() if ext else "Text"
                    return DetectedInput(
                        target=target,
                        input_type="files",
                        friendly_label=f"{resolved.name}",
                        target_path=str(resolved),
                        item_count=1,
                        estimated_size_bytes=fsize,
                        raw_input=raw_input,
                        language=lang_name,
                        detected_tech_stack=[lang_name],
                    )

        # Case 3: Pasted text, code snippet, or raw configuration (multiline or code syntax)
        is_code_snippet = (
            len(input_str) > 0 and (
                "\n" in input_str or
                "{" in input_str or
                ";" in input_str or
                "def " in input_str or
                "import " in input_str or
                "<html" in input_str.lower() or
                "const " in input_str or
                "function" in input_str
            )
        )
        if is_code_snippet:
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
                friendly_label=f"Pasted {lang} Snippet",
                target_path=f"Snippet ({len(input_str.splitlines())} lines)",
                item_count=1,
                estimated_size_bytes=len(input_str.encode("utf-8")),
                raw_input=raw_input,
                language=lang,
                detected_tech_stack=[lang],
            )

        # If it's not a URL, not a process, not a snippet, and not on disk:
        # DO NOT silently create a phantom Target that reports 100/100 score!
        raise FileNotFoundError(
            f"Path does not exist on disk: '{input_str}'. "
            "Please check the folder path or click 'Choose Folder' to browse."
        )

    @classmethod
    def override_kind(cls, detected: DetectedInput, forced_kind: str) -> DetectedInput:
        """Allows one-click user correction of detected type ('folder', 'website', 'files')."""
        if forced_kind == "website":
            raw = str(detected.raw_input).strip()
            url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
            detected.target.kind = TargetKind.WEBSITE
            detected.target.url = url
            detected.input_type = "website"
            detected.friendly_label = f"Website ({url})"
        elif forced_kind == "folder":
            detected.target.kind = TargetKind.CODEBASE
            detected.input_type = "folder"
        elif forced_kind in ("files", "single_file"):
            detected.target.kind = TargetKind.CODEBASE
            detected.input_type = "files"
        return detected

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
