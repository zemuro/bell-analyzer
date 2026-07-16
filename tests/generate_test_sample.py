#!/usr/bin/env python3
"""
Generate a synthetic bell sample for testing the overtone analyzer.

The output WAV contains a short noise burst at the start (the attack) followed
by a sum of exponentially decaying sine waves at known frequencies. Default
partials are 440 Hz, 880 Hz, 1320 Hz, and 1760 Hz.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf


DEFAULT_PARTIALS_HZ = [440.0, 880.0, 1320.0, 1760.0]
DEFAULT_AMPLITUDES = [1.0, 0.5, 0.3, 0.15]
DEFAULT_DECAYS = [2.0, 1.8, 1.5, 1.2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic bell WAV sample with known partials."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("samples/synthetic_bell.wav"),
        help="Output WAV path (default: samples/synthetic_bell.wav).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Total sample duration in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=48000,
        help="Sample rate in Hz (default: 48000).",
    )
    parser.add_argument(
        "--partials",
        type=float,
        nargs="+",
        default=DEFAULT_PARTIALS_HZ,
        help="Partial frequencies in Hz (default: 440 880 1320 1760).",
    )
    parser.add_argument(
        "--amplitudes",
        type=float,
        nargs="+",
        default=DEFAULT_AMPLITUDES,
        help="Relative amplitudes for each partial (default: 1.0 0.5 0.3 0.15).",
    )
    parser.add_argument(
        "--decays",
        type=float,
        nargs="+",
        default=DEFAULT_DECAYS,
        help="Decay time constants in seconds (default: 2.0 1.8 1.5 1.2).",
    )
    parser.add_argument(
        "--attack-noise-ms",
        type=float,
        default=50.0,
        help="Duration of the initial noise burst in milliseconds (default: 50.0).",
    )
    parser.add_argument(
        "--attack-noise-amplitude",
        type=float,
        default=0.3,
        help="Amplitude of the initial noise burst (default: 0.3).",
    )
    parser.add_argument(
        "--bit-depth",
        type=int,
        default=24,
        choices=[16, 24, 32],
        help="PCM bit depth (default: 24).",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=1,
        choices=[1, 2],
        help="Number of channels (default: 1).",
    )
    return parser.parse_args(argv)


def generate_bell_signal(
    duration: float,
    sample_rate: int,
    partials: list[float],
    amplitudes: list[float],
    decays: list[float],
    attack_noise_ms: float,
    attack_noise_amplitude: float,
) -> np.ndarray:
    """Synthesize a bell-like signal with a noisy attack."""
    num_samples = int(round(duration * sample_rate))
    t = np.arange(num_samples) / sample_rate

    if len(amplitudes) != len(partials):
        raise ValueError("--amplitudes must have the same length as --partials")
    if len(decays) != len(partials):
        raise ValueError("--decays must have the same length as --partials")

    signal = np.zeros(num_samples, dtype=np.float64)
    for freq, amp, decay in zip(partials, amplitudes, decays):
        envelope = np.exp(-t / max(decay, 1e-6))
        signal += amp * envelope * np.sin(2.0 * np.pi * freq * t)

    # Normalize so the peak is around -3 dBFS, leaving headroom.
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * 0.7

    # Add a brief noise burst at the start to simulate the attack transient.
    attack_samples = int(round((attack_noise_ms / 1000.0) * sample_rate))
    attack_samples = min(attack_samples, num_samples)
    if attack_samples > 0:
        noise = attack_noise_amplitude * (2.0 * np.random.random(attack_samples) - 1.0)
        # Taper the noise burst to avoid a hard click.
        taper = np.hanning(attack_samples * 2)[:attack_samples]
        signal[:attack_samples] += noise * taper

    # Final safety clamp.
    return np.clip(signal, -1.0, 1.0)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    signal = generate_bell_signal(
        duration=args.duration,
        sample_rate=args.sample_rate,
        partials=args.partials,
        amplitudes=args.amplitudes,
        decays=args.decays,
        attack_noise_ms=args.attack_noise_ms,
        attack_noise_amplitude=args.attack_noise_amplitude,
    )

    if args.channels == 2:
        # Duplicate the mono signal to both channels for stereo testing.
        signal = np.column_stack((signal, signal))

    subtype = f"PCM_{args.bit_depth}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(args.output), signal, args.sample_rate, subtype=subtype)
    print(f"Generated {args.output}: {args.duration}s, {args.sample_rate} Hz, "
          f"{args.bit_depth}-bit, {args.channels} channel(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
