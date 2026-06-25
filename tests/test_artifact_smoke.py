import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cmd(*args, timeout=90):
    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    return subprocess.run(
        [str(a) for a in args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=True,
    )


def test_expected_packaged_inputs_exist():
    expected = [
        "requirements.txt",
        "reproduce_all.py",
        "data/traces/demo_allreduce_16r_1MiB.goal",
        "data/output/grok_final/grok_N1024_latency_sweep.csv",
        "data/output/vllm_llama8b_128tok/latency_runtime.csv",
        "tools/LogGOPSim/Makefile",
        "pipeline/demo.py",
        "pipeline/run_monolithic_points.py",
        "pipeline/reproduce_fig5_from_nsys.sh",
        "scripts/grok_node_scaling.py",
    ]
    for rel in expected:
        path = ROOT / rel
        assert path.exists(), rel
        assert path.stat().st_size > 0, rel


def test_reproduce_all_list_works():
    result = run_cmd(sys.executable, "reproduce_all.py", "--list")
    assert "fig01_sensitivity_maps.py" in result.stdout
    assert "fig10_jitter.py" in result.stdout


def test_artifact_check_quick_path():
    result = run_cmd(
        sys.executable,
        "scripts/check_artifact.py",
        "--skip-figure",
        timeout=120,
    )
    assert "Artifact check passed" in result.stdout


def test_single_packaged_figure_generation():
    result = run_cmd(sys.executable, "reproduce_all.py", "--only", "7", timeout=90)
    assert "fig07_memory_scaling.py" in result.stdout
    assert (ROOT / "figures" / "fig6_grok_memory.pdf").exists()


def test_tier_c_wrappers_have_safe_dry_runs(tmp_path):
    goal = ROOT / "data" / "traces" / "demo_allreduce_16r_1MiB.goal"
    run_cmd(
        sys.executable,
        "pipeline/run_monolithic_lp.py",
        "--goal",
        goal,
        "--out",
        tmp_path / "full_runtime.csv",
        "--dry-run",
        "--allow-tag-match",
    )
    run_cmd(
        sys.executable,
        "pipeline/run_monolithic_points.py",
        "--goal",
        goal,
        "--out",
        tmp_path / "points_runtime.csv",
        "--latencies",
        "0",
        "4000",
        "--dry-run",
        "--allow-tag-match",
    )

    sqlite_dir = tmp_path / "sqlite"
    sqlite_dir.mkdir()
    (sqlite_dir / "node0.sqlite").write_text("", encoding="utf-8")
    run_cmd(
        sys.executable,
        "pipeline/run_nccl_generator.py",
        "--sqlite-dir",
        sqlite_dir,
        "--out-dir",
        tmp_path / "analysis",
        "--dry-run",
    )

    result = run_cmd("bash", "pipeline/reproduce_fig5_from_nsys.sh", "--dry-run")
    assert "Dry run complete" in result.stdout


def test_lp_wrappers_fail_cleanly_for_missing_sidecar(tmp_path):
    goal = ROOT / "data" / "traces" / "demo_allreduce_16r_1MiB.goal"

    missing_result = subprocess.run(
        [
            sys.executable,
            "pipeline/run_composite_lp.py",
            "--goal",
            str(goal),
            "--out",
            str(tmp_path / "composed_runtime.csv"),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert missing_result.returncode == 2
    assert "--comm-dep is required" in missing_result.stderr

    empty_sidecar = tmp_path / "empty_comm_dep.csv"
    empty_sidecar.write_text("", encoding="utf-8")
    empty_result = subprocess.run(
        [
            sys.executable,
            "pipeline/run_monolithic_lp.py",
            "--goal",
            str(goal),
            "--comm-dep",
            str(empty_sidecar),
            "--out",
            str(tmp_path / "full_runtime.csv"),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert empty_result.returncode == 2
    assert "comm_dep file is empty" in empty_result.stderr
