#!/usr/bin/env python3

import librosa.display
import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf


def onset_detection(y, sr, onset_sensitivity=0.15, plot=False):
    # Compute onset strength envelope
    onset_env = librosa.onset.onset_strength(
        y=y,
        sr=sr,
        hop_length=512,
        aggregate=np.median
    )

    # Detect onsets
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        backtrack=True,
        delta=onset_sensitivity,
        units='frames'
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
        plt.vlines(onset_times, 0, onset_env.max(), color='r', alpha=0.7, linestyle='--', label="Onsets")
        plt.legend()
        plt.xlabel("Time (s)")
        plt.title("Onset Detection")
        plt.tight_layout()
        plt.show()

    return onset_times


def merge_onsets(onset_times, merge_interval=0.075):
    # Merge onsets close to each other
    merged_onsets = [onset_times[0]]

    for t in onset_times[1:]:
        if t - merged_onsets[-1] >= merge_interval:
            merged_onsets.append(t)

    merged_onsets = np.array(merged_onsets)

    print(f"Merged to {len(merged_onsets)} onset frames.")

    return merged_onsets


def cents_to_steps(cents):
    # converts cents to semitones
    return cents / 100.0


def pitch_shift_segment(segment, sr, max_cents=5):
    # Random pitch variation
    cents = np.random.uniform(-max_cents, max_cents)
    steps = cents_to_steps(cents)

    # Apply pitch shift
    shifted = librosa.effects.pitch_shift(segment, sr=sr, n_steps=steps)

    return shifted


#def run_guitar_doubler(file_path):
# load audio
file_path = "data/DI01_part.wav"
y, sr = librosa.load(file_path, sr=None, mono=True)

# detect onsets
raw_onset_times = onset_detection(y, sr)
raw_merged_onsets = merge_onsets(raw_onset_times)
onset_samples = (raw_merged_onsets * sr).astype(int)

# --- Process segments ---
segments = []
buffer = np.array([])
processed = np.zeros_like(y)
weight = np.zeros_like(y)
overlap = int(0.005 * sr)       # 5 ms OLA
fade_len = int(0.005 * sr)      # 5 ms boundary smoothing

for i in range(len(onset_samples) - 1):
    start = max(0, onset_samples[i] - overlap)
    end = min(len(y), onset_samples[i + 1] + overlap)
    segment = y[start:end]
    seg_len = end - start

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

    shifted *= window

    # Overlap add
    processed[start:end] += shifted
    weight[start:end] += window

# normalizing crossfades
processed /= np.maximum(weight, 1e-8)

# --- Save result ---
sf.write("pitch_varied.wav", processed, sr)

print("Saved pitch-varied track.")