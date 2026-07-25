"""
LLAMP-NCCL: Latency sensitivity analysis for NCCL collectives.

Solves per-collective LPs, extracts compact max-of-affines representations,
caches results by collective signature, and composes them into program-level
models for fast what-if analysis.
"""
