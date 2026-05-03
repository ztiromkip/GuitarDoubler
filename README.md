# Guitar Doubler for DI Tracks

This project generates a synthetic double-tracked like DI Guitar Track to a given original take.
You can run the project by running
`python.exe .\GuitarDoubler.py inputTrack.wav outputTrack.wav`, 
with a given `inputTrack.wav` beeing a recorded DI Take and
`outputTrack.wav` beeing the path to save the generated file to,
in your console. Soft parameters of the algorithm are stored in `parameters.json`
and can be adapted to archieve the most realistic result possible for the given input signal.

The algorithm runs through the following steps to adapt the given audio and create a double take:

- Onset Detection and dividing the signal into frames that can be further processes frame by frame,
- Merging the frames to smooth out misinterpretations,
- Applying timing jitters to each frame to simulate the timing offset of a real player,
- Pitch shifting and drifting each frame,
- Volume drifting each frame,
- Adding up all the frames and applying allpass filtering to the complete signal to eliminate phasing issues 
when played together with the original signal.

The soft parameters that can be adapted individually are:

- ``onset_sensitivity``:
- ``plot_onsets``:
- ``merge_interval_time``: 
- ``max_shift_cents``: Adjusts, by how many cents every frame is shifted individually in frequency (maximum).
- ``max_drift_cents``: Adjusts, by how many cents every frame drifts in frequency over time at a given rate.
- ``drift_rate_hz``: Adjusts how fast the frames drift over time.
- ``overlap_time``:
- ``fade_time``:
- ``min_shift_time``: Adjusts, how many ms each frame is at least shifted away from its orignial position.
- ``max_shift_time``: Adjusts, how many ms each frame is maximally shifted away from its orignial position.
- ``gain_range``: Adjusts, how much the volume of each frame can be altered.
- ``fc_allpass``: Adjusts the center frequencies of the applied allpass cascade (list of frequencies in Hz).

## Quickstart
To use directly:
- clone repo
- create venv
- ``pip install requirements.txt``
- ``python.exe .\GuitarDoubler.py inputTrack.wav outputTrack.wav``

For Reaper .lua usage: 
- clone repo
- create venv
- ``pip install requirements.txt``
- Download https://dkolf.de/dkjson-lua/ and place it in your REAPER Scripts folder.
- In Reaper, go to Actions → new Action → select ``GuitarDoublerREAction.lua``
- Select the item you want to double.
- Run the created action.