"""Plane I conformance — FreeToken κ identities vs the REAL uor-addr crate.

Requires the `uor-addr` Python binding (ctypes over uor-addr-c). Every key
this lane mints must satisfy: `sha256:<hex(key)>` == kappa.cbor_address of
the same canonical-CBOR bytes. One JSON line; exit 0 = all byte-identical.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cbor2
from uor_addr import kappa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from freetoken_kappa.identity import ROOT_SEED, chain_page_keys, identity, root_key, uor_key_fn


def ref(obj) -> str:
    return kappa.cbor_address(cbor2.dumps(obj, canonical=True))


def main() -> int:
    toks = list(range(1000, 1000 + 96))
    page = 64
    cases = {}

    cases["root"] = ("sha256:" + root_key().hex()) == ref(ROOT_SEED)

    kf = uor_key_fn(page)
    cases["edge_key"] = ("sha256:" + kf(toks).hex()) == ref(tuple(toks[:page]))

    chain = chain_page_keys(toks, page)
    prev = root_key()
    ok = len(chain) == 1
    for i, k in enumerate(chain):
        expect = ref((prev, tuple(toks[i * page : (i + 1) * page])))
        ok &= ("sha256:" + k.hex()) == expect
        prev = k
    cases["chained_keys"] = ok

    cases["identity_records"] = (
        "sha256:" + identity({"v": 1, "t": "anchor", "k": chain[-1]}).hex()
    ) == ref({"v": 1, "t": "anchor", "k": chain[-1]})

    all_ok = all(cases.values())
    print(json.dumps({"gate": "FT-identity-conformance", "all_match": all_ok, "cases": cases}))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
