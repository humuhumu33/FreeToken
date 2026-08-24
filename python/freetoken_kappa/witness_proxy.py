"""Plane III — the sealing witness proxy (gate FT4).

A reverse proxy for any OpenAI-compatible engine (FreeToken's daemon, vLLM,
llama.cpp — the seam is the API, not the engine). Every /v1/chat/completions
round-trip is sealed into a κ-store:

    seal = {v, t:"api-seal", req: identity(canonical request),
            resp_kappa: blake3(response bytes), engine, model, ts}

identity() is the uor-addr rule; response bytes are content-addressed with
blake3 and stored, so the auditor re-derives both sides offline: a seal
whose stored response bytes no longer derive resp_kappa — or whose own
bytes don't derive their filename label — is REFUSED.

Scope note (honest): API-boundary seals bind request↔response *content*.
Token-level witness chains (the vllm-kappa form) need engine internals;
at a proxy this is the strongest binding available, and it is engine-portable.

Run:   uvicorn freetoken_kappa.witness_proxy:app --port 8001
Env:   KAPPA_UPSTREAM (default http://localhost:8000)
       KAPPA_PROXY_STORE (default ~/kappa-proxy-store)
Audit: python -m freetoken_kappa.witness_proxy audit <store>
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import blake3
import cbor2


def identity(obj) -> bytes:
    return hashlib.sha256(cbor2.dumps(obj, canonical=True)).digest()


class ProxyStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        label = blake3.blake3(data).hexdigest()
        p = self.root / label[:2]
        p.mkdir(exist_ok=True)
        f = p / label
        if not f.exists():
            tmp = f.with_suffix(".tmp." + str(os.getpid()))
            tmp.write_bytes(data)
            tmp.replace(f)
        return "blake3:" + label

    def iter_objects(self):
        for f in sorted(self.root.glob("??/*")):
            if f.suffix:
                continue
            yield f.name, f.read_bytes()


def seal_roundtrip(store: ProxyStore, engine: str, req_body: bytes, resp_body: bytes) -> str:
    try:
        req = json.loads(req_body)
    except ValueError:
        req = {"_raw": req_body}
    resp_label = store.put(resp_body)
    seal = {
        "v": 1,
        "t": "api-seal",
        "req": identity(req),
        "resp_kappa": resp_label,
        "engine": engine,
        "model": req.get("model") if isinstance(req, dict) else None,
        "ts": int(time.time()),
    }
    return store.put(cbor2.dumps(seal, canonical=True))


def audit(store_dir: str | Path) -> int:
    store = ProxyStore(store_dir)
    objects: dict[str, bytes] = {}
    corrupt = []
    for name, data in store.iter_objects():
        if blake3.blake3(data).hexdigest() != name:
            corrupt.append(name)
            continue
        objects[name] = data
    seals, refused = 0, 0
    for name, data in objects.items():
        try:
            rec = cbor2.loads(data)
        except Exception:
            continue
        if not (isinstance(rec, dict) and rec.get("t") == "api-seal"):
            continue
        seals += 1
        resp = rec["resp_kappa"].split(":", 1)[1]
        if resp not in objects:
            refused += 1
            print(f"REFUSED seal blake3:{name[:16]}…: response object "
                  f"{rec['resp_kappa'][:23]}… missing or corrupt")
    for name in corrupt:
        print(f"REFUSED blake3:{name[:16]}…: bytes do not derive their label")
    ok = not corrupt and not refused
    print(f"{seals - refused}/{seals} seals verified"
          + ("" if ok else f" · {len(corrupt)} corrupt object(s)"))
    return 0 if ok else 1


def _build_app():
    import httpx
    from fastapi import FastAPI, Request, Response

    upstream = os.getenv("KAPPA_UPSTREAM", "http://localhost:8000")
    store = ProxyStore(os.getenv("KAPPA_PROXY_STORE",
                                 str(Path.home() / "kappa-proxy-store")))
    app = FastAPI(title="kappa witness proxy")
    client = httpx.AsyncClient(base_url=upstream, timeout=300.0)

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def relay(path: str, request: Request):
        body = await request.body()
        r = await client.request(
            request.method, "/" + path, content=body,
            headers={k: v for k, v in request.headers.items()
                     if k.lower() not in ("host", "content-length")},
        )
        if request.method == "POST" and path.rstrip("/").endswith(
            ("chat/completions", "completions", "messages")
        ) and r.status_code == 200:
            seal_roundtrip(store, upstream, body, r.content)
        return Response(content=r.content, status_code=r.status_code,
                        media_type=r.headers.get("content-type"))

    return app


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "audit":
        sys.exit(audit(sys.argv[2]))
    print("usage: audit <store> | uvicorn freetoken_kappa.witness_proxy:app", file=sys.stderr)
    sys.exit(2)
else:
    app = _build_app()
