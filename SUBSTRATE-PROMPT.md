# SUBSTRATE-PROMPT — Removing FreeToken's Limits on the κ-Addressable Substrate

You are an engineering agent. Target machine: **ASUS ROG Flow Z13 — AMD Ryzen
AI MAX 390 (Strix Halo), Radeon 8050S iGPU, 32 GB unified LPDDR5X-8000
(~256 GB/s), no NVIDIA silicon, FreeToken Desktop v0.2.0-beta.14 running
(daemon :1900, OpenAI-compatible API :1919), WSL2 carrying the κ toolchain
(vllm-kappa venv, uor-addr binding, kappa stores).** Disk is nearly full
(918/954 GB) — every phase that downloads a model must first clear space and
say how much.

Mission: use the κ-addressable substrate to remove FreeToken's measured
limitations with the **smallest possible change** — a file written next to
the engine beats a patch, a patch beats a fork, and an *encoding switch*
that leaves the engine untouched beats everything. Sister programs, whose
MEASUREMENT-LOGs are prior art you must read first:
`humuhumu33/vllm-kappa` (all gates), this fork's `KAPPA-UOR-PROMPT.md`
(FT1 + Planes I/III done). The two-function discipline is law:
identity = sha256(canonical CBOR) [uor-addr], content = blake3(bytes)
[kappa-registry]. No third hash, ever.

## 0. Study set — six repos, one load-bearing insight each

| Repo | The insight you are borrowing |
|---|---|
| `Hologram-Technologies/hologram-os` | A whole OS ships as ONE signed κ and boots by `mount(κ)` with offline verify + rollback. Pattern: *an artifact's identity is its content; booting is resolving.* Apply to models. |
| `Hologram-Technologies/hologram` | Content-addressed memoized compute: memo hit is **flat ~157 ns regardless of operand size — 1.27M× over recompute** (validated on Zen 5). Pattern: *recomputation is a cache miss.* |
| `Hologram-Technologies/hologram-ai` | HF models already compile into κ-form `.holo` archives and run client-side/native. The model-as-κ-object pipeline **exists**; do not reinvent it. |
| `UOR-Foundation/uor-r4` | R⁴ compiles a teacher model's behavior ONCE into integer lookup tables + a scored graph; serving = bit ops and table reads — no matmul, no FP, no GPU — every answer carrying a **content-addressed witness** and honest **typed abstention**. The endpoint of "pay the math once." Quality is research-grade and disclosed — treat it as such. |
| `UOR-Foundation/uor-matmul` | Matmul-as-retrieval kernels, i32 164× vs ndarray (replicated on Zen 5). Bridges hologram's memo law down to tile granularity. |
| `UOR-Foundation/kappa-registry` | BLAKE3 CAS + tags-as-naming + verify-on-read. The shared tier every device resolves against. |

## 1. The limitations to remove (measured on this machine, 2026-08-24)

- **L-A Capacity**: weights must be RAM+VRAM-resident. 19.4 GiB fits;
  DeepSeek-V4-Flash (145 GiB) reads "Insufficient RAM" on a 31 GiB box.
- **L-B MoE-only economics**: dense models get nothing from expert offload.
- **L-C Decode ceiling**: bandwidth-bound GEMV ≈ 256 GB/s ÷ active bytes
  (~100–150 tok/s for A3B-class NVFP4) — degraded by expert-LRU misses.
- **L-D TTFT**: cold prefill is a full dense pass; warm reuse rests on
  *heuristic* anchor checkpoints (positional, session-local, unverified).
- **L-E Zero verification**: weights, experts, anchors, outputs — all
  anonymous mutable bytes; nothing refuses anything.

## 2. The substrate theses — limitation → lever

**One sentence for the whole program: FreeToken's limits all follow from
treating weights, KV, and compute as anonymous bytes that must be resident;
κ makes them named, verified, shared, memoized objects — so residency
becomes cache policy, recomputation becomes retrieval, and every tier
(VRAM / RAM / SSD / registry / another device) serves one address space.**

| Kill | Lever | Borrowed from |
|---|---|---|
| L-A | Experts as κ-pages faulted from SSD/registry on route, verified on read, LRU-evicted. "Insufficient RAM" becomes "cold cache." Power-law expert reuse is the physics that makes it work. | kappa-registry + hologram-os |
| L-D | Anchor checkpoints keyed by **content** (`freetoken_kappa.identity.chain_page_keys` — built, conformant) → exact-match, cross-session, cross-device prefix reuse. The vLLM lane measured the same move at **5.1× TTFT**. | vllm-kappa G3 |
| L-C | Recomputation → retrieval, at three rungs: (1) sequence-level κ-drafting (measured 4.4× decode-bound), (2) expert-GEMV memoization — NVFP4 is a 4-bit integer domain, so input-tile recurrence is *measurable, maybe exploitable*, (3) tile-level matmul-as-retrieval. Rung 2–3 are hypotheses: **measure recurrence before building mechanism.** | hologram + uor-matmul |
| L-E | Model = ONE signed κ (FT1 manifest + hologram-os boot discipline); page-in verify at blake3 3.6 GB/s ≫ any stream rate here; witness proxy on :1919 (FT4 form, already passing against vLLM). | hologram-os + FT1/FT4 |
| L-B + the FLOP economy itself | **The encoding switch**: compile the same HF model through hologram-ai/R⁴ into κ-form and serve by integer retrieval with witnesses and abstention — the engine is not patched, it is *bypassed for the workloads where retrieval wins*. | uor-r4 + hologram-ai |

## 3. Seam honesty — three integration planes on THIS machine

1. **File plane (zero engine change — works against the Desktop app
   today)**: FreeToken reads FTW dirs and model folders from disk. κ tools
   act AT REST: manifest, verified provisioning (registry → local, verify,
   place), dedup, signed-model identity, anchor export. The Desktop app
   never knows.
2. **API plane (zero engine change)**: everything at :1919 — witness proxy,
   baseline benching, sequence-level reuse orchestration.
3. **Engine plane (needs the OSS engine — Linux/CUDA today, so on this
   box it is measurement-limited)**: page-in verify hook, κ-KV injection,
   GEMV memoization. Prototype what is measurable, document what needs
   hardware, never pretend otherwise.

## 4. Phases and gates (rules of evidence per vllm-kappa: load controls,
isolated runs, counted byte-identity, negatives published with pride)

| Gate | Question | Method | Green / Kill |
|---|---|---|---|
| **S0 baseline** | What does this box actually do? | Free ≥25 GB disk; download Qwen3.6-35B-A3B NVFP4 in Desktop; bench TTFT + tok/s via :1919 (cold, warm, agentic-edit) with the witness proxy already in front | numbers logged; proxy seals verify — this is also FT4 completed on FreeToken itself |
| **S1 signed model** | Can the model boot only as its κ? | κ-manifest the downloaded model dir (FT1 tool); provision-verify-place flow; tamper → Desktop must be handed a refused dir, not a poisoned one | 100% verify at ≥3 GB/s; refusal names the tensor |
| **S2 recurrence census** | Is decode-time retrieval real here? | instrument at file/API plane only: capture expert-route + activation-tile distributions from real chat traffic; compute hit-rate curves vs table size | **measurement before mechanism**: publish the curve; if tile recurrence <5% at feasible table sizes, rungs 2–3 die honestly and the census is the deliverable |
| **S3 anchor κ-export** | Do content-keyed anchors beat positional ones? | chain_page_keys over real conversations; measure exact-prefix recurrence across sessions/edits vs FreeToken's own anchor hits | κ hit-rate ≥ anchor hit-rate; any cross-SESSION hit is a win positional anchors cannot score |
| **S4 capacity escape** | Can a >31 GiB model serve from partial residency? | OSS-engine plane: route-locality replay from S2 traces against a κ-paged expert store (simulation on this box; live on CUDA hardware) | projected tok/s ≥ 0.5× resident-serving at ≤50% residency ⇒ L-A falls; else publish the locality curve that says why not |
| **S5 the encoding switch** | What does R⁴/hologram-ai give up and gain vs FreeToken on the SAME model? | compile a small teacher (Qwen3-1.7B-class) via the hologram-ai/R⁴ pipeline; race on identical prompts: tok/s, joules if measurable, witness coverage, abstention rate, and an honest quality eval | report the triangle (speed / verifiability / quality) with no thumb on the scale; R⁴'s typed abstention counted as a FEATURE, not a failure |

## 5. Non-negotiables
- Minimal-diff ladder enforced per phase: file < API < patch < fork; an
  encoding switch that leaves the engine untouched outranks all patches.
- Every perf number carries the machine-load control; every identity is
  re-derivable by the uor-addr reference binding (installed on this box).
- The WSL VM must be sized DOWN (8 GB) or shut off before Desktop benches —
  it was measured stealing 16 GB from the unified pool.
- Traps: vllm-kappa T1–T14, KAPPA-UOR FT-T1, and the host's own
  (two pythons — always `python -m pip`; pkill self-match — use
  `fuser -k PORT/tcp`; WSL session flakes — retry once after 10 s).
- Append results to this fork's MEASUREMENT-LOG in the dated,
  retraction-honest style. The log is the product.
