import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copy(source: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / source, target)


def test_full_run_plotting_rejects_missing_results(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/plot_full_run.py",
            "--scratch",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode != 0
    assert "Full-run plotting requires fresh numerical outputs" in result.stderr
    assert "fig5/out/composed_runtime.csv" in result.stderr


def test_full_run_plotting_uses_scratch_outputs(tmp_path):
    copy(
        "data/output/final_plots/data/ar_128m_16n_ch1/latency_full_runtime.csv",
        tmp_path / "fig3/ch1/composed_runtime.csv",
    )
    copy(
        "data/output/final_plots/data/ar_128m_16n_ch1/bw_composite_runtime.csv",
        tmp_path / "fig3/ch1/bandwidth_sensitivity.csv",
    )
    copy(
        "data/output/final_plots/data/ar_128m_16n_auto/latency_full_runtime.csv",
        tmp_path / "fig3/auto/composed_runtime.csv",
    )
    copy(
        "data/output/final_plots/data/ar_128m_16n_auto/bw_composite_runtime.csv",
        tmp_path / "fig3/auto/bandwidth_sensitivity.csv",
    )
    copy(
        "data/output/final_plots/data/mixed_16n_ch1/latency_full_runtime.csv",
        tmp_path / "fig4/composed_runtime.csv",
    )
    copy(
        "local_artifact/results/fig5/composed_runtime.csv",
        tmp_path / "fig5/out/composed_runtime.csv",
    )
    copy(
        "data/workspaces/llama7b_n32_spcl_20260407/output/comp/sweeps/"
        "composed_runtime.csv",
        tmp_path / "fig6_latency/composed_runtime.csv",
    )
    copy(
        "data/workspaces/llama7b_n32_spcl_20260407/output/"
        "bw_sensitivity_l4us_composition_exact_goal/bandwidth_sensitivity.csv",
        tmp_path / "fig6_bandwidth/bandwidth_sensitivity.csv",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/plot_full_run.py",
            "--scratch",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=True,
        timeout=120,
    )

    figure_dir = tmp_path / "figures"
    for name in (
        "fig3_sensitivity_1x4.pdf",
        "fig_mixed_16n_ch1.pdf",
        "fig5_llama7b.pdf",
        "fig_3x3_sensitivity.pdf",
    ):
        assert (figure_dir / name).is_file()

    manifest = json.loads((tmp_path / "run_manifest.json").read_text())
    assert manifest["figures"]["3"]["input_stage"].startswith("fresh_")
    assert manifest["figures"]["5"]["fresh_inputs"][0]["path"].endswith(
        "fig5/out/composed_runtime.csv"
    )
    assert (
        manifest["figures"]["1"]["input_stage"]
        == "plot_from_supplied_numerical_data"
    )
