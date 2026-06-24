# Legacy Solver Tests

These tests are kept as historical unit tests for the old standalone
`solver/` package, but they are not the artifact's default test path.
They expect `solver/` on `PYTHONPATH`, refer to historical
`mpi-dep-graph/test/data` files that are not shipped in this artifact,
and include assumptions that no longer match the current dependency graph
API.

Use the root-level smoke tests instead:

```bash
python3 -m pytest -q
```

Those tests validate the packaged artifact path, Tier C wrapper safety
surfaces, and one lightweight figure regeneration.

