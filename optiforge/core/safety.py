"""Safety, Snapshot, Quarantine, and Rollback Engine for OptiForge."""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from optiforge.config import OptiConfig
from optiforge.core.finding import FixProposal, FixResult
from optiforge.core.target import Target

logger = logging.getLogger("optiforge.safety")


class SafetyEngine:
    """Guarantees zero-data-loss modifications via pre-fix snapshots, quarantine, and one-command rollbacks."""

    def __init__(self, config: Optional[OptiConfig] = None):
        self.config = config or OptiConfig()
        self.root_dir = self.config.project_root
        self.backup_root = self.root_dir / self.config.general.backup_dir
        self.quarantine_root = self.root_dir / self.config.general.quarantine_dir

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Computes SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def create_snapshot(self, target: Target, proposal_paths: List[Path]) -> Tuple[str, Path]:
        """Creates an isolated snapshot backup of all files slated for modification or quarantine."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_id = f"backup-{timestamp}"
        snapshot_dir = self.backup_root / backup_id
        files_backup_dir = snapshot_dir / "files"
        files_backup_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "backup_id": backup_id,
            "created_at": datetime.datetime.now().isoformat(),
            "target": target.identifier,
            "target_kind": target.kind.value,
            "items": [],
            "git_commit": None,
        }

        # Check git status if available
        try:
            git_check = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if git_check.returncode == 0:
                manifest["git_commit"] = git_check.stdout.strip()
        except Exception:
            pass

        # Backup each slated file
        for fpath in proposal_paths:
            if not fpath.exists() or not fpath.is_file():
                continue

            rel_p = fpath.relative_to(self.root_dir) if fpath.is_relative_to(self.root_dir) else Path(fpath.name)
            backup_dest = files_backup_dir / rel_p
            backup_dest.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(fpath, backup_dest)
            sha = self.compute_sha256(fpath)

            manifest["items"].append({
                "original_path": str(rel_p),
                "backup_path": str(backup_dest.relative_to(self.root_dir)),
                "sha256": sha,
                "size_bytes": fpath.stat().st_size,
            })

        # Save manifest
        manifest_file = snapshot_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return backup_id, snapshot_dir

    def apply_proposals(self, proposals: List[FixProposal], target: Target) -> List[FixResult]:
        """Safely applies fix proposals with automatic snapshotting and quarantine."""
        results: List[FixResult] = []
        if not proposals:
            return results

        target_paths = [p.target_path for p in proposals if p.target_path.exists()]
        backup_id, snapshot_dir = self.create_snapshot(target, target_paths)
        quarantine_dir = self.quarantine_root / backup_id
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        # Load manifest to update during fix execution
        manifest_file = snapshot_dir / "manifest.json"
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        applied_actions = []

        for p in proposals:
            fpath = p.target_path
            if not fpath.exists():
                results.append(FixResult(
                    success=False,
                    finding_id=p.finding_id,
                    action_type=p.action_type,
                    target_path=fpath,
                    message=f"Target file '{fpath}' does not exist on disk.",
                ))
                continue

            rel_p = fpath.relative_to(self.root_dir) if fpath.is_relative_to(self.root_dir) else Path(fpath.name)

            try:
                # 1. Quarantine Action (NEVER delete)
                if p.action_type == "quarantine_file":
                    dest_quarantine = quarantine_dir / rel_p
                    dest_quarantine.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(fpath, dest_quarantine)

                    applied_actions.append({
                        "action": "quarantine",
                        "original_path": str(rel_p),
                        "quarantined_path": str(dest_quarantine.relative_to(self.root_dir)),
                    })

                    results.append(FixResult(
                        success=True,
                        finding_id=p.finding_id,
                        action_type=p.action_type,
                        target_path=fpath,
                        quarantine_path=dest_quarantine,
                        message=f"Safely moved file to quarantine: '{dest_quarantine.relative_to(self.root_dir)}'",
                        bytes_saved=p.estimated_savings_bytes,
                    ))

                # 2. Image WebP Conversion Action
                elif p.action_type == "convert_image_webp":
                    if p.custom_action:
                        new_webp_path = p.custom_action()
                    else:
                        from PIL import Image
                        new_webp_path = fpath.with_suffix(".webp")
                        with Image.open(fpath) as img:
                            conv = img.convert("RGBA" if "A" in img.mode else "RGB") if img.mode not in ("RGB", "RGBA") else img
                            conv.save(new_webp_path, format="WEBP", quality=80, method=4)

                    # Quarantine original image
                    dest_quarantine = quarantine_dir / rel_p
                    dest_quarantine.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(fpath, dest_quarantine)

                    rel_webp = new_webp_path.relative_to(self.root_dir) if new_webp_path.is_relative_to(self.root_dir) else Path(new_webp_path.name)
                    applied_actions.append({
                        "action": "convert_image_webp",
                        "original_path": str(rel_p),
                        "created_path": str(rel_webp),
                        "quarantined_path": str(dest_quarantine.relative_to(self.root_dir)),
                    })

                    actual_savings = dest_quarantine.stat().st_size - new_webp_path.stat().st_size
                    results.append(FixResult(
                        success=True,
                        finding_id=p.finding_id,
                        action_type=p.action_type,
                        target_path=fpath,
                        quarantine_path=dest_quarantine,
                        message=f"Converted to '{new_webp_path.name}' (saved {actual_savings / 1024:.1f} KB). Original quarantined safely.",
                        bytes_saved=max(0, actual_savings),
                    ))

                # 3. File Modification / Minification Action
                elif p.action_type == "modify_file" and p.replacement_content is not None:
                    # Write to temporary file first for atomic swap
                    tmp_file = fpath.with_suffix(".optitmp")
                    if isinstance(p.replacement_content, str):
                        tmp_file.write_text(p.replacement_content, encoding="utf-8")
                    else:
                        tmp_file.write_bytes(p.replacement_content)

                    # Atomic replace
                    os.replace(tmp_file, fpath)

                    applied_actions.append({
                        "action": "modify",
                        "path": str(rel_p),
                    })

                    results.append(FixResult(
                        success=True,
                        finding_id=p.finding_id,
                        action_type=p.action_type,
                        target_path=fpath,
                        message=f"Applied minification/modification to '{fpath.name}' ({p.estimated_savings_bytes / 1024:.1f} KB saved).",
                        bytes_saved=p.estimated_savings_bytes,
                    ))

                else:
                    results.append(FixResult(
                        success=False,
                        finding_id=p.finding_id,
                        action_type=p.action_type,
                        target_path=fpath,
                        message=f"Unknown or unsupported action type: {p.action_type}",
                    ))

            except Exception as e:
                logger.error(f"Error applying fix on {fpath}: {e}")
                results.append(FixResult(
                    success=False,
                    finding_id=p.finding_id,
                    action_type=p.action_type,
                    target_path=fpath,
                    message=f"Failed to apply fix: {e}",
                ))

        # Save executed actions in manifest
        manifest_data["applied_actions"] = applied_actions
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        return results

    def rollback(self, backup_id: Optional[str] = None) -> Dict[str, Any]:
        """Restores files to exact pre-fix state from snapshot and quarantine."""
        if not self.backup_root.exists():
            return {"success": False, "error": "No backup directory exists."}

        # Resolve backup snapshot
        if backup_id:
            snapshot_dir = self.backup_root / backup_id
            if not snapshot_dir.exists():
                return {"success": False, "error": f"Backup snapshot '{backup_id}' not found."}
        else:
            backups = sorted([d for d in self.backup_root.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)
            if not backups:
                return {"success": False, "error": "No backups available to rollback."}
            snapshot_dir = backups[0]
            backup_id = snapshot_dir.name

        manifest_file = snapshot_dir / "manifest.json"
        if not manifest_file.exists():
            return {"success": False, "error": f"Corrupt backup '{backup_id}': missing manifest.json."}

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        files_backup_dir = snapshot_dir / "files"
        restored_count = 0
        verified_count = 0

        # 1. Reverse applied actions (e.g. remove created webp files)
        applied_actions = manifest.get("applied_actions", [])
        for act in applied_actions:
            if act.get("action") == "convert_image_webp" and "created_path" in act:
                created_p = self.root_dir / act["created_path"]
                if created_p.exists():
                    created_p.unlink()

        # 2. Restore all files from backup/quarantine
        for item in manifest.get("items", []):
            orig_rel = Path(item["original_path"])
            orig_dest = self.root_dir / orig_rel
            backup_src = files_backup_dir / orig_rel

            if backup_src.exists():
                orig_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_src, orig_dest)
                restored_count += 1

                # Verify SHA-256 match
                restored_hash = self.compute_sha256(orig_dest)
                if restored_hash == item["sha256"]:
                    verified_count += 1
                else:
                    logger.warning(f"Hash mismatch on restored file: {orig_dest}")

        return {
            "success": True,
            "backup_id": backup_id,
            "restored_count": restored_count,
            "verified_count": verified_count,
        }
