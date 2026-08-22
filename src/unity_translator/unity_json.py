from __future__ import annotations

from .storage import sha256_text


def extract_json_entries(
    document: dict,
    *,
    source_file: str,
    path_id: int,
    list_key: str,
    id_field: str,
    text_field: str,
) -> list[dict]:
    items = document.get(list_key)
    if not isinstance(items, list):
        raise ValueError(f"JSON field is not a list: {list_key}")
    entries: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"JSON item {index} is not an object")
        data_id = item.get(id_field)
        text = item.get(text_field)
        if data_id is None or text is None or not isinstance(text, str) or not text.strip():
            continue
        entry_id = f"{source_file}:{path_id}:{text_field}:{data_id}"
        if entry_id in seen:
            raise ValueError(f"Duplicate extracted ID: {entry_id}")
        seen.add(entry_id)
        entries.append({
            "id": entry_id,
            "source_file": source_file,
            "asset_type": "TextAssetJSON",
            "object_identifier": str(path_id),
            "field": f"{list_key}[{index}].{text_field}",
            "original_text": text,
            "translated_text": "",
            "original_hash": sha256_text(text),
            "status": "untranslated",
            "metadata": {
                "path_id": path_id,
                "list_key": list_key,
                "item_index": index,
                "data_id": str(data_id),
                "id_field": id_field,
                "text_field": text_field,
            },
        })
    return entries


def apply_translations(document: dict, entries: list[dict]) -> int:
    changed = 0
    for entry in entries:
        if entry["status"] not in {"translated", "intentionally_empty"}:
            continue
        metadata = entry["metadata"]
        item = document[metadata["list_key"]][metadata["item_index"]]
        if str(item.get(metadata["id_field"])) != metadata["data_id"]:
            raise ValueError(f"JSON locator changed for ID: {entry['id']}")
        if item.get(metadata["text_field"]) != entry["original_text"]:
            raise ValueError(f"JSON original changed for ID: {entry['id']}")
        item[metadata["text_field"]] = entry["translated_text"]
        changed += 1
    return changed
