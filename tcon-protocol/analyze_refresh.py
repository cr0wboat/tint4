#!/usr/bin/env python3
"""Video-based refresh-mode analysis for the T-CON eInk.

Reverse-engineers refresh modes from a phone video of the panel during a
beep-counted probe (N beeps = mode N, then a display-area with that mode).

Pipeline:
  1. ffmpeg extract audio -> Goertzel @ beep freq -> beep bursts -> mode segments.
  2. ffmpeg extract frames -> per-frame mean/std -> FLASH vs INSTANT signature
     (FLASH = transient spike->dip at the transition; INSTANT = flat/monotonic).

Deps: ffmpeg, numpy (system Python 3.13). Usage:
    analyze_refresh.py VIDEO [--freq 880] [--fps 10] [--t-start 0] [--dur D]
"""

import argparse
import subprocess
import tempfile
import os
import glob
import math

import numpy as np


def goertzel(x, freq, sr):
    """DFT magnitude at freq for a 1-D signal x (pure-Python loop)."""
    k = int(0.5 + len(x) * freq / sr)
    c = 2.0 * math.cos(2.0 * math.pi * k / len(x))
    s1 = s2 = 0.0
    for v in x:
        s0 = v + c * s1 - s2
        s2, s1 = s1, s0
    return math.sqrt(s1 * s1 + s2 * s2 - c * s1 * s2)


def detect_modes(wav, freq=880.0, sr=16000, win=0.02, thr_frac=0.35, gap=0.45):
    """Return a list of beep 'modes'; each mode is a list of (start, end) beeps.
    The length of each list = the mode number (beep count)."""
    import wave
    w = wave.open(wav, 'rb')
    n = w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64)
    wn = int(win * sr)
    env = np.array([goertzel(x[i:i + wn], freq, sr)
                    for i in range(0, n - wn, wn)])
    thr = env.max() * thr_frac
    above = env > thr
    segs, i = [], 0
    while i < len(above):
        if above[i]:
            s = i
            while i < len(above) and above[i]:
                i += 1
            segs.append((s * win, i * win))
        else:
            i += 1
    modes = []
    for t0, t1 in segs:
        if modes and t0 - modes[-1][-1][1] < gap:
            modes[-1].append((t0, t1))
        else:
            modes.append([(t0, t1)])
    return modes


def frame_stats(video, t_start, dur, fps=10.0):
    """Return (means, stds) per frame over [t_start, t_start+dur]."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        pat = os.path.join(d, 'f%05d.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t_start),
                        '-t', str(dur), '-i', video, '-vf', f'fps={fps}', pat],
                       check=True)
        means, stds = [], []
        for f in sorted(glob.glob(os.path.join(d, 'f*.png'))):
            im = Image.open(f).convert('L')
            im.thumbnail((160, 90))
            a = np.asarray(im, dtype=np.float64).ravel()
            means.append(a.mean())
            stds.append(a.std())
        return means, stds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--freq', type=float, default=880.0)
    ap.add_argument('--fps', type=float, default=10.0)
    ap.add_argument('--t-start', type=float, default=0.0)
    ap.add_argument('--dur', type=float, default=None)
    args = ap.parse_args()

    if args.dur is None:
        args.dur = float(subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', args.video]).strip())

    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, 'a.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', args.video,
                        '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav],
                       check=True)
        modes = detect_modes(wav, freq=args.freq)
        print('=== beep modes (count = mode number) ===')
        for i, m in enumerate(modes):
            print(f'  idx {i}: {len(m)} beeps, t={m[0][0]:.2f}s .. {m[-1][1]:.2f}s')

    means, stds = frame_stats(args.video, args.t_start, args.dur, args.fps)
    print('=== frame stats (t, mean, std) - FLASH=spike->dip; INSTANT=flat ===')
    for i, (m, s) in enumerate(zip(means, stds)):
        t = args.t_start + i / args.fps
        print(f'{t:6.1f} {m:5.0f} {s:4.0f}')


if __name__ == '__main__':
    main()
