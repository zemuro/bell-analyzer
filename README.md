# Bell Sample Overtone Analyzer

A command-line tool that analyzes a single bell WAV sample and reports its spectral overtones as CSV or a formatted table.

## Features

- Loads mono or stereo WAV files (24-bit / 48 kHz tested)
- Reduces stereo input to the first channel
- Skips a configurable attack transient
- Averages the magnitude spectrum over the decay portion
- Detects spectral peaks with configurable prominence, distance, and smoothing
- Maps each peak to the nearest 12-TET note and reports cent deviation

## Installation

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Usage

```bash
# Print CSV to stdout
python analyze_bell.py samples/bell.wav

# Write CSV file, skip first 150 ms
python analyze_bell.py samples/bell.wav --output peaks.csv --attack-skip-ms 150

# Formatted table with a narrower frequency range
python analyze_bell.py samples/bell.wav --min-freq 200 --max-freq 4000 --prominence 0.02 --format table
```

## Tests

```bash
venv\Scripts\python -m pytest tests/test_analyze_bell.py -v
```

## Project Structure

- `analyze_bell.py` — main analyzer CLI
- `tests/generate_test_sample.py` — synthetic bell fixture generator
- `tests/test_analyze_bell.py` — pytest test suite
- `plan/` — project plan, reviews, and implementation reports
