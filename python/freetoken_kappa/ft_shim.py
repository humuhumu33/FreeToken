"""The κ serve-shim — FreeToken Desktop's UX over a verified vLLM engine.

Zero patches, zero impostors: FreeToken's daemon has a first-class ADOPTION
mechanism (serve.json + is_ft_serve_on_port). This process satisfies the
adoption identity by construction — argv carries ``serve`` and ``--port``,
the path carries ``freetoken`` — and speaks the two contracts the daemon
probes (`/health`, `/v1/stats`; `/v1/admin/prepare-stop` 404s into the
handled legacy path). Chat traffic (`/v1/*`) forwards to a vLLM upstream
(the κ-connector engine in WSL) and every round-trip is κ-sealed via the
witness-proxy store, so the Desktop GUI renders — truthfully — a running,
verified engine, with seal counts surfaced in its own stats panel.

Run (argv shape matters for adoption):
    python …\\freetoken_kappa\\ft_shim.py serve --port 1919 \
        --upstream http://localhost:8000 --model-label "vLLM+kappa"

Then write serve.json and restart the daemon (see run_s_shim bench notes).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from freetoken_kappa.witness_proxy import ProxyStore, seal_roundtrip  # noqa: E402


def build_app(upstream: str, model_label: str, store_dir: str):
    import httpx
    from fastapi import FastAPI, Request, Response
    from fastapi.middleware.cors import CORSMiddleware

    store = ProxyStore(store_dir)
    app = FastAPI(title="freetoken-kappa serve shim")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["tauri://localhost", "http://tauri.localhost",
                       "http://localhost", "http://127.0.0.1"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    client = httpx.AsyncClient(base_url=upstream, timeout=600.0)
    state = {"started": time.time(), "requests": 0, "seals": 0,
             "prompt_tokens": 0, "completion_tokens": 0}

    @app.get("/health")
    async def health():
        try:
            r = await client.get("/v1/models")
            engine_up = r.status_code == 200
        except httpx.HTTPError:
            engine_up = False
        return {"status": "ok" if engine_up else "starting",
                "model": model_label, "upstream": upstream,
                "kappa": True}

    @app.get("/v1/stats")
    async def stats():
        # Shape matters: the daemon's legacy stop receipt
        # (serve_manager._parse_snapshot) requires model_id, uptime_s, and
        # integer prompt/completion token totals — `requests` must NOT be a
        # scalar (it is inspected as a dict fallback).
        up = time.time() - state["started"]
        return {
            "model_id": model_label,
            "model": model_label,
            "uptime_s": round(up, 1),
            "prompt_tokens_total": state["prompt_tokens"],
            "completion_tokens_total": state["completion_tokens"],
            "requests_total": state["requests"],
            "kappa_seals": state["seals"],
            "kappa_store": store_dir,
            "engine": "vLLM (kappa-connector, verified)",
        }

    # /v1/admin/prepare-stop intentionally absent: the daemon's probe treats
    # 404 as the supported legacy-engine path.

    upstream_model: dict = {"id": None}

    async def _upstream_model_id() -> str | None:
        if upstream_model["id"] is None:
            try:
                r = await client.get("/v1/models")
                upstream_model["id"] = r.json()["data"][0]["id"]
            except Exception:
                return None
        return upstream_model["id"]

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def relay(path: str, request: Request):
        body = await request.body()
        # The GUI names models by its library entry; the upstream serves its
        # own id. Rewrite so any client name maps to the engine actually
        # running (the seal records what was truly served).
        if request.method == "POST" and path.rstrip("/").endswith(
            ("chat/completions", "completions", "messages")
        ):
            real = await _upstream_model_id()
            if real:
                try:
                    doc = json.loads(body)
                    if isinstance(doc, dict):
                        changed = False
                        if doc.get("model") != real:
                            doc["model"] = real
                            changed = True
                        # The GUI sends its catalog ctx (e.g. 32768/262144);
                        # clamp to what this engine was started with so a
                        # generous default can't exceed max_model_len.
                        cap = int(os.environ.get("KAPPA_MAX_TOKENS", "1024"))
                        mt = doc.get("max_tokens")
                        if not isinstance(mt, int) or mt > cap or mt <= 0:
                            doc["max_tokens"] = cap
                            changed = True
                        if changed:
                            body = json.dumps(doc).encode()
                except ValueError:
                    pass
        try:
            r = await client.request(
                request.method, "/" + path, content=body,
                headers={k: v for k, v in request.headers.items()
                         if k.lower() not in ("host", "content-length", "origin")},
            )
        except httpx.HTTPError as exc:
            return Response(content=json.dumps({"error": str(exc)}),
                            status_code=502, media_type="application/json")
        if request.method == "POST" and r.status_code == 200 and \
                path.rstrip("/").endswith(("chat/completions", "completions", "messages")):
            state["requests"] += 1
            seal_roundtrip(store, upstream, body, r.content)
            state["seals"] += 1
            try:
                usage = json.loads(r.content).get("usage", {})
                state["prompt_tokens"] += usage.get("prompt_tokens", 0)
                state["completion_tokens"] += usage.get("completion_tokens", 0)
            except ValueError:
                pass
        return Response(content=r.content, status_code=r.status_code,
                        media_type=r.headers.get("content-type"))

    return app


def write_serve_state(pid: int, port: int, model_label: str, log_path: str) -> str:
    """Persist the adoption record the daemon's readopt() consumes."""
    state_dir = os.path.join(os.path.expanduser("~"), ".freetoken", "daemon")
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "serve.json")
    doc = {"model": model_label, "port": port, "pid": pid,
           "args": ["serve", model_label, "--port", str(port)],
           "starttime": None, "log_path": log_path}
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh)
    os.replace(tmp, path)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("verb", choices=["serve"])  # adoption identity: argv[1] == "serve"
    ap.add_argument("--port", type=int, default=1919)
    ap.add_argument("--upstream", default="http://localhost:8000")
    ap.add_argument("--model-label", default="Qwen2.5 · vLLM · κ-verified")
    ap.add_argument("--store", default=os.path.join(os.path.expanduser("~"), "kappa-shim-store"))
    ap.add_argument("--log", default=os.path.join(os.path.expanduser("~"), "kappa-shim.log"))
    args = ap.parse_args()

    state_path = write_serve_state(os.getpid(), args.port, args.model_label, args.log)
    print(f"serve state written: {state_path} (pid={os.getpid()})", flush=True)

    import uvicorn

    uvicorn.run(build_app(args.upstream, args.model_label, args.store),
                host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
