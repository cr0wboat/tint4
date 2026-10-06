#!/usr/bin/env python3
"""Probe refresh modes: cycle the 0x34 'display area' mode field.

Uploads an image first (optional path arg), then re-displays it full-screen
with each candidate mode so you can observe speed / ghosting per mode.

Usage: probe-modes.py [IMAGE]
"""
import sys
import os
import time
import subprocess
import logging

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from HelperClient import HelperClient

SOCKET_PATH = '/tmp/tinta4plusu.sock'
CANDIDATE_MODES = [1, 2, 3, 4, 6, 7, 8]
PAUSE = 5.0

# Standard IT8951 mode names (guesses — the IT8957 may differ)
MODE_DETAILS = {
    1: 'DU     (1-bit direct, fast, ghosting)',
    2: 'GC16   (full 16-gray, slow, flash)',
    3: 'GL16   (16-gray)',
    4: 'GLR16  (16-gray)',
    5: 'GLD16  (16-gray + dither — our default)',
    6: 'A2     (1-bit fast, ghosting)',
    7: 'GL4    (4-gray)',
    8: '?      (unknown)',
}


def beep(count=1):
    """Play `count` short beeps — the count encodes the mode number."""
    wav = os.path.join(script_dir, 'beep.wav')
    for i in range(count):
        for cmd in (['paplay', wav], ['aplay', wav], ['play', wav]):
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=2)
                break
            except Exception:
                continue
        time.sleep(0.15)
    time.sleep(0.35)  # gap after the count, before the refresh


def _ensure_helper(logger):
    def _up():
        h = HelperClient(logger)
        ok = h.connect(SOCKET_PATH, timeout=2.0, quiet=True)
        h.close()
        return ok

    deadline = time.time() + 10.0
    while not _up() and time.time() < deadline:
        time.sleep(0.5)
    if _up():
        return True
    logger.info("helper not running — starting via pkexec")
    try:
        subprocess.Popen(['pkexec', 'tinta4plusu-helper'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"could not launch helper: {e}")
        return False
    deadline = time.time() + 20.0
    while not _up() and time.time() < deadline:
        time.sleep(0.5)
    return _up()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger('probe-modes')

    if not _ensure_helper(logger):
        print('helper daemon not running', file=sys.stderr)
        return 1

    helper = HelperClient(logger)
    if not helper.connect(SOCKET_PATH, timeout=120.0):
        print('could not connect to helper daemon', file=sys.stderr)
        return 1

    # Stop any running carousel so it can't overwrite the probe's images
    try:
        helper.send_command('carousel-stop')
    except Exception:
        pass

    # Pre-load the gradient + checkerboard once (fast, no per-mode upload)
    grad = os.path.join(script_dir, 'tcon-protocol', 'gradient.png')
    check = os.path.join(script_dir, 'tcon-protocol', 'checkerboard.png')
    for buf, img, name in ((1, grad, 'gradient'), (2, check, 'checkerboard')):
        if os.path.isfile(img):
            helper.send_command('show-image', path=img, buffer=buf)
            print(f'upload {name} -> buffer {buf}', flush=True)

    for m in CANDIDATE_MODES:
        print(f'=== mode {m} : {MODE_DETAILS.get(m, "unknown")} ===', flush=True)
        beep(m)  # N beeps = mode N
        try:
            helper.send_command('display-area', x=0, y=0, w=2560, h=1600, mode=m, buffer=1)
            time.sleep(2.0)
            helper.send_command('display-area', x=0, y=0, w=2560, h=1600, mode=m, buffer=2)
            print(f'  alternated BUF1 (GRADIENT) -> BUF2 (CHECKER)', flush=True)
        except Exception as e:
            print('  error:', e)
        time.sleep(PAUSE)

    print('done. Per mode: flash+clean = GC16 (slow); instant+ghost = A2/DU (fast).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
