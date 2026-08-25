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

## 2026-08-24 — THE UX SWAP: FreeToken Desktop adopts a κ-verified vLLM

Zero patches, zero impostors: the daemon's own ADOPTION mechanism
(serve.json + `is_ft_serve_on_port`) attaches it to any process satisfying
the serve identity. `freetoken_kappa/ft_shim.py serve --port 1919`
satisfies it by construction, answers the daemon's two probe contracts
(`/health`, `/v1/stats`), 404s `prepare-stop` into the handled legacy path,
and forwards `/v1/*` to the κ-connector vLLM in WSL with every round-trip
sealed. Result, all from the REAL daemon:

    /engine/status → {"running":true,"adopted":true,
        "model":"Qwen2.5 · vLLM · κ-verified","port":1919}
    /engine/stats  → {"kappaSeals":1,"engine":"vLLM (kappa-connector,
        verified)","reachable":true}

Chat via :1919 answered; offline audit: 1/1 seals verified. FreeToken's
face, κ-verified heart — engine swapped with ONE json file and one shim
process. En route, the day's disk-zero was attributed (4 GB of WSL crash
diagnostics in Temp\DiagOutputDir + WSL swap.vhdx creation failing at 0
free) — fixed by deleting diagnostics and `swap=0` in .wslconfig.

Trap S-T2: PowerShell Start-Process -ArgumentList mangles non-ASCII args
(the κ in --model-label) — let defaults carry unicode, or pass via env.
Trap S-T3: the daemon's single-instance lock (~/.freetoken/daemon/
daemon.pid) is the safety: the Desktop app's own spawn attempt exits
AlreadyRunning and the GUI attaches to whichever daemon holds the lock.

## 2026-08-25 — THE LIBRARY UNLOCK: GUI Start button ignites the κ-engine

The Chat tab gates on the GUI-side LIBRARY (a models-dir scan recognizing
`freetoken_weight.json`), not on engine status. Unlock, zero upstream edits:

1. **Planted library model**: `~/.freetoken/models/Qwen2.5-0.5B-vLLM-kappa/`
   written by FreeToken's OWN FTWWriter (valid FTW index + config.json) —
   honestly labeled; the real weights live in the vLLM engine it fronts.
2. **Serve interception**: daemon restarted with `--serve-python` = the
   host python + a PYTHONPATH shadow package `freetoken/` whose __init__
   path-extends into the real installed package (daemon's own imports
   unharmed) while `freetoken.cli` resolves to our launcher — so the
   daemon's spawn (`-m freetoken.cli serve --model … --port …`) starts the
   κ-shim as a FIRST-CLASS MANAGED CHILD (adopted:false, supervised,
   restartable from the GUI).
3. Proof: `/engine/start {model: <library path>, port: 1919}` →
   running:true pid-managed; chat answered; kappaSeals counting;
   `/engine/stats` renders the κ fields.

Traps: S-T4 — /engine/start JSON rejects backslash-escaped Windows paths;
send forward slashes. S-T5 — the PYTHONPATH shadow MUST path-extend into
the real package or the daemon kills itself at import.
