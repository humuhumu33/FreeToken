# MEASUREMENT-LOG — FreeToken κ lane

Dated, retraction-honest, negatives published with pride. Sister log:
`humuhumu33/vllm-kappa/MEASUREMENT-LOG.md`.

## 2026-08-24 — FT1 + Planes I/III (see KAPPA-UOR-PROMPT.md §Status)

FT1 PASS (manifest/verify/refuse on real-writer FTW, 3.6 GB/s, tamper names
the expert-bank layer) · Plane I 4/4 byte-conformant vs uor-addr crate ·
FT4 CPU-serve form PASS (witness proxy, 3/3 live seals, double refusal) —
upstream engine in that test was vLLM.

## 2026-08-24 — S0 (SUBSTRATE-PROMPT): the machine-truth, a double blocker

Target: ROG Flow Z13 — Ryzen AI MAX 390 (Strix Halo), Radeon 8050S, 32 GB
unified LPDDR5X-8000, FreeToken Desktop v0.2.0-beta.14 (daemon :1900,
API :1919). Findings, all from the daemon's own API:

1. **The daemon API is real and scriptable** — `/checkpoint/start` (HF id →
   download+convert), `/engine/start|switch|status|metrics`, `/bench/run`,
   SSE streaming. No GUI automation needed, ever.
2. **Blocker 1 — no CUDA on this machine kills every backend.**
   `POST /bench/run {args:[]}` → *"benchbw needs a CUDA device to measure
   PCIe bandwidth (both offload and hybrid serve experts to the GPU)"*,
   with the bundled torch reporting `cudaErrorNotSupported … on CPU
   machine`. The Desktop venv ships CUDA-only torch; models.md's own
   backend table routes dense→fused(GPU), MoE→offload/hybrid(GPU), and
   `cpu` computes only cache MISSES on CPU. **FreeToken Desktop on Strix
   Halo is a catalog browser until upstream ships a ROCm/Vulkan/true-CPU
   backend.** The GUI's "Fits in VRAM" badge is a size arithmetic, not a
   runnability check.
3. **Blocker 2 — disk.** C: free = 4.2 GB (measured; the Settings app's
   "36 GB" was stale). Smallest supported checkpoint ≈ 7 GB (gemma-4-12B
   NVFP4-class). Nothing in the catalog can land. Unblock = the WSL VHD
   compaction (~18 GB back, needs one elevated `diskpart /s` the operator
   must run) or operator-chosen deletions. Note: fixing disk does NOT fix
   Blocker 1.

Consequences for the substrate program on this box:
- S0 bench / S2 census / S3 anchor comparison are **hardware-blocked**, not
  design-blocked; they run unchanged the day a CUDA box (or a non-CUDA
  FreeToken backend) appears.
- The κ layers themselves are NOT blocked: FT1 (weights), Plane I
  (identity), FT4 (witness proxy) are all measured and engine-portable —
  the witness proxy passed against vLLM, which remains the only serving
  engine this machine can actually run.
- S5 (the R⁴/hologram-ai encoding switch) is disk-blocked only (~4 GB
  teacher + compile artifacts); it becomes the FIRST runnable substrate
  gate after disk clears, and it needs no CUDA — which on this machine
  makes the "transformerless" path not just elegant but the only native
  frontier-adjacent option.

Trap S-T1: FreeToken Desktop's `/bench/run` args are the `ft bench bw`
argv WITHOUT the subcommand (the endpoint implies it); `--device` takes a
GPU ordinal, not a string.
