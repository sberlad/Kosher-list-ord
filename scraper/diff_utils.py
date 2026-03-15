import hashlib
import json
from typing import Any


def canonicalize_products_for_hash(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return products in a stable, hashable form."""
    canonical_products = []

    for product in products:
        cleaned = dict(product)
        canonical_products.append(cleaned)

    canonical_products.sort(
        key=lambda p: (
            p.get("id", ""),
            p.get("manufacturer", "").lower(),
            p.get("name", "").lower(),
            p.get("size", "").lower() if p.get("size") else "",
        )
    )

    return canonical_products


def compute_content_hash(products: list[dict[str, Any]]) -> str:
    canonical_products = canonicalize_products_for_hash(products)
    payload = json.dumps(
        canonical_products,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def index_products_by_id(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in products if "id" in p}


def diff_products(
    old_products: list[dict[str, Any]],
    new_products: list[dict[str, Any]],
) -> dict[str, list[str]]:
    old_by_id = index_products_by_id(old_products)
    new_by_id = index_products_by_id(new_products)

    old_ids = set(old_by_id.keys())
    new_ids = set(new_by_id.keys())

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)

    changed = sorted(
        pid
        for pid in (old_ids & new_ids)
        if old_by_id[pid] != new_by_id[pid]
    )

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
    }