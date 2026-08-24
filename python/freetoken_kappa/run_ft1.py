"""Gate FT1 — κ-manifest + verify + refusal on a checkpoint written by the
REAL FTWWriter (loaded from source with its logger dependency stubbed, so no
GPU stack is needed). Exercises the format's edge cases deliberately:
multi-shard span (a tensor larger than the shard limit), expert-bank layer
entries, and the long tail of tiny tensors.

Emits one JSON line: build/verify rates, tamper witness, exit 0 on pass.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import shutil
import sys
import time
import types
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

# load the real writer from source; stub only freetoken.utils.init_logger
ft = types.ModuleType("freetoken")
ft_utils = types.ModuleType("freetoken.utils")
ft_utils.init_logger = lambda name: logging.getLogger(name)
ft.utils = ft_utils
sys.modules.setdefault("freetoken", ft)
sys.modules.setdefault("freetoken.utils", ft_utils)
spec = importlib.util.spec_from_file_location(
    "ftw_real", REPO / "python" / "freetoken" / "checkpoint" / "ftw.py"
)
ftw_real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ftw_real)

sys.path.insert(0, str(REPO / "python"))
from freetoken_kappa.ftw_kappa import MANIFEST_NAME, build_manifest, verify  # noqa: E402


def main() -> int:
    out = Path.home() / "ftw-f1-checkpoint"
    shutil.rmtree(out, ignore_errors=True)
    g = torch.Generator().manual_seed(7)

    # 1 MiB shard limit so the big tensor spans shards (format edge case)
    w = ftw_real.FTWWriter(str(out), shard_limit=1 << 20)
    w.add_tensor("model.embed", torch.randn(512, 512, generator=g, dtype=torch.float32))
    for layer in range(4):
        w.add_tensor(f"experts.gate_up#L{layer:05d}",
                     torch.randn(8, 64, 128, generator=g, dtype=torch.bfloat16).view(torch.bfloat16),
                     kind="experts_bank")
        w.add_tensor(f"model.layers.{layer}.norm",
                     torch.randn(64, generator=g, dtype=torch.float32))
    w.finalize({"meta": {"model": "f1-synthetic"}})

    t0 = time.perf_counter()
    manifest = build_manifest(out)
    build_s = time.perf_counter() - t0
    (out / MANIFEST_NAME).write_text(json.dumps(manifest))

    ok, wit, verify_s = verify(out, manifest)
    assert ok and wit is None, "clean checkpoint must certify"

    # single-bit tamper deep inside shard 1 (an experts_bank region)
    victim = out / "freetoken-00001.ftw"
    data = bytearray(victim.read_bytes())
    data[len(data) // 2] ^= 0x01
    victim.write_bytes(bytes(data))
    ok2, wit2, _ = verify(out, manifest)

    mb = manifest["total_bytes"] / 1e6
    result = {
        "gate": "FT1",
        "tensors": len(manifest["tensors"]),
        "mb": round(mb, 1),
        "manifest_identity": manifest["identity"][:23],
        "build_s": round(build_s, 3),
        "verify_s": round(verify_s, 3),
        "verify_mb_s": round(mb / max(verify_s, 1e-9), 0),
        "clean_certified": ok,
        "tamper_refused": (not ok2) and wit2 is not None,
        "tamper_witness": wit2.tensor if wit2 else None,
    }
    print(json.dumps(result))
    shutil.rmtree(out, ignore_errors=True)
    return 0 if ok and not ok2 and wit2 else 1


if __name__ == "__main__":
    sys.exit(main())
