"""Plane II for FreeToken weights — κ-manifest over the FTW format.

Standalone by design: reads only `freetoken_weight.json` + the shard files,
imports nothing from `freetoken`. The FTW invariants it relies on are the
format's own: every tensor occupies [global_off, global_off+nbytes) in one
logical byte region, physically sliced into shard files listed with their
global offsets.

- build: per-tensor (and per-expert-bank-layer) `blake3:` labels + a
  manifest identity under the uor-addr rule (`sha256:` over canonical CBOR).
  Written additively as `kappa-manifest.json` next to the index — the FTW
  bytes and the index itself are never modified.
- verify: recompute every label; Certified, or a Witness naming the exact
  tensor whose bytes no longer derive their label. No third state.

CLI:
    python -m freetoken_kappa.ftw_kappa build  <ftw_dir>
    python -m freetoken_kappa.ftw_kappa verify <ftw_dir>
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import blake3
import cbor2

INDEX_NAME = "freetoken_weight.json"
MANIFEST_NAME = "kappa-manifest.json"


def _shard_map(index: dict) -> list[tuple[int, int, str]]:
    """[(global_off, nbytes, file)] sorted by global_off."""
    return sorted(
        (s["global_off"], s["nbytes"], s["file"]) for s in index["shards"]
    )


def _region_kappa(ftw_dir: Path, shards, global_off: int, nbytes: int) -> str:
    """blake3 over one tensor's byte region, spanning shards if needed."""
    h = blake3.blake3()
    remaining = nbytes
    pos = global_off
    for s_off, s_len, s_file in shards:
        if remaining == 0:
            break
        if pos >= s_off + s_len or pos + remaining <= s_off:
            continue
        local = pos - s_off
        take = min(remaining, s_len - local)
        with (ftw_dir / s_file).open("rb") as f:
            f.seek(local)
            left = take
            while left:
                chunk = f.read(min(left, 1 << 24))
                if not chunk:
                    raise IOError(f"short read in {s_file} at {local}")
                h.update(chunk)
                left -= len(chunk)
        pos += take
        remaining -= take
    if remaining:
        raise IOError(f"region [{global_off}, +{nbytes}) not covered by shards")
    return "blake3:" + h.hexdigest()


def build_manifest(ftw_dir: str | Path) -> dict:
    ftw_dir = Path(ftw_dir)
    index = json.loads((ftw_dir / INDEX_NAME).read_text())
    shards = _shard_map(index)
    tensors = []
    total = 0
    for t in index["tensors"]:
        total += t["nbytes"]
        tensors.append(
            {
                "name": t["name"],
                "kind": t["kind"],
                "dtype": t["dtype"],
                "shape": t["shape"],
                "nbytes": t["nbytes"],
                "kappa": _region_kappa(ftw_dir, shards, t["global_off"], t["nbytes"]),
            }
        )
    body = {"v": 1, "t": "ftw-kappa-manifest", "format": index["format"],
            "align": index["align"], "tensors": tensors}
    ident = hashlib.sha256(cbor2.dumps(body, canonical=True)).hexdigest()
    return {**body, "identity": "sha256:" + ident, "total_bytes": total}


@dataclass
class Witness:
    tensor: str
    expected: str
    actual: str


def verify(ftw_dir: str | Path, manifest: dict) -> tuple[bool, Witness | None, float]:
    t0 = time.perf_counter()
    ftw_dir = Path(ftw_dir)
    index = json.loads((ftw_dir / INDEX_NAME).read_text())
    shards = _shard_map(index)
    offsets = {t["name"]: (t["global_off"], t["nbytes"]) for t in index["tensors"]}
    for t in manifest["tensors"]:
        entry = offsets.get(t["name"])
        if entry is None:
            return False, Witness(t["name"], t["kappa"], "<absent>"), time.perf_counter() - t0
        actual = _region_kappa(ftw_dir, shards, *entry)
        if actual != t["kappa"]:
            return False, Witness(t["name"], t["kappa"], actual), time.perf_counter() - t0
    return True, None, time.perf_counter() - t0


def main() -> int:
    cmd, ftw_dir = sys.argv[1], Path(sys.argv[2])
    if cmd == "build":
        t0 = time.perf_counter()
        m = build_manifest(ftw_dir)
        (ftw_dir / MANIFEST_NAME).write_text(json.dumps(m))
        print(json.dumps({"identity": m["identity"], "tensors": len(m["tensors"]),
                          "mb": round(m["total_bytes"] / 1e6, 1),
                          "build_s": round(time.perf_counter() - t0, 2)}))
        return 0
    if cmd == "verify":
        m = json.loads((ftw_dir / MANIFEST_NAME).read_text())
        ok, wit, secs = verify(ftw_dir, m)
        if ok:
            print(json.dumps({"certified": True, "verify_s": round(secs, 2),
                              "mb_s": round(m["total_bytes"] / 1e6 / max(secs, 1e-9), 0)}))
            return 0
        print(json.dumps({"certified": False, "witness": {
            "tensor": wit.tensor, "expected": wit.expected, "actual": wit.actual}}))
        return 1
    print("usage: build|verify <ftw_dir>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
