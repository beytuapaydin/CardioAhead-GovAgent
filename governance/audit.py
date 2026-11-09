"""Tamper-evident hash-chain JSONL log. Not immutable or tamper-proof."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

def _serialize(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def append_event(path: Path, event: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = "GENESIS"
    if path.exists() and not verify_chain(path):
        raise ValueError("Existing audit chain invalid")
    if path.exists() and path.stat().st_size:
        previous = [line for line in path.read_text().splitlines() if line.strip()]
        if previous:
            prev = json.loads(previous[-1])["hash"]
    record = {"ts_utc": datetime.now(timezone.utc).isoformat(), "previous_hash": prev, **event}
    record["hash"] = hashlib.sha256(_serialize(record).encode()).hexdigest()
    with path.open("a", encoding="utf-8") as f:
        f.write(_serialize(record) + "\n")
    return record

def verify_chain(path: Path) -> bool:
    prev = "GENESIS"
    if not path.exists(): return True
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            obj = json.loads(line)
            digest = obj.pop("hash")
            if obj["previous_hash"] != prev or hashlib.sha256(_serialize(obj).encode()).hexdigest() != digest:
                return False
            prev = digest
    except (KeyError, TypeError, ValueError):
        return False
    return True
