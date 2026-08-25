"""κ serve entrypoint — what the daemon actually launches.

Receives the daemon's spawn argv (``-m freetoken.cli serve --model PATH
--port N``) and serves that request with the κ-shim over the vLLM upstream:
the FreeToken GUI's own Start button becomes the ignition for a verified
engine, managed as a first-class daemon child (liveness identity holds:
argv carries ``serve`` + ``--port``; the path carries ``freetoken``).
"""

import argparse
import os
import sys

_SHIM_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.abspath(os.path.join(_SHIM_ROOT, "..")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("verb", nargs="?", default="serve")
    ap.add_argument("--model", default="")
    ap.add_argument("--port", type=int, default=1919)
    args, _extra = ap.parse_known_args()

    label = os.path.basename(args.model.rstrip("/\\")) or "vLLM+kappa"
    upstream = os.environ.get("KAPPA_UPSTREAM", "http://localhost:8000")
    store = os.path.join(os.path.expanduser("~"), "kappa-shim-store")

    print(f"[kappa-cli] serving {label} on :{args.port} over {upstream}", flush=True)

    from freetoken_kappa.ft_shim import build_app

    import uvicorn

    uvicorn.run(build_app(upstream, f"{label} · κ-verified", store),
                host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
