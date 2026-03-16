import json
import os
from datetime import datetime, timezone
from typing import Any

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots")


def load_previous_manifest(output_dir: str) -> dict | None:
    manifest_path = os.path.join(output_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def previous_content_hash(output_dir: str) -> str | None:
    manifest = load_previous_manifest(output_dir)
    if not manifest:
        return None
    return manifest.get("content_hash")


def save_snapshot(
    kosher_list: dict[str, Any],
    manifest: dict[str, Any],
    diff: dict[str, Any],
):
    version = manifest.get("version")
    if not version:
        version = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    snapshot_path = os.path.join(SNAPSHOT_DIR, version)
    os.makedirs(snapshot_path, exist_ok=True)

    with open(os.path.join(snapshot_path, "kosher_list.json"), "w", encoding="utf-8") as f:
        json.dump(kosher_list, f, ensure_ascii=False, indent=2)

    with open(os.path.join(snapshot_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(os.path.join(snapshot_path, "diff.json"), "w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)