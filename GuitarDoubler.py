#!/usr/bin/env python3
import sys
import random
import json

import librosa.display
import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf

from tqdm import tqdm


def onset_detection(y, sr, onset_sensitivity, plot=False):
    # Compute onset strength envelope
    onset_env = librosa.onset.onset_strength(
        y=y, sr=sr, hop_length=512, aggregate=np.median
    )

    # Detect onsets
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        backtrack=True,
        delta=onset_sensitivity,
        units="frames",
    )

    # Convert to time
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    onset_times = np.append(onset_times, len(y) / sr)

    print(f"Detected {len(onset_times)} onset frames.")

    # visualize
    if plot:
        times = librosa.times_like(onset_env, sr=sr)

        plt.figure(figsize=(10, 4))
        plt.plot(times, onset_env, label="Onset strength")
        plt.vlines(
            onset_times,
            0,
            onset_env.max(),
            color="r",
            alpha=0.7,
            linestyle="--",
            label="Onsets",
        )
        plt.legend()
        plt.xlabel("Time (s)")
        plt.title("Onset Detection")
        plt.tight_layout()
        plt.show()

    return onset_times


def merge_onsets(onset_times, merge_interval_time):
    # Merge onsets close to each other
    merged_onsets = [onset_times[0]]

    for t in onset_times[1:]:
        if t - merged_onsets[-1] >= merge_interval_time:
            merged_onsets.append(t)

    merged_onsets = np.array(merged_onsets)

    print(f"Merged to {len(merged_onsets)} onset frames.")

    return merged_onsets


def cents_to_steps(cents):
    # converts cents to semitones
    return cents / 100.0


def pitch_shift_segment(segment, sr, max_cents=7):
    # Random pitch variation
    cents = np.random.uniform(-max_cents, max_cents)
    steps = cents_to_steps(cents)

    # Apply pitch shift
    shifted = librosa.effects.pitch_shift(segment, sr=sr, n_steps=steps)

    return shifted


def generate_offset(overlap, min_shift, max_shift, prev_offset=0):
    # min_shift < ∣offset∣ < max_shift
    # prev_offset − overlap < offset < prev_offset + overlap
    intervals = []

    base_lo = prev_offset - overlap
    base_hi = prev_offset + overlap

    # Positive interval: (min_shift, max_shift)
    lo = max(base_lo, min_shift)
    hi = min(base_hi, max_shift)
    if lo < hi:
        lo_i = int(lo) + 1
        hi_i = int(hi) - 1
        if lo_i <= hi_i:
            intervals.append((lo_i, hi_i))

    # Negative interval: (-max_shift, -min_shift)
    lo = max(base_lo, -max_shift)
    hi = min(base_hi, -min_shift)
    if lo < hi:
        lo_i = int(lo) + 1
        hi_i = int(hi) - 1
        if lo_i <= hi_i:
            intervals.append((lo_i, hi_i))

    if not intervals:
        raise ValueError("No valid offset satisfies the constraints.")

    # Uniform sampling across intervals without building full list
    sizes = [hi - lo + 1 for lo, hi in intervals]
    total = sum(sizes)
    r = random.randint(1, total)

    for (lo, hi), size in zip(intervals, sizes):
        if r <= size:
            return lo + (r - 1)
        r -= size


def apply_timing_jitter(
    y, sr, onset_samples, i, overlap, min_shift_time, max_shift_time, prev_offset=0
):
    # read position: unchanged
    read_start = max(0, onset_samples[i] - overlap)
    read_end = min(len(y), onset_samples[i + 1] + overlap)
    segment = y[read_start:read_end]
    seg_len = read_end - read_start

    # convert to samples
    min_shift = int(min_shift_time * sr)
    max_shift = int(max_shift_time * sr)

    # write position: jittered
    offset = generate_offset(overlap, min_shift, max_shift, prev_offset)
    write_start = read_start + offset
    write_end = write_start + seg_len

    # clamp to valid range
    if write_start < 0:
        segment = segment[-write_start:]
        write_start = 0

    if write_end > len(y):
        segment = segment[: len(y) - write_start]
        write_end = len(y)

    seg_len = len(segment)

    return segment, seg_len, write_start, write_end, offset


def apply_pitch_drift(segment, sr, max_drift_cents, drift_rate_hz):
    n = len(segment)
    t = np.arange(n) / sr

    # create smooth low-frequency modulation signal
    # random phase so segments don't align
    phase = np.random.uniform(0, 2 * np.pi)
    drift = np.sin(2 * np.pi * drift_rate_hz * t + phase)

    # scale to cents
    drift_cents = drift * max_drift_cents

    # convert cents to playback rate
    rate = 2 ** (drift_cents / 1200.0)

    # integrate rate to get new time mapping
    time_map = np.cumsum(rate)
    time_map = time_map / time_map[-1] * (n - 1)

    # resample using interpolation
    drifted = np.interp(time_map, np.arange(n), segment)

    return drifted


def apply_gain(segment, gain_range):
    return segment * random.uniform(1 - gain_range, 1 + gain_range)


def allpass_filter_fc(x, sr, fc):
    # convert frequency to coefficient
    k = np.tan(np.pi * fc / sr)
    a = (k - 1) / (k + 1)

    y = np.zeros_like(x)
    z = 0.0

    # apply allpass
    for n in range(len(x)):
        y[n] = -a * x[n] + z
        z = x[n] + a * y[n]

    return y


def allpass_cascade(signal, sr, fc_allpass):
    # cascade allpass for all center frequencies
    for fc in tqdm(fc_allpass, desc="Applying allpass filtering"):
        signal = allpass_filter_fc(signal, sr, fc)

    return signal


def run_guitar_doubler(input_path, output_path):
    # load audio
    y, sr = librosa.load(input_path, sr=None, mono=True)

    # detect onsets
    raw_onset_times = onset_detection(y, sr, parameters["onset_sensitivity"])
    raw_merged_onsets = merge_onsets(raw_onset_times, parameters["merge_interval_time"])
    onset_samples = (raw_merged_onsets * sr).astype(int)

    # Process segments
    processed = np.zeros_like(y)
    overlap = int(parameters["overlap_time"] * sr)  # 10 ms OLA
    fade_len = int(parameters["fade_time"] * sr)  # 5 ms boundary smoothing
    prev_offset = 0

    for i in tqdm(
        range(len(onset_samples) - 1), desc="Applying processing to segments"
    ):
        # apply timing jitter
        segment, seg_len, write_start, write_end, prev_offset = apply_timing_jitter(
            y,
            sr,
            onset_samples,
            i,
            overlap,
            parameters["min_shift_time"],
            parameters["max_shift_time"],
            prev_offset=prev_offset,
        )

        # pitch shift segment
        shifted = pitch_shift_segment(segment, sr)

        # Crossfade
        window = np.ones(seg_len)
        ramp = np.linspace(0, 1, fade_len)
        window[:fade_len] = ramp
        window[-fade_len:] = ramp[::-1]

        # match length
        shifted = shifted[:seg_len]
        if len(shifted) < seg_len:
            shifted = np.pad(shifted, (0, seg_len - len(shifted)))

        # apply pitch drift
        drifted = apply_pitch_drift(
            shifted, sr, parameters["max_drift_cents"], parameters["drift_rate_hz"]
        )

        # apply volume variation
        gained = apply_gain(drifted, parameters["gain_range"])

        # window
        gained *= window

        # Overlap add
        processed[write_start:write_end] += gained

    # allpass
    filtered = allpass_cascade(processed, sr, parameters["fc_allpass"])

    # Save result
    sf.write(output_path, filtered, sr)

    print("Saved doubled track.")


if __name__ == "__main__":
    # check if file paths are given as an argument
    if len(sys.argv) < 3:
        raise SystemExit(
            "Missing arguments. Call script with [1] path to input track and [2] path to output track."
        )

    try:
        with open("parameters.json", "r") as f:
            parameters = json.load(f)
    except FileNotFoundError:
        raise SystemExit("Parameters file not found. Make sure parameters.json exists.")

    # fetch file path
    input_path = sys.argv[1]
    output_path = sys.argv[2]

    # run program
    run_guitar_doubler(input_path, output_path)
