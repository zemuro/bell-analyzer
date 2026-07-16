# Usage Guide

This guide covers running the Bell Sample Overtone Analyzer from the command line.

## Running the analyzer

The analyzer takes a single positional argument: the path to a WAV file.

```bash
python analyze_bell.py samples/bell.wav
```

If no input is given, it defaults to `samples\bell.wav` relative to the project root.

## Complete CLI flag reference

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `input` | path | `samples\bell.wav` | Path to input WAV file |
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
| `--plot-save` | path | `None` | Save figure to PNG; derives filename if no path given |
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

## Config precedence

Values are resolved in this order:

1. **CLI flags** — highest priority
2. **Config file** (`analyze_bell.ini` or file passed with `--config`)
3. **Hardcoded defaults** — lowest priority

## Examples

### Basic CSV output

```bash
python analyze_bell.py samples/bell.wav
```

### Table output with custom frequency range

```bash
python analyze_bell.py samples/bell.wav --min-freq 200 --max-freq 4000 --format table
```

### Interactive visualization

```bash
python analyze_bell.py samples/bell.wav --visualize --peak-count 12
```

### Headless PNG export

```bash
python analyze_bell.py samples/bell.wav --plot-save bell_report.png --no-show
```

### Loading a custom config

```bash
python analyze_bell.py samples/bell.wav --config my_bell.ini
```

### Saving a config

```bash
python analyze_bell.py --save-config my_bell.ini
```

### Override a config value from the command line

```bash
python analyze_bell.py samples/bell.wav --config my_bell.ini --min-freq 200.0
```

## Sample output

```csv
peak_number,frequency_hz,amplitude_percent,note_name,deviation_cents
1,366.2,100.0,F#4,-17.8
2,890.6,81.6,A5,+20.8
3,805.7,60.2,G5,+47.2
4,1517.6,44.6,F#6,+43.4
```

## Visualization tips

- Use `--n-labels` to avoid crowded plots. The default is `7`; reduce it for dense spectra.
- Use `--no-show` together with `--plot-save` on servers or in CI.
- Adjust `--spectrum-floor` if quiet peaks are cut off or the plot looks too empty.
- Adjust `--spec-floor` if the spectrogram looks too noisy or too dark.

## Troubleshooting

**No peaks reported**
- Lower `--prominence` (e.g., `0.001`) to detect quieter partials.
- Reduce `--distance` (e.g., `10`) for closely spaced partials.
- Widen `--min-freq` / `--max-freq`.

**Attack skip too long**
- Reduce `--attack-skip-ms` or use a longer sample.

**Labels overlap**
- Reduce `--n-labels`.

**PNG is blank**
- Check that `--plot-save` received a valid path.
- Ensure `--no-show` is used in headless environments.

**Config file not found**
- Verify the path passed to `--config`.
- Use `--save-config` to generate a valid starter file.
