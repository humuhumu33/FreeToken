"""Plane I — UOR identity for FreeToken's prefix cache and anchors.

Upstream `_get_key_fn(page_size)` keys radix-tree edges by the raw token
tuple of a page — fine for an in-memory dict, meaningless outside the
process. The UOR forms here are:

- `uor_key_fn(page_size)`: drop-in replacement for `_get_key_fn` — the
  edge key becomes `sha256(canonical_cbor(page_token_tuple))` bytes.
  Injection is one constructor argument (`RadixCache`/`HybridRadixCache`
  already accept `key_fn`); no upstream edit required.
- `chain_page_keys(tokens, page_size)`: the exportable identity — chained
  page keys in the vllm-kappa doctrine (`key_i = H((key_{i-1}, page_i))`),
  making a prefix's identity global: two hosts with the same tokens derive
  the same keys, which is what anchor-snapshot export and cross-host prefix
  sharing key on. Byte-conformant with uor-addr's `cbor_address`
  (see run_identity_conformance.py).

Torch-free: token pages are plain int sequences here; the tensor-facing
key_fn does its own minimal conversion.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import cbor2

ROOT_SEED = "freetoken-kappa-root"


def identity(obj) -> bytes:
    """The uor-addr rule: sha256 over RFC-canonical CBOR."""
    return hashlib.sha256(cbor2.dumps(obj, canonical=True)).digest()


def root_key() -> bytes:
    return identity(ROOT_SEED)


def uor_key_fn(page_size: int):
    """Drop-in for `freetoken.kvcache.radix_cache._get_key_fn`."""
    def key_fn(x) -> bytes:
        page = x[:page_size].tolist() if hasattr(x, "tolist") else list(x[:page_size])
        return identity(tuple(int(t) for t in page))
    return key_fn


def chain_page_keys(tokens: Sequence[int], page_size: int) -> list[bytes]:
    """Chained global identity for each FULL page of a token stream."""
    keys: list[bytes] = []
    prev = root_key()
    for i in range(0, (len(tokens) // page_size) * page_size, page_size):
        page = tuple(int(t) for t in tokens[i : i + page_size])
        prev = identity((prev, page))
        keys.append(prev)
    return keys
