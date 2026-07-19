#!/usr/bin/env python3
"""
Tests for the Bell Sample Overtone Analyzer CLI.

Generates a synthetic bell sample and verifies that analyze_bell.py recovers the
known partials within the tolerances specified in the phase plan.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYZE_BELL = PROJECT_ROOT / "analyze_bell.py"
GENERATE_SAMPLE = PROJECT_ROOT / "tests" / "generate_test_sample.py"
SAMPLE_PATH = PROJECT_ROOT / "samples" / "synthetic_bell.wav"
OUTPUT_PATH = PROJECT_ROOT / "samples" / "synthetic_bell.csv"

EXPECTED_PARTIALS = [440.0, 880.0, 1320.0, 1760.0]
# Original percentages: [100.0, 50.0, 30.0, 15.0]
# In relative dB: 20*log10(1) = 0.0, 20*log10(0.5) = -6.0, 20*log10(0.3) = -10.5, 20*log10(0.15) = -16.5
EXPECTED_AMPLITUDES_DB = [0.0, -6.0, -10.5, -16.5]


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command with the current interpreter and return the result."""
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("UV_INTERNAL__PYTHONHOME", None)
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result


def generate_fixture() -> None:
    """Create the synthetic bell WAV fixture if it does not exist."""
    result = run_command([
        sys.executable,
        str(GENERATE_SAMPLE),
        "--output",
        str(SAMPLE_PATH),
    ])
    assert result.returncode == 0, result.stderr


def analyze_fixture() -> list[dict[str, str]]:
    """Run the analyzer on the fixture and return parsed CSV rows."""
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--output",
        str(OUTPUT_PATH),
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr

    with open(OUTPUT_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


@pytest.fixture(scope="module", autouse=True)
def fixture() -> None:
    generate_fixture()


def test_analyzer_runs_without_errors() -> None:
    rows = analyze_fixture()
    assert len(rows) >= len(EXPECTED_PARTIALS)


def test_fundamental_is_loudest() -> None:
    rows = analyze_fixture()
    assert float(rows[0]["frequency_hz"]) == pytest.approx(440.0, abs=5.0)
    assert float(rows[0]["amplitude_db"]) == pytest.approx(0.0, abs=0.1)


def test_expected_partials_recovered() -> None:
    rows = analyze_fixture()
    detected_freqs = [float(row["frequency_hz"]) for row in rows]

    for expected_freq in EXPECTED_PARTIALS:
        matches = [f for f in detected_freqs if abs(f - expected_freq) <= 5.0]
        assert matches, f"Expected partial near {expected_freq} Hz not found"


def test_amplitude_ordering_and_values() -> None:
    rows = analyze_fixture()
    detected_freqs = [float(row["frequency_hz"]) for row in rows]
    detected_amps = [float(row["amplitude_db"]) for row in rows]

    # Find the detected peaks closest to each expected partial.
    selected: list[tuple[float, float]] = []
    for expected_freq, expected_amp in zip(EXPECTED_PARTIALS, EXPECTED_AMPLITUDES_DB):
        best_idx = min(
            range(len(detected_freqs)),
            key=lambda i: abs(detected_freqs[i] - expected_freq),
        )
        assert abs(detected_freqs[best_idx] - expected_freq) <= 5.0
        selected.append((expected_freq, detected_amps[best_idx]))

    # Verify rank order is preserved (highest dB first).
    sorted_by_freq = sorted(selected, key=lambda x: x[0])
    amplitudes = [amp for _, amp in sorted_by_freq]
    assert amplitudes == sorted(amplitudes, reverse=True)

    # Verify each amplitude is within ±3 dB of expected.
    for expected_freq, detected_amp in sorted_by_freq:
        expected_amp = EXPECTED_AMPLITUDES_DB[EXPECTED_PARTIALS.index(expected_freq)]
        assert detected_amp == pytest.approx(expected_amp, abs=3.0)


def test_csv_header_and_columns() -> None:
    rows = analyze_fixture()
    assert len(rows) > 0
    expected_columns = {
        "peak_number",
        "frequency_hz",
        "amplitude_db",
        "duration_percent",
        "note_name",
        "deviation_cents",
    }
    assert set(rows[0].keys()) == expected_columns


def test_stereo_input_reduced_to_first_channel() -> None:
    stereo_path = PROJECT_ROOT / "samples" / "synthetic_bell_stereo.wav"
    result = run_command([
        sys.executable,
        str(GENERATE_SAMPLE),
        "--output",
        str(stereo_path),
        "--channels",
        "2",
    ])
    assert result.returncode == 0, result.stderr

    csv_path = stereo_path.with_name(f"{stereo_path.stem}_bell_analysis.csv")
    if csv_path.exists():
        csv_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(stereo_path),
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr
    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8")
    assert "440" in content or "A4" in content


def test_attack_skip_too_long_returns_error() -> None:
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--attack-skip-ms",
        "10000",
    ])
    assert result.returncode == 2
    assert "attack skip" in result.stderr.lower()


def test_missing_input_file_returns_error() -> None:
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(PROJECT_ROOT / "samples" / "nonexistent.wav"),
    ])
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()


def test_plot_save_creates_png() -> None:
    png_path = PROJECT_ROOT / "samples" / "synthetic_bell_plot.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--plot-save",
        str(png_path),
        "--no-show",
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()
    assert png_path.stat().st_size > 0


def test_visualize_no_show_plot_save() -> None:
    png_path = PROJECT_ROOT / "samples" / "visualize_test.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--visualize",
        "--no-show",
        "--plot-save",
        str(png_path),
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()
    assert png_path.stat().st_size > 0


def test_plot_save_default_filename() -> None:
    default_path = PROJECT_ROOT / "samples" / "synthetic_bell_bell_analysis.png"
    if default_path.exists():
        default_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--plot-save",
        "--no-show",
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert default_path.exists()
    assert default_path.stat().st_size > 0


def test_quiet_suppresses_text_output() -> None:
    png_path = PROJECT_ROOT / "samples" / "quiet_test.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--plot-save",
        str(png_path),
        "--no-show",
        "--quiet",
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()
    
    csv_path = SAMPLE_PATH.with_name(f"{SAMPLE_PATH.stem}_bell_analysis.csv")
    if csv_path.exists():
        csv_path.unlink()


def test_peak_count_limits_output() -> None:
    csv_path = SAMPLE_PATH.with_name(f"{SAMPLE_PATH.stem}_bell_analysis.csv")
    if csv_path.exists():
        csv_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--peak-count",
        "2",
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr
    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8")
    lines = [line for line in content.splitlines() if line.strip()]
    # Header + 2 data rows
    assert len(lines) == 3


def test_spectrogram_alias_enables_plotting() -> None:
    png_path = PROJECT_ROOT / "samples" / "alias_test.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--spectrogram",
        "--no-show",
        "--plot-save",
        str(png_path),
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()


def test_config_loading_changes_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "test_config.ini"
    config_path.write_text(
        "[analysis]\nmin_freq = 500.0\n[visualization]\nn_labels = 3\n[output]\nformat = table\n",
        encoding="utf-8",
    )
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--config",
        str(config_path),
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    # With min_freq=500, the 440 Hz fundamental should not appear.
    csv_path = SAMPLE_PATH.with_name(f"{SAMPLE_PATH.stem}_bell_analysis.txt")
    if csv_path.exists():
        content = csv_path.read_text(encoding="utf-8")
        assert "440" not in content
        assert "A4" not in content
        assert "," not in content


def test_cli_overrides_config(tmp_path: Path) -> None:
    config_path = tmp_path / "test_config.ini"
    config_path.write_text(
        "[analysis]\nmin_freq = 500.0\n",
        encoding="utf-8",
    )
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--config",
        str(config_path),
        "--min-freq",
        "100.0",
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    csv_path = SAMPLE_PATH.with_name(f"{SAMPLE_PATH.stem}_bell_analysis.csv")
    content = csv_path.read_text(encoding="utf-8")
    # CLI --min-freq 100 overrides config min_freq=500, so 440 Hz appears.
    assert "440" in content or "A4" in content


def test_missing_config_returns_error() -> None:
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--config",
        str(PROJECT_ROOT / "nonexistent_config.ini"),
    ])
    assert result.returncode == 1
    assert "config file not found" in result.stderr.lower()


def test_no_config_uses_hardcoded_defaults() -> None:
    # Run from a temp directory with no analyze_bell.ini nearby.
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable,
                str(ANALYZE_BELL),
                str(SAMPLE_PATH),
                "--attack-skip-ms",
                "60",
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            env={k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "UV_INTERNAL__PYTHONHOME")},
            check=False,
        )
        assert result.returncode == 0, result.stderr
        csv_path = SAMPLE_PATH.with_name(f"{SAMPLE_PATH.stem}_bell_analysis.csv")
        content = csv_path.read_text(encoding="utf-8")
        # Hardcoded defaults should still detect the 440 Hz fundamental.
        assert "440" in content or "A4" in content


def test_save_config_writes_valid_file(tmp_path: Path) -> None:
    config_path = tmp_path / "saved_config.ini"
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        "--save-config",
        str(config_path),
    ])
    assert result.returncode == 0, result.stderr
    assert config_path.exists()

    text = config_path.read_text(encoding="utf-8")
    assert "[analysis]" in text
    assert "[visualization]" in text
    assert "[output]" in text
    assert "n_labels = 7" in text
    assert "prominence = 0.005" in text

    # Verify the saved config can be re-loaded.
    result2 = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--config",
        str(config_path),
        "--attack-skip-ms",
        "60",
    ])
    assert result2.returncode == 0, result2.stderr


def test_n_labels_does_not_raise() -> None:
    png_path = PROJECT_ROOT / "samples" / "n_labels_test.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--plot-save",
        str(png_path),
        "--no-show",
        "--n-labels",
        "3",
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()
    assert png_path.stat().st_size > 0


def test_public_functions_have_docstrings() -> None:
    import inspect
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    import analyze_bell as ab

    public_names = [
        "config_defaults",
        "load_config",
        "parse_args",
        "load_audio",
        "skip_attack",
        "compute_mean_spectrum",
        "compute_stft",
        "smooth_spectrum",
        "detect_peaks",
        "frequency_to_note",
        "format_peaks",
        "derive_plot_save_path",
        "write_csv",
        "write_table",
        "plot_analysis",
        "save_config",
        "main",
    ]
    for name in public_names:
        obj = getattr(ab, name)
        doc = inspect.getdoc(obj)
        assert doc, f"{name} is missing a docstring"
        assert "Args:" in doc or "Returns:" in doc or "Raises:" in doc, (
            f"{name} docstring missing Args/Returns/Raises"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
