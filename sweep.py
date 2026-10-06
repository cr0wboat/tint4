#!/usr/bin/env python3
"""Sweep a spatial refresh-wave pattern across the eInk via the helper daemon.

Uploads the image once, then reveals it tile-by-tile in the pattern's order
(edge-aware / ripple / center-radiation / center-spiral / rectangular-grad /
clockwise-grad / diagonal-grad).

Usage: sweep.py IMAGE [--pattern P] [--mode N] [--tile N] [--delay S] [--buffer 1|2]
"""
import sys
import os
import time
import subprocess
import logging

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from HelperClient import HelperClient
from RefreshPatterns import PATTERNS

SOCKET_PATH = '/tmp/tinta4plusu.sock'


def _ensure_helper(logger):
    def _up():
        h = HelperClient(logger)
        ok = h.connect(SOCKET_PATH, timeout=2.0, quiet=True)
        h.close()
        return ok

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
    while time.time() < deadline:
        if _up():
            return True
        time.sleep(0.5)
    return False


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger('sweep')

    args = sys.argv[1:]

    def flag(name, default):
        if name in args:
            i = args.index(name)
            return args[i + 1]
        return default

    if len(args) < 1:
        print(f'usage: sweep.py IMAGE [--pattern P] [--mode N] [--tile N] [--delay S] [--buffer 1|2]',
              file=sys.stderr)
        print('patterns:', ', '.join(PATTERNS), file=sys.stderr)
        return 1

    path = os.path.abspath(args[0])
    pattern = flag('--pattern', 'ripple')
    mode = int(flag('--mode', 6))
    tile = int(flag('--tile', 256))
    delay = float(flag('--delay', 0.02))
    buffer = int(flag('--buffer', 1))

    if pattern not in PATTERNS:
        print(f'unknown pattern {pattern!r}; choose from {list(PATTERNS)}', file=sys.stderr)
        return 1
    if not os.path.isfile(path):
        print(f'not a file: {path}', file=sys.stderr)
        return 1
    if not _ensure_helper(logger):
        print('helper daemon not running', file=sys.stderr)
        return 1

    helper = HelperClient(logger)
    if not helper.connect(SOCKET_PATH, timeout=120.0):
        print('could not connect to helper daemon', file=sys.stderr)
        return 1

    t0 = time.time()
    resp = helper.send_command('sweep', path=path, pattern=pattern, mode=mode,
                               tile=tile, delay=delay, buffer=buffer)
    dt = time.time() - t0
    if resp and resp.get('success'):
        print(f'OK ({dt * 1000:.0f}ms):', resp.get('message'))
        return 0
    print('FAILED:', resp)
    return 1


if __name__ == '__main__':
    sys.exit(main())
