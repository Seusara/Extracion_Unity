from __future__ import annotations

import csv
import io
from pathlib import Path

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .storage import sha256_file, sha256_text

PASSWORD = b"mogurasofttype"
SALT = b"mogumogumogu"
PROFILE = {
    "extractor": "holyknight-encrypted-tsv",
    "source_root": "StreamingAssets/Lang/en",
}


def _key_iv() -> tuple[bytes, bytes]:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=32, salt=SALT, iterations=1000)
    derived = kdf.derive(PASSWORD)
    return derived[:16], derived[16:]


def _decrypt(path: Path) -> str:
    key, iv = _key_iv()
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(path.read_bytes()) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8-sig")


def _encrypt(text: str) -> bytes:
    key, iv = _key_iv()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(text.encode("utf-8-sig")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def detect(data_dir: Path) -> bool:
    root = data_dir / PROFILE["source_root"]
    return root.is_dir() and any(root.rglob("*.dat"))


def _source_root(data_dir: Path, profile: dict) -> Path:
    root = data_dir / profile.get("source_root", PROFILE["source_root"])
    if not root.is_dir():
        raise FileNotFoundError(f"Holy Knight text directory not found: {root}")
    return root


def extract(project: Path, manifest: dict) -> tuple[list[dict], dict[str, str]]:
    data_dir = Path(manifest["analysis"]["data_dir"])
    root = _source_root(data_dir, manifest["profile"])
    data_dir_name = manifest["analysis"]["data_dir_name"]
    entries: list[dict] = []
    source_files: dict[str, str] = {}
    seen: set[str] = set()

    for source in sorted(root.rglob("*.dat")):
        relative_source = source.relative_to(root).as_posix()
        if relative_source.lower().startswith("image/"):
            continue
        relative_game = f"{data_dir_name}/{manifest['profile'].get('source_root', PROFILE['source_root'])}/{relative_source}"
        try:
            text = _decrypt(source)
        except Exception as error:
            raise ValueError(f"Could not decrypt Holy Knight text file {relative_game}: {error}") from error
        source_files[relative_game] = sha256_file(source)
        snapshot = project / "originals" / Path(relative_game)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(source.read_bytes())
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter="\t"))
        is_dialogue = relative_source.lower().startswith("adv/")
        text_column = 2 if is_dialogue else 1
        for row_number, row in enumerate(rows, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            key = row[0].strip() if row else ""
            if not key or key.startswith("//"):
                continue
            if text_column >= len(row):
                continue
            original = row[text_column]
            if not original.strip():
                continue
            entry_id = f"{relative_game}:{key}"
            if entry_id in seen:
                raise ValueError(f"Duplicate Holy Knight translation ID: {entry_id}")
            seen.add(entry_id)
            entries.append({
                "id": entry_id,
                "source_file": relative_game,
                "asset_type": "HolyKnightEncryptedTSV",
                "object_identifier": key,
                "field": f"cell[{row_number}][{text_column}]",
                "original_text": original,
                "translated_text": "",
                "original_hash": sha256_text(original),
                "status": "untranslated",
                "metadata": {
                    "row": row_number,
                    "column": text_column,
                    "delimiter": "\t",
                    "encoding": "utf-8-sig",
                },
            })
    if not entries:
        raise ValueError(f"No translatable Holy Knight rows found under {root}")
    return entries, source_files


def inject_file(path: Path, entries: list[dict]) -> None:
    text = _decrypt(path)
    rows = [list(row) for row in csv.reader(io.StringIO(text, newline=""), delimiter="\t")]
    for entry in entries:
        metadata = entry["metadata"]
        row_index = metadata["row"] - 1
        column = metadata["column"]
        if row_index >= len(rows) or column >= len(rows[row_index]):
            raise ValueError(f"Staging row missing for ID: {entry['id']}")
        if rows[row_index][column] != entry["original_text"]:
            raise ValueError(f"Staging original mismatch for ID: {entry['id']}")
        rows[row_index][column] = entry["translated_text"]
    output = io.StringIO(newline="")
    csv.writer(output, delimiter="\t", lineterminator="\n").writerows(rows)
    path.write_bytes(_encrypt(output.getvalue()))
    verified = list(csv.reader(io.StringIO(_decrypt(path), newline=""), delimiter="\t"))
    for entry in entries:
        metadata = entry["metadata"]
        actual = verified[metadata["row"] - 1][metadata["column"]]
        if actual != entry["translated_text"]:
            raise RuntimeError(f"Post-injection verification failed: {entry['id']}")
