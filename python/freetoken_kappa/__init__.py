"""freetoken_kappa — UOR content addressing for FreeToken (KAPPA-UOR-PROMPT.md).

Additive package: imports nothing from `freetoken` at module level, modifies
no upstream file. identity = sha256(canonical CBOR) [uor-addr]; content =
blake3(bytes) [kappa-registry].
"""
