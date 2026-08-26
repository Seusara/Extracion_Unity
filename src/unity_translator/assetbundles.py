from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import UnityPy

from .storage import sha256_file


@dataclass(frozen=True)
class BundleObject:
    bundle: str
    path_id: int
    type: str
    name: str
    locator: dict[str, Any]
    text: str | None = None
    classification: str = "metadata"

    def as_dict(self) -> dict[str, Any]:
        result = {
            "bundle": self.bundle,
            "path_id": self.path_id,
            "type": self.type,
            "name": self.name,
            "locator": self.locator,
            "classification": self.classification,
        }
        if self.text is not None:
            result["text"] = self.text
        return result


@dataclass(frozen=True)
class BundleInspection:
    path: str
    sha256: str
    readable: bool
    objects: tuple[BundleObject, ...]
    type_counts: dict[str, int]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "readable": self.readable,
            "objects": [obj.as_dict() for obj in self.objects],
            "type_counts": self.type_counts,
            "error": self.error,
        }


def _close_environment(environment: Any) -> None:
    for asset_file in getattr(environment, "files", {}).values():
        stream = getattr(getattr(asset_file, "reader", None), "stream", None)
        if stream is not None and hasattr(stream, "close"):
            stream.close()


def _text_classification(text: str) -> str:
    if not text.strip():
        return "metadata"
    if "{" in text or "}" in text or "@" in text or "\n" in text:
        return "translation_candidate"
    return "text_candidate"


def inspect_bundle(path: str | Path, *, max_objects: int = 500) -> BundleInspection:
    bundle_path = Path(path)
    digest = sha256_file(bundle_path)
    try:
        environment = UnityPy.load(str(bundle_path))
        objects = []
        counts: dict[str, int] = {}
        for obj in environment.objects:
            type_name = obj.type.name
            counts[type_name] = counts.get(type_name, 0) + 1
            if len(objects) >= max_objects:
                continue
            name = ""
            text: str | None = None
            classification = "metadata"
            if type_name == "TextAsset":
                try:
                    data = obj.read()
                    name = str(getattr(data, "m_Name", ""))
                    value = getattr(data, "m_Script", "")
                    text = value.decode("utf-8-sig") if isinstance(value, bytes) else str(value)
                    classification = _text_classification(text)
                except Exception:
                    classification = "binary_data"
            elif type_name == "MonoScript":
                try:
                    data = obj.read()
                    name = str(getattr(data, "m_ClassName", ""))
                except Exception:
                    pass
            elif type_name == "AssetBundle":
                try:
                    data = obj.read()
                    name = str(getattr(data, "m_AssetBundleName", ""))
                except Exception:
                    pass
            objects.append(BundleObject(
                bundle=bundle_path.name,
                path_id=obj.path_id,
                type=type_name,
                name=name,
                locator={
                    "bundle": bundle_path.name,
                    "path_id": obj.path_id,
                    "type": type_name,
                    "name": name,
                },
                text=text,
                classification=classification,
            ))
        if not objects:
            return BundleInspection(
                str(bundle_path),
                digest,
                False,
                (),
                counts,
                "ValueError: bundle contains no Unity objects",
            )
        return BundleInspection(str(bundle_path), digest, True, tuple(objects), counts)
    except Exception as error:
        return BundleInspection(str(bundle_path), digest, False, (), {}, f"{type(error).__name__}: {error}")
    finally:
        if "environment" in locals():
            _close_environment(environment)
