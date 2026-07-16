---
document_type: phase_spec
phase: 03
title: Configuration System and Bilingual Documentation
status: planning
created: 2026-07-16
author: plan_editor
dependencies:
  - soundfile
  - numpy
  - scipy
  - matplotlib
acceptance_criteria_summary:
  - All tunable analyzer defaults are moved to an INI-style config file with explanatory comments and logical sections.
  - CLI flags override config values, and the tool falls back to hardcoded defaults when no config is present.
  - New `--config/-c`, `--save-config`, and `--n-labels/-n` flags work as specified.
  - Spectrum labels are limited to the top N peaks by amplitude and do not overlap, even for closely spaced partials.
  - README.md (English) and README.ru.md (Russian) are present at the project root.
  - docs/ contains bilingual usage, configuration reference, and development guides.
  - All public functions in analyze_bell.py have complete docstrings (Args/Returns/Raises where applicable).
---

# Phase 03 — Configuration System and Bilingual Documentation

## Summary

This phase makes `analyze_bell.py` easier to configure and easier to use by moving all tunable defaults into an INI-style configuration file and by providing complete documentation in English and Russian. A new set of CLI flags (`--config`, `--save-config`, `--n-labels`) gives users explicit control without editing source code, while the analyzer continues to work out of the box with hardcoded defaults when no config file is present.

## 1. Overview

### 1.1 Problem Statement

By the end of Phase 02 the analyzer exposes more than a dozen tunable parameters on the command line, and the visualization labels are becoming crowded for bells with many partials. Currently:

- Defaults are duplicated between argparse definitions and documentation.
- Users who want a personal default style must type long command lines every time.
- There is no user-facing documentation explaining the theory of operation, configuration, or how to contribute.
- Several functions lack complete docstrings.

### 1.2 Goal

Deliver a non-breaking enhancement that:

1. Moves all numeric/string defaults into an INI-style config file with logical sections `[analysis]`, `[visualization]`, and `[output]`.
2. Adds `--config / -c` to load a custom configuration file.
3. Adds `--save-config` to write the current effective configuration (defaults + CLI overrides) to a file.
4. Adds `--n-labels / -n` to control how many detected peaks are annotated on the spectrum plot (default `7`), using alternating offsets to avoid overlap.
5. Keeps every existing CLI flag functional, with CLI values taking precedence over config values and config values taking precedence over hardcoded defaults.
6. Adds a documented example config file to the repository.
7. Writes a full English README and a Russian README (`README.ru.md`) at the project root.
8. Creates a `docs/` directory with bilingual usage, configuration, and development guides.
9. Completes docstrings for all public functions in `analyze_bell.py`.

### 1.3 Scope Boundaries

**In scope:**
- INI configuration file support via `configparser`.
- Config precedence: CLI overrides > config file > hardcoded defaults.
- New CLI flags `--config`, `--save-config`, `--n-labels`.
- Improved spectrum peak-label layout with a configurable limit.
- Example config file shipped in the repository.
- English and Russian project documentation.
- Complete docstrings and type hints.

**Out of scope:**
- Dynamic reload of config while the program is running.
- JSON/YAML/TOML config formats.
- GUI preferences editor.
- Translation of inline code comments or CLI help text (CLI help remains English-only).
- Automated translation; Russian docs are written and maintained by hand.

## 2. Architecture

The configuration layer is inserted between argument parsing and the analysis pipeline. It does not change the core FFT, peak-detection, or plotting algorithms from Phase 02.

```text
argv
 │
 ▼
Extract --config path (first pass)
 │
 ▼
Load INI file (if any) into a defaults dictionary
 │
 ▼
Set argparse defaults from dictionary
 │
 ▼
Parse remaining CLI flags (CLI overrides config)
 │
 ▼
Optionally write effective config with --save-config
 │
 ▼
Existing analysis + visualization pipeline (Phase 02)
```

### 2.1 Dependencies

No new runtime dependencies are required. `configparser` is part of the Python standard library.

The following packages remain required and must be declared in `c:/Users/zemuro/Antigravity/bell synth/requirements.txt` (or equivalent):

| Package | Purpose | Recommended minimum |
|---------|---------|---------------------|
| `soundfile` | Read mono/stereo WAV files, including 24-bit PCM | `>=0.12.1` |
| `numpy` | Array operations, FFT, frequency/cent conversion | `>=1.24` |
| `scipy` | Windowing, smoothing, peak detection, STFT | `>=1.10` |
| `matplotlib` | Spectrogram and spectrum plots | `>=3.7` |

Install or update with:

```bash
pip install -r "c:/Users/zemuro/Antigravity/bell synth/requirements.txt"
```

## 3. Detailed Design

### Task 1: Define the configuration file format

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.ini.example`
- `c:/Users/zemuro/Antigravity/bell synth/config/default.ini`

**Description:**
Create an INI-style configuration file with three logical sections. Every key must have an inline comment explaining its purpose and units.

```ini
[analysis]
; Duration to skip at the start of the file, in milliseconds.
attack_skip_ms = 100.0

; Minimum and maximum peak frequencies to report, in Hz.
min_freq = 50.0
max_freq = 8000.0

; Minimum peak prominence in normalized magnitude units.
; Increase this value to suppress noise; decrease it to catch quiet partials.
prominence = 0.005

; Minimum number of bins between detected peaks.
; Tune downward for bells with closely spaced partials.
distance = 20

; Window length for Savitzky-Golay smoothing. Must be an odd integer >= 3.
smoothing_window = 11

; FFT size per analysis frame and hop size between frames, in samples.
fft_size = 16384
hop_size = 2048

; Maximum number of peaks to report. Leave blank for no limit.
peak_count =

[visualization]
; STFT parameters for the spectrogram, in samples.
spec_nperseg = 4096
spec_noverlap = 3072
spec_nfft = 4096

; Minimum dB value shown on the averaged spectrum plot.
spectrum_floor = -50.0

; Minimum dB value used for the spectrogram color scale.
spec_floor = -144.0

; Number of strongest peaks to label on the spectrum plot.
n_labels = 7

[output]
; Default output format: csv or table.
format = csv
```

Notes:
- `analyze_bell.ini.example` is a documented example that users can copy and edit.
- `config/default.ini` is the repository-wide default config. It is identical to the hardcoded fallback values.
- Keys with empty values (e.g., `peak_count =`) are interpreted as `None`.

### Task 2: Implement config loading and CLI merging

**Effort:** 3 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
1. Add a helper `load_config(path: Path | None) -> dict[str, object]` that:
   - If `path` is provided and exists, parses it with `configparser.ConfigParser`.
   - If `path` is provided and missing, raises a clear `RuntimeError`.
   - If `path` is `None`, searches for `analyze_bell.ini` in the current working directory, then `config/default.ini` next to the script, and returns an empty dictionary if neither exists.
   - Converts numeric values to `float` or `int`, leaves strings as strings, and converts empty strings to `None`.
2. Add a helper `config_defaults() -> dict[str, object]` that returns the hardcoded fallback dictionary.
3. In `parse_args`:
   - Perform a minimal first-pass scan of `argv` for `--config` / `-c` so the config path is known before argparse runs.
   - Merge `config_defaults()` → `load_config(...)` values → argparse defaults. Config values overwrite hardcoded defaults; CLI values will overwrite both during normal parsing.
4. Keep existing argparse argument names identical to the config keys so the mapping is trivial.

### Task 3: Add new CLI flags

**Effort:** 1 hour

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
Add the following argparse entries. Their long-term defaults are taken from the config file, but argparse itself must use the merged defaults from Task 2.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--config`, `-c` | path | `None` | Path to a custom INI configuration file. |
| `--save-config` | path | `None` | Write the effective configuration to this file and exit without analyzing. If the flag is given without a path, write to `analyze_bell.ini` in the current working directory. |
| `--n-labels`, `-n` | int | `7` | Maximum number of peaks to label on the spectrum plot. |

Notes:
- `--save-config` must be processed after `parse_args` returns and before the analysis pipeline runs.
- When `--save-config` is used, the tool prints the path written to `stderr` and exits with code `0`.
- `--n-labels` affects only the plot annotation; it does not change how many peaks are reported in CSV/table output.

### Task 4: Improve spectrum peak-label layout

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
Update `plot_analysis` so that spectrum labels are limited and non-overlapping:

1. Sort detected peaks by descending amplitude.
2. Select the top `args.n_labels` peaks for annotation.
3. Re-sort the selected labels by ascending frequency for display order.
4. Alternate label placement:
   - Even-indexed labels: placed above the peak with a positive vertical offset.
   - Odd-indexed labels: placed below the peak with a negative vertical offset.
   - Use two different offset magnitudes (e.g., `+12` and `+20` points, `-12` and `-20` points) so neighboring labels are staggered both vertically and horizontally.
5. Keep the existing white bounding box and small font size.
6. If the selected peak count is zero, draw the spectrum line without labels.

### Task 5: Implement `--save-config`

**Effort:** 1 hour

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
1. After parsing arguments, if `--save-config` is present:
   - Determine the destination path (`args.save_config` or `analyze_bell.ini` in the current working directory).
   - Build an `configparser.ConfigParser` object with sections `[analysis]`, `[visualization]`, and `[output]`.
   - Populate each section with the effective value of every configurable key (the value that will be used for analysis, i.e., CLI override or config value or hardcoded default).
   - Write a top comment explaining that the file was generated by `--save-config` and that values are in the documented units.
   - Write each section with inline comments copied from the example config.
   - Save the file and exit.
2. The generated file should be valid input for a later `--config` run.

### Task 6: Complete docstrings and type hints

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
Ensure every public function has a complete docstring in the following form:

```python
def function_name(arg: type) -> return_type:
    """One-line summary.

    Args:
        arg: Description.

    Returns:
        Description of return value.

    Raises:
        RuntimeError: When ...
        ValueError: When ...
    """
```

Functions to update or verify:
- `parse_args`
- `load_audio`
- `skip_attack`
- `compute_mean_spectrum`
- `compute_stft`
- `smooth_spectrum`
- `detect_peaks`
- `frequency_to_note`
- `format_peaks`
- `derive_plot_save_path`
- `write_csv`
- `write_table`
- `plot_analysis`
- `main`

### Task 7: Write the project READMEs

**Effort:** 3 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/README.md`
- `c:/Users/zemuro/Antigravity/bell synth/README.ru.md`

**Description:**
Both files must mirror each other in structure and content. Required sections:

1. **Title and one-paragraph description** of the tool.
2. **Features** — list what the analyzer does (WAV input, attack skip, peak detection, note/cents mapping, CSV/table output, visualization).
3. **Quick start** — installation (`pip install -r requirements.txt`) and a minimal example command.
4. **Example output** — a short CSV/table snippet.
5. **Configuration** — brief explanation with a link to `docs/config.md` (or `docs/config.ru.md`).
6. **Documentation index** — links to `docs/usage.md`, `docs/config.md`, `docs/development.md`.
7. **Contributing** — short guidelines (open an issue, fork, add tests, keep docs in sync, both languages for user-facing docs).
8. **Troubleshooting** — at least three common issues and fixes.
9. **License** — reference the project license.

### Task 8: Write the usage guides

**Effort:** 3 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/docs/usage.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/usage.ru.md`

**Description:**
Required content:

1. **Running the analyzer** — positional `input` argument and default path.
2. **Complete CLI flag reference** — table with argument, type, default, and description for every flag from Phases 01–03.
3. **Config file precedence** — CLI > config file > hardcoded defaults.
4. **Examples:**
   - Basic CSV output.
   - Table output with custom frequency range.
   - Visualization (interactive window).
   - Headless PNG export.
   - Loading a custom config.
   - Saving a config.
5. **Sample output** — copy of a typical CSV/table result.
6. **Visualization tips** — how to choose `n_labels`, how to avoid crowded plots, how to use `--no-show` on servers.
7. **Troubleshooting section** with at least five entries (e.g., “no peaks reported”, “attack skip too long”, “labels overlap”, “PNG is blank”, “config file not found”).

### Task 9: Write the configuration reference

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/docs/config.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/config.ru.md`

**Description:**
Required content:

1. **Config file location** — how the tool searches for `analyze_bell.ini`, `config/default.ini`, and how to use `--config`.
2. **Section overview** — `[analysis]`, `[visualization]`, `[output]`.
3. **Key reference table** — every key, type, default, units, and effect.
4. **Example config** — a complete copy of `analyze_bell.ini.example`.
5. **Precedence rules** — CLI overrides, config file, hardcoded defaults.
6. **Saving a config** — how `--save-config` works and why it is useful.

### Task 10: Write the development guides

**Effort:** 3 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/docs/development.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/development.ru.md`

**Description:**
Required content:

1. **Project structure** — list of top-level files and directories with purpose.
2. **Theory of operation:**
   - **Decay-window selection** — why the attack is skipped, how `attack_skip_ms` is converted to samples, and what happens if the skip is too long.
   - **Spectrum averaging** — windowed FFT frames, mean magnitude spectrum, and smoothing.
   - **Peak detection** — `scipy.signal.find_peaks`, prominence, distance, frequency range filtering.
   - **Note/cents conversion** — formula based on `log2(f / 440)`, nearest 12-TET note, cent deviation.
   - **Inharmonic bell overtones** — explanation that bell partials are not integer multiples of the fundamental, which is why each peak is mapped independently rather than assumed harmonic.
3. **Running tests** — `pytest` command and how to generate synthetic samples.
4. **How to add a feature** — steps: update `analyze_bell.py`, update config schema if needed, add tests, update both language docs.
5. **Architecture notes** — first-channel extraction, lazy matplotlib import, headless backend handling.
6. **Contribution guidelines** in the same language as the document.
7. **Troubleshooting for developers** — e.g., installing `soundfile` on Windows, handling 24-bit PCM, matplotlib backend issues.

### Task 11: Add/update tests

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py`
- `c:/Users/zemuro/Antigravity/bell synth/tests/data/` (optional fixtures)

**Description:**
Add tests for the new functionality:

1. **Config loading** — create a temporary INI with non-default values, run the analyzer, and verify the effective values are used (e.g., a different `min_freq` changes reported peaks).
2. **CLI override** — verify that a CLI flag overrides the same key in a config file.
3. **Missing config fallback** — run with `--config missing.ini` and assert a clear error; run without any config and assert hardcoded defaults are used.
4. **Save config** — run `--save-config` and verify the generated file can be re-loaded and contains the expected sections/keys.
5. **`n_labels` behavior** — run with `--plot-save --no-show --n-labels 3` and verify no exception; visual inspection not required.
6. **Docstring completeness** — a lightweight test that every public function in `analyze_bell.py` has a non-empty docstring containing at least an `Args:` and `Returns:` section where applicable.

## 4. Acceptance Criteria

- [ ] All tunable numeric/string defaults are configurable through an INI file with sections `[analysis]`, `[visualization]`, and `[output]`.
- [ ] `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.ini.example` exists and every key has an explanatory comment.
- [ ] `c:/Users/zemuro/Antigravity/bell synth/config/default.ini` exists and matches the hardcoded fallback values.
- [ ] `--config / -c` loads a custom INI file; missing file produces a clear error.
- [ ] CLI argument values override values from the config file.
- [ ] When no config file is present, the tool uses hardcoded defaults and runs successfully.
- [ ] `--save-config PATH` writes the effective configuration to the given path and exits cleanly.
- [ ] `--n-labels / -n` limits the number of labeled peaks on the spectrum plot to the specified count (default `7`).
- [ ] Spectrum labels for the top `n_labels` peaks do not overlap; alternating vertical offsets are used.
- [ ] Existing Phase 01/02 behavior is unchanged when no new flags are provided.
- [ ] `README.md` (English) and `README.ru.md` (Russian) exist at the project root and cover all required sections.
- [ ] `docs/usage.md`, `docs/usage.ru.md`, `docs/config.md`, `docs/config.ru.md`, `docs/development.md`, and `docs/development.ru.md` exist and contain the required content.
- [ ] The development documentation explains the theory of operation: decay-window selection, spectrum averaging, peak detection, note/cents conversion, and inharmonic bell overtones.
- [ ] The usage documentation includes a troubleshooting section.
- [ ] The README and development guides include contribution guidelines in both languages.
- [ ] Every public function in `analyze_bell.py` has a complete docstring with `Args`, `Returns`, and `Raises` where applicable.
- [ ] All tests pass:
  ```bash
  pytest "c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py"
  ```

## 5. Test Plan

### 5.1 Unit / integration tests

Run the full test suite:

```bash
cd "c:/Users/zemuro/Antigravity/bell synth"
pytest tests/test_analyze_bell.py -v
```

Expected: all existing tests plus new config/label/docstring tests pass.

### 5.2 Config file smoke test

```bash
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --config "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.ini.example" \
  --format table
```

Verify the command runs and the output respects the example config defaults.

### 5.3 CLI override test

Create a temporary config with `min_freq = 500.0`. Run:

```bash
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --config "c:/Users/zemuro/Antigravity/bell synth/tmp_config.ini" \
  --min-freq 100.0 --format table
```

Verify reported peaks include frequencies below 500 Hz, proving `--min-freq` overrode the config.

### 5.4 `--save-config` test

```bash
cd "c:/Users/zemuro/Antigravity/bell synth"
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  --save-config "c:/Users/zemuro/Antigravity/bell synth/my_config.ini"
```

Verify:
- The file `c:/Users/zemuro/Antigravity/bell synth/my_config.ini` is created.
- It contains `[analysis]`, `[visualization]`, and `[output]` sections.
- It contains `n_labels = 7`.
- The command exits without running analysis.

### 5.5 Headless visualization with limited labels

```bash
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --plot-save "c:/Users/zemuro/Antigravity/bell synth/labels_test.png" \
  --no-show --n-labels 5
```

Verify the PNG is created and non-empty.

### 5.6 No-config fallback test

Temporarily rename `config/default.ini` and any `analyze_bell.ini` in the working directory. Run:

```bash
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav"
```

Verify the analyzer still produces CSV output using hardcoded defaults.

### 5.7 Documentation completeness check

Verify the following files exist and are non-empty:

- `c:/Users/zemuro/Antigravity/bell synth/README.md`
- `c:/Users/zemuro/Antigravity/bell synth/README.ru.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/usage.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/usage.ru.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/config.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/config.ru.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/development.md`
- `c:/Users/zemuro/Antigravity/bell synth/docs/development.ru.md`

Spot-check that each contains the required sections described in Tasks 7–10.

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Config precedence logic becomes confusing for users | Medium | Medium | Document precedence clearly in `docs/config.md`, `docs/usage.md`, and the example INI. |
| `--save-config` writes an invalid file due to `None` values | Low | Medium | Handle empty/None values explicitly when writing; validate the generated file can be re-parsed. |
| Spectrum labels still overlap for very dense spectra | Medium | Medium | Limit labels to top `n_labels` and use alternating offsets; allow users to reduce `n_labels` further. |
| Russian documentation drifts out of sync with English docs | Medium | Low | Keep structure identical; acceptance criteria require mirroring sections. |
| Existing tests break because argparse defaults change | Low | High | Load config defaults before argparse parses so existing CLI behavior is preserved when no config is used. |
| Users expect config to control boolean flags like `--quiet` | Low | Low | Document that action flags (`--visualize`, `--quiet`, etc.) remain CLI-only; numeric/visualization defaults are config-driven. |

## 7. Effort Estimate

| Sub-task | Hours | Notes |
|----------|-------|-------|
| Design config schema and create example/default INI files | 2 | Includes comments and verification |
| Implement config loading, precedence, and argparse integration | 3 | First-pass `--config` extraction is the trickiest part |
| Add `--save-config` and `--n-labels` flags | 2 | Includes save-config writer and label layout |
| Update spectrum label layout | 2 | Alternating offsets for top N labels |
| Complete docstrings in `analyze_bell.py` | 2 | Args/Returns/Raises for all public functions |
| Write README.md and README.ru.md | 3 | Must mirror structure |
| Write docs/usage.md and usage.ru.md | 3 | Includes full flag reference and troubleshooting |
| Write docs/config.md and config.ru.md | 2 | Key reference table and example config |
| Write docs/development.md and development.ru.md | 3 | Theory of operation and contribution guidelines |
| Add tests for config, labels, save-config, docstrings | 2 | Integration tests with temporary files |
| Manual verification | 1 | Run commands, inspect generated config and plots |
| **Total** | **25** | |

## 8. Deferred Items

| Item | Reason |
|------|--------|
| Additional config formats (JSON/TOML/YAML) | INI is sufficient and stdlib-supported; other formats can be added later if requested. |
| Per-file config inheritance | Adds complexity; users can use `--config` per run. |
| Interactive config editor | Out of scope for a CLI tool; users edit INI directly. |
| Auto-detection of optimal `n_labels` | User control is simpler and more predictable. |
| Translation of CLI help text | Keeping CLI help in English avoids argparse locale complexity. |

## 9. CLI Interface

### Arguments

The following table lists **all** CLI arguments after this phase. Defaults shown are the hardcoded fallbacks; in practice they are overridden by any loaded config file.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `input` | path | `c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav` | Path to input WAV file |
| `--output` | path | `None` | Output CSV/table path; prints to stdout if omitted |
| `--attack-skip-ms` | float | `100.0` | Duration to skip at the start (ms) |
| `--min-freq` | float | `50.0` | Minimum peak frequency to report (Hz) |
| `--max-freq` | float | `8000.0` | Maximum peak frequency to report (Hz) |
| `--prominence` | float | `0.005` | Minimum peak prominence in normalized magnitude units |
| `--distance` | int | `20` | Minimum number of bins between peaks |
| `--smoothing-window` | int | `11` | Window length for spectrum smoothing (odd integer) |
| `--fft-size` | int | `16384` | FFT size per frame |
| `--hop-size` | int | `2048` | Hop between successive frames |
| `--peak-count` | int | `None` | Maximum number of peaks to report (`None` = no limit) |
| `--format` | choice | `csv` | Output format: `csv` or `table` |
| `--visualize` | flag | `False` | Open an interactive matplotlib window |
| `--spectrogram` | flag | `False` | Alias for `--visualize` |
| `--plot-save` | path | `None` | Save the figure to a PNG; derives filename if no path given |
| `--no-show` | flag | `False` | Skip the interactive plot window |
| `--quiet` | flag | `False` | Suppress textual CSV/table output |
| `--spec-nperseg` | int | `4096` | STFT window length for the spectrogram |
| `--spec-noverlap` | int | `3072` | STFT overlap for the spectrogram |
| `--spec-nfft` | int | `4096` | FFT length used by the STFT |
| `--spectrum-floor` | float | `-50.0` | Minimum dB value on the averaged spectrum plot |
| `--spec-floor` | float | `-144.0` | Minimum dB value on the spectrogram color scale |
| `--config`, `-c` | path | `None` | Path to a custom INI configuration file |
| `--save-config` | path | `None` | Write effective configuration to a file and exit |
| `--n-labels`, `-n` | int | `7` | Number of peaks to label on the spectrum plot |

### Exit codes

| Exit code | Meaning | Typical cause |
|-----------|---------|---------------|
| `0` | Success | Analysis completed, config saved, or output emitted |
| `1` | General error | Missing file, invalid arguments, unhandled exception |
| `2` | Empty signal after attack skip | `--attack-skip-ms` removes the entire usable sample |

### Example Commands

```bash
# Basic usage with default config search
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav"

# Load a custom configuration file
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --config "c:/Users/zemuro/Antigravity/bell synth/my_bell.ini"

# Save the current effective configuration for editing
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  --save-config "c:/Users/zemuro/Antigravity/bell synth/my_bell.ini"

# Label only the 5 strongest peaks and save a PNG headlessly
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --n-labels 5 --plot-save --no-show

# Override a config value from the command line
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --config "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.ini.example" \
  --min-freq 200.0 --format table
```

## 10. Example Output

### Saved configuration (`my_bell.ini`)

```ini
# Effective configuration generated by analyze_bell.py --save-config
# Units are documented in the example config file.

[analysis]
attack_skip_ms = 100.0
min_freq = 50.0
max_freq = 8000.0
prominence = 0.005
distance = 20
smoothing_window = 11
fft_size = 16384
hop_size = 2048
peak_count =

[visualization]
spec_nperseg = 4096
spec_noverlap = 3072
spec_nfft = 4096
spectrum_floor = -50.0
spec_floor = -144.0
n_labels = 7

[output]
format = csv
```

### Analysis output (CSV)

```csv
peak_number,frequency_hz,amplitude_percent,note_name,deviation_cents
1,439.8,100.0,A4,-0.8
2,879.6,45.2,A5,-0.8
3,1319.4,18.6,E6,+1.2
4,1759.2,8.3,A6,-0.8
5,2200.1,4.1,C#7,-29.8
6,2639.8,2.7,E7,+1.2
7,3080.2,1.5,G7,-17.2
```

### Analysis output (table)

```text
peak_number  frequency_hz  amplitude_percent  note_name  deviation_cents
1            439.8         100.0              A4         -0.8
2            879.6         45.2               A5         -0.8
3            1319.4        18.6               E6         +1.2
4            1759.2        8.3                A6         -0.8
5            2200.1        4.1                C#7        -29.8
6            2639.8        2.7                E7         +1.2
7            3080.2        1.5                G7         -17.2
```
