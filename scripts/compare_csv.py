#!/usr/bin/env python3
"""Numerically compare two latency/runtime CSV curves.

The common artifact format is ``L,runtime`` with both values in ns. Some
wrappers use ``L_ns`` or ``runtime_ns``/``runtime_ms``; those aliases are
detected automatically. By default, the expected curve is linearly
interpolated onto the actual curve's latency points so solver critical
points can be compared with sampled packaged sweeps.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


X_ALIASES = ("L", "L_ns", "latency", "latency_ns")
Y_ALIASES = ("runtime", "runtime_ns", "T", "time_ns")


def _column(df: pd.DataFrame, explicit: str | None, aliases: tuple[str, ...]) -> str:
    if explicit:
        if explicit not in df.columns:
            raise SystemExit(f"column {explicit!r} not found; available: {list(df.columns)}")
        return explicit
    for name in aliases:
        if name in df.columns:
            return name
    raise SystemExit(f"none of {aliases} found; available: {list(df.columns)}")


def _runtime_values(df: pd.DataFrame, y_col: str) -> np.ndarray:
    values = df[y_col].astype(float).to_numpy()
    if y_col == "runtime_ms":
        values = values * 1e6
    return values


def _load(path: Path, x_col: str | None, y_col: str | None) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(path)
    x_name = _column(df, x_col, X_ALIASES)
    y_name = _column(df, y_col, Y_ALIASES + ("runtime_ms",))
    out = pd.DataFrame({"x": df[x_name].astype(float), "y": _runtime_values(df, y_name)})
    out = out.dropna().sort_values("x")
    out = out.groupby("x", as_index=False)["y"].mean()
    return out["x"].to_numpy(), out["y"].to_numpy()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expected", required=True, type=Path)
    ap.add_argument("--actual", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--label", default="comparison")
    ap.add_argument("--expected-x-col")
    ap.add_argument("--expected-y-col")
    ap.add_argument("--actual-x-col")
    ap.add_argument("--actual-y-col")
    ap.add_argument("--points", choices=("actual", "expected", "intersection"), default="actual",
                    help="Latency points used for comparison. Default: actual.")
    args = ap.parse_args()

    exp_x, exp_y = _load(args.expected, args.expected_x_col, args.expected_y_col)
    act_x, act_y = _load(args.actual, args.actual_x_col, args.actual_y_col)

    if args.points == "actual":
        xs = act_x[(act_x >= exp_x.min()) & (act_x <= exp_x.max())]
        actual = np.interp(xs, act_x, act_y)
        expected = np.interp(xs, exp_x, exp_y)
    elif args.points == "expected":
        xs = exp_x[(exp_x >= act_x.min()) & (exp_x <= act_x.max())]
        actual = np.interp(xs, act_x, act_y)
        expected = np.interp(xs, exp_x, exp_y)
    else:
        common = sorted(set(exp_x).intersection(set(act_x)))
        if not common:
            raise SystemExit("no exact shared latency points; use --points actual or --points expected")
        xs = np.array(common, dtype=float)
        actual = np.interp(xs, act_x, act_y)
        expected = np.interp(xs, exp_x, exp_y)

    if len(xs) == 0:
        raise SystemExit("no comparison points within both curve ranges")

    abs_diff = actual - expected
    rel_diff_pct = np.where(expected != 0, abs_diff / expected * 100.0, np.nan)
    detail = pd.DataFrame({
        "L": xs,
        "expected_runtime": expected,
        "actual_runtime": actual,
        "abs_diff": abs_diff,
        "rel_diff_pct": rel_diff_pct,
    })

    summary = {
        "label": args.label,
        "expected": str(args.expected),
        "actual": str(args.actual),
        "points": args.points,
        "n_points": int(len(detail)),
        "max_abs_diff_ns": float(np.nanmax(np.abs(abs_diff))),
        "mean_abs_diff_ns": float(np.nanmean(np.abs(abs_diff))),
        "max_abs_rel_diff_pct": float(np.nanmax(np.abs(rel_diff_pct))),
        "mean_abs_rel_diff_pct": float(np.nanmean(np.abs(rel_diff_pct))),
        "min_L": float(np.min(xs)),
        "max_L": float(np.max(xs)),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    detail_path = args.out_dir / f"{args.label}_detail.csv"
    summary_path = args.out_dir / f"{args.label}_summary.json"
    detail.to_csv(detail_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"[compare-csv] wrote {detail_path}")
    print(f"[compare-csv] wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
