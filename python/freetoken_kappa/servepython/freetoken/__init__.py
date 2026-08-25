"""PYTHONPATH shadow of the `freetoken` package (κ serve interception).

First on sys.path for any interpreter the daemon spawns. Two duties:
- extend __path__ into the REAL installed package, so every genuine
  submodule (freetoken.daemon.*, …) keeps resolving — the daemon itself
  runs unharmed under this shadow;
- let `freetoken.cli` (the serve entrypoint the daemon spawns with
  ``-m freetoken.cli serve --model … --port …``) resolve to OUR cli.py,
  which launches the κ-shim over vLLM instead of the CUDA engine.
"""

import os

_REAL = os.path.join(
    os.path.expanduser("~"),
    "AppData", "Local", "FreeToken", "venv", "Lib", "site-packages", "freetoken",
)
if os.path.isdir(_REAL):
    __path__.append(_REAL)
