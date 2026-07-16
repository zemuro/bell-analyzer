---
document_type: phase_spec
phase: 01
title: Bell Sample Overtone Analyzer CLI
status: implemented
created: 2026-07-16
author: plan_editor
dependencies:
  - soundfile
  - numpy
  - scipy
acceptance_criteria_summary:
  - CLI loads a mono or stereo 24-bit/48 kHz WAV file and processes only the first channel.
  - Skips a configurable attack window before analyzing the steady/decay portion.
  - Reports frequency (Hz), relative amplitude (% of strongest peak), nearest 12-TET note, and cent deviation for each detected peak.
  - Outputs CSV to stdout or a file, with sensible defaults and override knobs.
---

# Phase 01 — Bell Sample Overtone Analyzer CLI

## Summary

Build a Python command-line tool (`analyze_bell.py`) that reads a single WAV bell sample, ignores the noisy attack, averages the magnitude spectrum over the remaining signal, and emits a ranked list of overtone peaks. Output is human-readable CSV/ table data suitable for further analysis or documentation.

## 1. Overview

### 1.1 Problem Statement

Bell recordings contain a short, noisy attack followed by sustained, decaying partials (overtones). Manual inspection of the spectrum is tedious, and off-the-shelf tuners assume harmonic series. We need an automated tool that measures the actual partials in a bell sample and maps each partial to the nearest 12-tone equal-temperament note.

### 1.2 Goal

Deliver a runnable Python CLI that:

1. Accepts a single WAV file path.
2. Loads only the first channel if stereo.
3. Skips the attack transient.
4. Computes an averaged magnitude spectrum over the decay portion.
5. Detects spectral peaks with configurable sensitivity.
6. Outputs each peak's frequency, relative amplitude, nearest note name, and cent deviation.

### 1.3 Scope Boundaries

**In scope:**
- Single-file processing from the command line.
- First-channel extraction for stereo input.
- Configurable attack skip, frequency range, peak prominence, and smoothing.
- CSV or formatted table output.
- Test helpers that generate synthetic bell samples.

**Out of scope:**
- Batch processing of multiple files.
- Graphical user interface.
- Time-varying partial tracking (this phase uses a single averaged spectrum).
- Source separation for multiple bells.

## 2. Architecture

The tool is a single Python script built on standard scientific-audio libraries:

- `soundfile` — load WAV files, including 24-bit/48 kHz mono or stereo.
- `numpy` — array math, FFT bins, frequency/cent conversion.
- `scipy.signal` — windowing, peak detection, optional smoothing.

Pipeline:

```text
WAV file
   │
   ▼
Load first channel (float64)
   │
   ▼
Skip attack transient
   │
   ▼
Windowed FFT on decay portion → magnitude per frame
   │
   ▼
Average magnitudes across frames
   │
   ▼
Smooth + detect peaks
   │
   ▼
Filter by min/max frequency
   │
   ▼
Convert Hz → note name + cent deviation
   │
   ▼
Emit CSV/table
```

### 2.1 Dependencies

The implementation depends on the following Python packages, which must be declared in a dependency manifest (e.g., `c:/Users/zemuro/Antigravity/bell synth/requirements.txt` or `c:/Users/zemuro/Antigravity/bell synth/pyproject.toml`):

| Package | Purpose | Recommended minimum |
|---------|---------|---------------------|
| `soundfile` | Read mono/stereo WAV files, including 24-bit PCM | `>=0.12.1` |
| `numpy` | Array operations, FFT, frequency/cent conversion | `>=1.24` |
| `scipy` | Windowing, spectrum smoothing, peak detection | `>=1.10` |

Install with:

```bash
pip install -r "c:/Users/zemuro/Antigravity/bell synth/requirements.txt"
```

## 3. Detailed Design

### Task 1: Implement `analyze_bell.py`

**Effort:** 6 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
Implement the analyzer as a self-contained CLI script.

1. **Load audio.** Use `soundfile.read(path, dtype='float64')`. The result is normalized to `[-1.0, 1.0]`.
   - If the array is 2-D, keep only the first column: `data = data[:, 0]`.
   - Capture sample rate `sr`.
2. **Skip attack.** Convert `--attack-skip-ms` to samples:
   `skip_samples = int(round((args.attack_skip_ms / 1000.0) * sr))`.
   - If `skip_samples >= len(data)`, abort with a clear error.
3. **Windowing.** Use a Hann window of size `--fft-size` and hop size `--hop-size`.
   - Pad the final frame with zeros if needed.
   - Apply `numpy.fft.rfft` to each windowed frame and take `numpy.abs`.
4. **Average spectrum.** Accumulate magnitude frames and divide by frame count to get a mean magnitude spectrum.
5. **Smoothing.** Apply `scipy.signal.savgol_filter` or a moving-average convolution with width `--smoothing-window`. Smoothing reduces noise but preserves peak locations.
6. **Frequency axis.** Compute with `numpy.fft.rfftfreq(fft_size, 1.0 / sr)`.
7. **Detect peaks.** Use `scipy.signal.find_peaks` on the smoothed magnitude, restricted to bins between `--min-freq` and `--max-freq`.
   - `prominence` controls how much a peak must stand out.
   - `distance` is specified in bins and prevents duplicate detections of the same broad peak; it may need to be reduced when analyzing bells with closely spaced partials.
8. **Amplitude normalization.** For each detected peak, compute relative amplitude as a percentage of the strongest detected peak:
   `amplitude_percent = 100.0 * mag / max_mag`.
9. **Note/cents conversion.** For each peak frequency `f`:
   - `semitones = 12.0 * np.log2(f / 440.0)`
   - `note_index = int(round(semitones))`
   - `deviation_cents = 1200.0 * np.log2(f / (440.0 * 2.0 ** (note_index / 12.0)))`
   - Map `note_index % 12` to note names: `['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']`.
   - Compute octave relative to A4 = 440 Hz. For a note index where A4 corresponds to `note_index = 0`:
     `octave = 4 + floor((note_index + 9) / 12)`.
     This places C4 at MIDI note 60 and ensures octaves change at C.
10. **Output.** Print CSV with columns:
    `peak_number,frequency_hz,amplitude_percent,note_name,deviation_cents`.
    - The CSV includes a header row by default.
    - Respect `--output` if provided; otherwise print to stdout.
    - Optional `--format table` prints aligned columns for human reading.

### Task 2: Create test helpers

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/tests/generate_test_sample.py`
- `c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py`

**Description:**
- `generate_test_sample.py` creates a 24-bit/48 kHz WAV with a known set of exponentially decaying sine waves plus a brief noise burst at the start. Defaults: fundamental 440 Hz + partials 880 Hz, 1320 Hz, 1760 Hz.
- `test_analyze_bell.py` runs the CLI against the generated file and asserts that the expected peaks are recovered within tolerance (frequency ±5 Hz, relative amplitude percentages within ±5 percentage points of expected values, with the same rank order).

## 4. Acceptance Criteria

- [x] `analyze_bell.py` runs from the command line on a single WAV file without import errors.
- [x] Stereo input is reduced to the first channel before analysis.
- [x] 24-bit/48 kHz WAV files load correctly via `soundfile`.
- [x] The attack window is skipped according to `--attack-skip-ms`.
- [x] Detected peaks include frequency (Hz), relative amplitude (%), nearest 12-TET note, and cent deviation.
- [x] Output can be written to a CSV file or printed to stdout.
- [x] All configurable parameters listed below are exposed as CLI flags with documented defaults.
- [x] The synthetic test passes: known partials are recovered within the specified tolerances.

## 5. Test Plan

### 5.1 Test framework

Tests may be written with plain `assert` statements for simplicity, but `pytest` is recommended and should be documented in the dependency manifest. Example run:

```bash
pytest "c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py"
```

### 5.2 Synthetic known-bell test

1. Run `python tests/generate_test_sample.py --output samples/synthetic_bell.wav`.
2. Run `python analyze_bell.py samples/synthetic_bell.wav --output samples/synthetic_bell.csv`.
3. Inspect the CSV and verify:
   - Peak at 440 Hz is present and has the largest amplitude.
   - Peaks near 880 Hz, 1320 Hz, and 1760 Hz are present.
   - Frequency error is within ±5 Hz for each expected partial.
   - Relative amplitude percentages are within ±5 percentage points of expected values, with the same rank order.

### 5.3 Sine sweep sanity check

1. Generate a short linear sine sweep from 200 Hz to 2 kHz without noise.
2. Run the analyzer with `--min-freq 100 --max-freq 3000`.
3. Confirm the output contains a single dominant peak band and no peaks below/above the configured range.

### 5.4 Real sample smoke test

1. If a real bell sample is available, run `python analyze_bell.py sample.wav --format table`.
2. Visually confirm:
   - The fundamental and several overtones are reported.
   - Cent deviations are plausible (typically under a few hundred cents).
   - Skipping the attack produces a cleaner peak list than `--attack-skip-ms 0`.

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 24-bit WAV loading fails on some platforms | Low | High | Use `soundfile` (libsndfile-backed). Document a fallback to `scipy.io.wavfile` with a clear error message if `soundfile` is unavailable. |
| Attack skip removes usable signal if set too high | Medium | Medium | Default to a conservative value (100 ms), validate remaining length, and print the effective skip time. |
| Peak detector misses quiet overtones or reports noise | Medium | Medium | Expose `prominence`, `distance`, `smoothing-window`, and `fft-size` knobs. Document recommended ranges. |
| Inharmonic bell partials map to enharmonic/distant notes | Low | Low | Output cents deviation explicitly and note that mapping is to 12-TET, not a bell-specific temperament. |

## 7. Effort Estimate

| Sub-task | Hours | Notes |
|----------|-------|-------|
| Implement `analyze_bell.py` CLI and core algorithm | 6 | Includes argparse, FFT/peak pipeline, note conversion, CSV output |
| Create synthetic sample generator and tests | 2 | Includes fixture generation and assertion harness |
| Manual verification with real/synthetic samples | 1 | Tweak defaults and confirm robustness |
| **Total** | **9** | |

## 8. Deferred Items

| Item | Reason |
|------|--------|
| Multi-file batch processing | Out of scope for Phase 01; can be added once single-file behavior is stable. |
| Time-varying partial tracking | Requires spectrogram/peak linking; keep as future enhancement. |
| GUI or plotting | CLI-first deliverable; visualization can be added later. |
| Bell-specific temperament mapping | User requested 12-TET output; custom bell scales may be added if needed. |

## 9. Notes for the Implementer

- **First channel only:** Always reduce multi-channel input to a 1-D array by selecting index `0`. Do not average channels unless explicitly requested later.
- **24-bit WAV files:** `soundfile.read(..., dtype='float64')` reads 24-bit PCM correctly and returns normalized floats. If the environment cannot install `soundfile`, `scipy.io.wavfile.read` can read 24-bit PCM in recent SciPy versions, but normalization must be performed manually.
- **48 kHz sample rate:** The implementation must use the sample rate reported by the file rather than hard-coding 48000. Document that 48 kHz is the target/tested rate.
- **Attack skip:** The default should be `100` ms. For very short samples, abort with a helpful message rather than silently producing an empty spectrum.
- **Octave calculation:** For A4 = 440 Hz (`note_index = 0`), compute the displayed octave as `octave = 4 + floor((note_index + 9) / 12)`. This places C4 at MIDI note 60 and makes octave boundaries align with the musical convention that octaves change at C.
- **Distance parameter:** `--distance` is specified in bins. With the default `--fft-size=8192` at 48 kHz, 50 bins ≈ 293 Hz minimum separation. Reduce it when analyzing bells with closely spaced partials, or increase it to suppress duplicate detections of a single broad peak.
- **Inharmonic spectra:** Bell overtones are often not integer multiples of the fundamental. The note/cents conversion therefore maps each peak independently to the nearest 12-TET pitch; it does not assume a harmonic series.
- **Input paths:** All input paths are resolved relative to the project root (`c:/Users/zemuro/Antigravity/bell synth/`). The default input path is `samples\bell.wav`, and the analyzer works with any `.wav` file inside the `samples\` directory under the project root.

## 10. CLI Interface

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `input` | path | `samples\bell.wav` | Path to input WAV file (resolved relative to the project root) |
| `--output` | path | `None` | Output CSV path; prints to stdout if omitted |
| `--attack-skip-ms` | float | `100.0` | Duration to skip at the start (ms) |
| `--min-freq` | float | `50.0` | Minimum peak frequency to report (Hz) |
| `--max-freq` | float | `8000.0` | Maximum peak frequency to report (Hz) |
| `--prominence` | float | `0.01` | Minimum peak prominence in normalized magnitude units |
| `--distance` | int | `50` | Minimum number of bins between peaks; tune downward for closely spaced partials |
| `--smoothing-window` | int | `11` | Window length for spectrum smoothing (odd integer) |
| `--fft-size` | int | `8192` | FFT size per frame |
| `--hop-size` | int | `2048` | Hop between successive frames |
| `--format` | choice | `csv` | Output format: `csv` (with header row) or `table` |

### Exit codes

| Exit code | Meaning | Typical cause |
|-----------|---------|---------------|
| `0` | Success | Analysis completed and output emitted |
| `1` | General error | Missing file, invalid arguments, or unhandled exception |
| `2` | Empty signal after attack skip | `--attack-skip-ms` removes the entire usable sample |

Error messages must be printed to `stderr` and include a concise description, e.g.:
- `Error: input file not found: <path>`
- `Error: attack skip (<ms> ms) is longer than the input (<duration> ms)`

### Example Commands

```bash
# Basic usage: print CSV to stdout
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" "sample.wav"

# Write CSV file, skip first 150 ms
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" "sample.wav" \
  --output peaks.csv --attack-skip-ms 150

# Narrow frequency range, higher prominence for cleaner results
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" "sample.wav" \
  --min-freq 200 --max-freq 4000 --prominence 0.02 --format table
```

### Example Output (CSV)

```csv
peak_number,frequency_hz,amplitude_percent,note_name,deviation_cents
1,439.8,100.0,A4,-0.8
2,879.6,45.2,A5,-0.8
3,1319.4,18.6,E6,+1.2
4,1759.2,8.3,A6,-0.8
```

### Example Output (table)

```text
peak_number  frequency_hz  amplitude_percent  note_name  deviation_cents
1            439.8         100.0              A4         -0.8
2            879.6         45.2               A5         -0.8
3            1319.4        18.6               E6         +1.2
4            1759.2        8.3                A6         -0.8
```
