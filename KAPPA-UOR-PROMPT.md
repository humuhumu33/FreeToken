# KAPPA-UOR-PROMPT — FreeToken on the UOR Universal Lossless Encoding Standard

Mission: bring FreeToken — an edge-native MoE serving engine — onto UOR
content addressing with the **smallest possible diff against upstream**, and
measure what it buys. Sister program to `humuhumu33/vllm-kappa` (vLLM lane),
whose MEASUREMENT-LOG carries the ground truth this spec builds on; read it
first. The UOR doctrine and the two-function discipline are unchanged:

- **identity(x)** = `sha256(canonical_cbor(x))` — uor-addr's `cbor_address`
  rule (byte-verified against the reference crate on 2026-08-24).
- **kappa(b)** = `blake3(b)` — kappa-registry's blob rule.

Nothing else. Any third hash or non-canonical serialization in an identity
path is wrong by definition.

## Why FreeToken is the *better* second lane

FreeToken's entire performance story is **unverified byte-artifact
management**: experts paged VRAM←RAM←SSD by a global LRU, a custom aligned
weight format (FTW), anchor-checkpointed KV/recurrent state for agentic
edits. Every one of those is a content-addressing shape-match. And it holds
the case vLLM couldn't: **MoE experts are identical bytes fleet-wide**, so
the U4 dedup negative (0% across full finetunes) inverts here — expert
streaming from a shared κ-registry is dedup-positive by construction.

## The seams (found 2026-08-24; upstream commit at fork time)

1. **FTW** (`python/freetoken/checkpoint/ftw.py`): one logical byte region;
   every tensor starts 4096-aligned and padded; index
   `freetoken_weight.json` lists `tensors[]` (name, kind, dtype, shape,
   global_off, nbytes) + `shards[]`. Expert banks are per-layer entries
   (`…#L00042`, `kind="experts_bank"`). **A κ-manifest's natural home**:
   aligned regions are clean hash units; the index is extensible JSON; the
   byte region never needs touching.
2. **Radix prefix cache** (`python/freetoken/kvcache/radix_cache.py`): the
   constructor takes an **injected `key_fn`**. A pluggable identity seam —
   the analog of vLLM's `prefix_caching_hash_algo`, better: no config enum
   to patch, just pass the UOR key function at construction.
3. **Daemon proxy** (`python/freetoken/daemon/proxy.py`): OpenAI/Anthropic
   API traffic transits here — the witness sidecar's home. The vllm-kappa
   witness chain (engine fingerprint + sampling fingerprint + token chain →
   seal) is engine-agnostic and reuses verbatim.
4. **`FTWReader.read_into`**: the single choke point through which every
   expert bank enters memory. One hook = verify-on-page-in — a poisoned
   expert is refused before it ever computes.

## The plan — additive package, zero upstream edits until measured

Everything lands in `python/freetoken_kappa/` (this branch). Upstream
`freetoken/*` files are not modified until a gate proves the hook is worth
its diff; even then the target is ≤10 lines per seam.

### Plane II first (weights — the FreeToken-specific win)
- `ftw_kappa.py`: standalone (no freetoken imports) manifest tool over the
  FTW index — per-tensor and per-expert-bank-layer `blake3:` labels, an
  additive `kappa` block in (a copy of) the index, manifest identity by the
  uor-addr rule, `verify` = Certified | Witness naming the exact tensor.
- Later: the `read_into` page-in verify hook; the κ-registry as shared
  expert store (fleet lane).

### Plane I (identity)
- UOR `key_fn` for the radix cache: chained `sha256_cbor` block keys — the
  same `chain_block_keys` doctrine as vllm-kappa, adapted to FreeToken's
  page granularity. Anchor-checkpoint snapshots get content-derived keys in
  the same pass.

### Plane III (witness)
- Sealing middleware for `daemon/proxy.py`: per-request witness chain +
  seal into a κ-store; offline auditor reused from vllm-kappa.

## Gates (rules of evidence per vllm-kappa MEASUREMENT-LOG: controls on
every perf rep, isolated boots, counted byte-identity, negatives published)

| Gate | Question | Green |
|---|---|---|
| **FT1** (runnable on any box) | Manifest + verify + refuse on a real-writer FTW checkpoint | 100% verify; single-bit tamper → refusal naming the tensor; GB/s reported |
| **FT2** (needs RTX box) | Verify-at-load cost on a real model dir | ≤15% of load, tamper refused |
| **FT3** (RTX) | Page-in verify overhead vs expert stream rate | blake3 ≥ SSD/PCIe stream rate ⇒ verify hides in the copy; report the ratio |
| **FT4** (RTX or CPU-serve) | Witness sidecar overhead at the proxy | within noise; seals audit offline; tamper refused |
| **FT5** (two hosts) | Fleet expert dedup + κ-registry pull | ≥90% expert-bank κ overlap between two installs of one model ⇒ shared store serves the fleet; measure pull-vs-local-SSD latency |

Kill criteria: FT3 blake3 slower than the stream rate on the target box ⇒
page-in verify costs latency — report the number and gate it behind a flag.
FT5 overlap <90% (quantization/repack nondeterminism) ⇒ **that is a
finding**: FTW conversion is not canonical; the fix is a deterministic
repack, and the finding is worth more than the feature.

## Status 2026-08-24 (all on a no-RTX box)

- **FT1 PASS**: real-FTWWriter checkpoint certifies; 1-bit tamper refused
  naming `experts.gate_up#L00002`; 3.6 GB/s (`run_ft1.py`).
- **Plane I built + conformant**: `identity.py` (drop-in `uor_key_fn` for
  `_get_key_fn`, chained exportable page keys); 4/4 shapes byte-identical
  vs the uor-addr reference crate (`run_identity_conformance.py`).
- **FT4 PASS in its CPU-serve form**: `witness_proxy.py` sealed live
  OpenAI-API traffic (3/3 verified); 1-bit tamper → double refusal (object
  + referencing seal). Upstream engine in the test was vLLM — the sidecar
  is engine-portable by construction. Overhead measurement + FreeToken
  daemon as upstream: pending an RTX box, with FT2/FT3/FT5.
- Trap FT-T1: `from __future__ import annotations` + function-local
  `Request` import breaks FastAPI's annotation resolution (params become
  query fields, 422). Keep runtime annotations real in endpoint modules.

## Non-negotiables
- Fork stays mergeable: upstream `main` untouched; work on `kappa` branch.
- Apache-2.0 respected; attribution intact.
- The vllm-kappa traps (T1–T14) apply where analogous; log new ones here.
