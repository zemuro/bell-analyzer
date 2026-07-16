#!/usr/bin/env python3
"""
Bell Sample Overtone Analyzer CLI.

Reads a single WAV bell sample, skips the noisy attack, averages the magnitude
spectrum over the remaining signal, and emits a ranked list of overtone peaks
with frequency, relative amplitude, nearest 12-TET note, and cent deviation.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import find_peaks, savgol_filter


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    project_root = Path(__file__).resolve().parent
    default_input = project_root / "samples" / "bell.wav"

    parser = argparse.ArgumentParser(
        description="Analyze a bell WAV sample and report its overtone peaks."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=default_input,
        help="Path to input WAV file (default: samples\\bell.wav).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path; prints to stdout if omitted.",
    )
    parser.add_argument(
        "--attack-skip-ms",
        type=float,
        default=100.0,
        help="Duration to skip at the start, in milliseconds (default: 100.0).",
    )
    parser.add_argument(
        "--min-freq",
        type=float,
        default=50.0,
        help="Minimum peak frequency to report, in Hz (default: 50.0).",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=8000.0,
        help="Maximum peak frequency to report, in Hz (default: 8000.0).",
    )
    parser.add_argument(
        "--prominence",
        type=float,
        default=0.01,
        help="Minimum peak prominence in normalized magnitude units (default: 0.01).",
    )
    parser.add_argument(
        "--distance",
        type=int,
        default=50,
        help="Minimum number of bins between peaks (default: 50).",
    )
    parser.add_argument(
        "--smoothing-window",
        type=int,
        default=11,
        help="Window length for spectrum smoothing, odd integer (default: 11).",
    )
    parser.add_argument(
        "--fft-size",
        type=int,
        default=8192,
        help="FFT size per frame (default: 8192).",
    )
    parser.add_argument(
        "--hop-size",
        type=int,
        default=2048,
        help="Hop size between successive frames (default: 2048).",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "table"],
        default="csv",
        help="Output format: csv or table (default: csv).",
    )
    return parser.parse_args(argv)


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file and reduce multi-channel input to the first channel."""
    if not path.exists():
        raise RuntimeError(f"Error: input file not found: {path}")

    try:
        data, sr = sf.read(str(path), dtype="float64")
    except Exception as exc:  # pragma: no cover - library-specific errors
        raise RuntimeError(f"Error: failed to read input file {path}: {exc}")

    if data.ndim > 1:
        data = data[:, 0]
    return data, sr


def skip_attack(data: np.ndarray, sr: int, attack_skip_ms: float) -> np.ndarray:
    """Return the portion of the signal after the attack transient."""
    skip_samples = int(round((attack_skip_ms / 1000.0) * sr))
    if skip_samples >= len(data):
        duration_ms = len(data) / sr * 1000.0
        raise RuntimeError(
            f"Error: attack skip ({attack_skip_ms:.1f} ms) is longer than "
            f"the input ({duration_ms:.1f} ms)"
        )
    if skip_samples < 0:
        skip_samples = 0
    return data[skip_samples:]


def compute_mean_spectrum(
    data: np.ndarray, sr: int, fft_size: int, hop_size: int
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the mean magnitude spectrum over windowed frames."""
    if fft_size > len(data):
        # Pad with zeros so at least one full frame can be analyzed.
        data = np.pad(data, (0, fft_size - len(data)))

    window = np.hanning(fft_size)
    frames = []
    start = 0
    while start < len(data):
        frame = data[start : start + fft_size]
        if len(frame) < fft_size:
            frame = np.pad(frame, (0, fft_size - len(frame)))
        frames.append(frame * window)
        start += hop_size

    frames_array = np.array(frames)
    magnitude_spectra = np.abs(np.fft.rfft(frames_array, n=fft_size, axis=1))
    mean_spectrum = np.mean(magnitude_spectra, axis=0)
    freqs = np.fft.rfftfreq(fft_size, 1.0 / sr)
    return mean_spectrum, freqs


def smooth_spectrum(spectrum: np.ndarray, smoothing_window: int) -> np.ndarray:
    """Smooth a magnitude spectrum while preserving peak locations."""
    window = int(smoothing_window)
    if window < 3:
        return spectrum
    if window % 2 == 0:
        window += 1
    if window > len(spectrum):
        window = len(spectrum) if len(spectrum) % 2 == 1 else len(spectrum) - 1
    if window < 3:
        return spectrum
    return savgol_filter(spectrum, window_length=window, polyorder=3)


def detect_peaks(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    min_freq: float,
    max_freq: float,
    prominence: float,
    distance: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Detect spectral peaks within a frequency range."""
    valid_idx = np.where((freqs >= min_freq) & (freqs <= max_freq))[0]
    if len(valid_idx) == 0:
        return np.array([], dtype=int), freqs[np.array([], dtype=int)]

    min_idx = valid_idx[0]
    max_idx = valid_idx[-1]

    peaks, _ = find_peaks(
        spectrum,
        prominence=prominence,
        distance=distance,
    )
    peaks = peaks[(peaks >= min_idx) & (peaks <= max_idx)]
    return peaks, freqs[peaks]


def frequency_to_note(frequency: float) -> tuple[str, float]:
    """Map a frequency to the nearest 12-TET note name and cent deviation."""
    if frequency <= 0:
        raise ValueError("Frequency must be positive")

    semitones = 12.0 * np.log2(frequency / 440.0)
    note_index = int(round(semitones))
    deviation_cents = 1200.0 * np.log2(
        frequency / (440.0 * 2.0 ** (note_index / 12.0))
    )

    note_name = NOTE_NAMES[(note_index + 9) % 12]
    octave = 4 + (note_index + 9) // 12
    return f"{note_name}{octave}", float(deviation_cents)


def format_peaks(
    peaks: np.ndarray,
    freqs: np.ndarray,
    spectrum: np.ndarray,
) -> list[dict[str, object]]:
    """Build a list of peak records sorted by descending amplitude."""
    if len(peaks) == 0:
        return []

    peak_mags = spectrum[peaks]
    sorted_order = np.argsort(peak_mags)[::-1]
    sorted_peaks = peaks[sorted_order]
    sorted_mags = peak_mags[sorted_order]
    max_mag = sorted_mags[0]

    rows: list[dict[str, object]] = []
    for rank, peak_idx in enumerate(sorted_peaks, start=1):
        frequency = float(freqs[peak_idx])
        amplitude_percent = 100.0 * sorted_mags[rank - 1] / max_mag
        note_name, deviation_cents = frequency_to_note(frequency)
        rows.append(
            {
                "peak_number": rank,
                "frequency_hz": frequency,
                "amplitude_percent": round(amplitude_percent, 1),
                "note_name": note_name,
                "deviation_cents": round(deviation_cents, 1),
            }
        )
    return rows


def write_csv(rows: list[dict[str, object]], output: Path | None) -> None:
    """Write peak records as CSV to a file or stdout."""
    fieldnames = [
        "peak_number",
        "frequency_hz",
        "amplitude_percent",
        "note_name",
        "deviation_cents",
    ]

    def write_to_fileobj(fobj: object) -> None:
        writer = csv.DictWriter(fobj, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            formatted = {
                "peak_number": row["peak_number"],
                "frequency_hz": f"{row['frequency_hz']:.1f}",
                "amplitude_percent": f"{row['amplitude_percent']:.1f}",
                "note_name": row["note_name"],
                "deviation_cents": f"{row['deviation_cents']:+.1f}",
            }
            writer.writerow(formatted)

    if output is None:
        write_to_fileobj(sys.stdout)
    else:
        with open(output, "w", newline="", encoding="utf-8") as f:
            write_to_fileobj(f)


def write_table(rows: list[dict[str, object]], output: Path | None) -> None:
    """Write peak records as an aligned table to a file or stdout."""
    headers = [
        "peak_number",
        "frequency_hz",
        "amplitude_percent",
        "note_name",
        "deviation_cents",
    ]
    formatted_rows: list[list[str]] = []
    for row in rows:
        formatted_rows.append(
            [
                str(row["peak_number"]),
                f"{row['frequency_hz']:.1f}",
                f"{row['amplitude_percent']:.1f}",
                str(row["note_name"]),
                f"{row['deviation_cents']:+.1f}",
            ]
        )

    widths = [len(h) for h in headers]
    for formatted in formatted_rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, formatted)]

    def write_to_fileobj(fobj: object) -> None:
        header_line = "  ".join(
            h.ljust(w) for h, w in zip(headers, widths)
        )
        fobj.write(header_line + "\n")
        for formatted in formatted_rows:
            line = "  ".join(
                cell.ljust(w) for cell, w in zip(formatted, widths)
            )
            fobj.write(line + "\n")

    if output is None:
        write_to_fileobj(sys.stdout)
    else:
        with open(output, "w", encoding="utf-8") as f:
            write_to_fileobj(f)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the analyzer CLI."""
    args = parse_args(argv)

    try:
        data, sr = load_audio(args.input)
        decay_signal = skip_attack(data, sr, args.attack_skip_ms)
        spectrum, freqs = compute_mean_spectrum(
            decay_signal, sr, args.fft_size, args.hop_size
        )
        smoothed = smooth_spectrum(spectrum, args.smoothing_window)
        peaks, _ = detect_peaks(
            smoothed,
            freqs,
            args.min_freq,
            args.max_freq,
            args.prominence,
            args.distance,
        )
        rows = format_peaks(peaks, freqs, smoothed)

        if args.format == "csv":
            write_csv(rows, args.output)
        else:
            write_table(rows, args.output)

        return 0
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1 if "not found" in str(exc) or "failed to read" in str(exc) else 2
    except Exception as exc:  # pragma: no cover - unexpected errors
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
