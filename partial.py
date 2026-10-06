#!/usr/bin/env python3
"""Partial-region update: write + display a sub-region of the eInk.

Usage: partial.py IMAGE [--x N] [--y N] [--w N] [--h N] [--mode N]
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
    logger = logging.getLogger('partial')

    args = sys.argv[1:]

    def flag(name, default):
        if name in args:
            i = args.index(name)
            return int(args[i + 1])
        return default

    if len(args) < 1:
        print('usage: partial.py IMAGE [--x N] [--y N] [--w N] [--h N] [--mode N]',
              file=sys.stderr)
        return 1

    path = os.path.abspath(args[0])
    x = flag('--x', 0)
    y = flag('--y', 0)
    w = flag('--w', 2560)
    h = flag('--h', 1600)
    mode = flag('--mode', 6)

    if not os.path.isfile(path):
        print(f'not a file: {path}', file=sys.stderr)
        return 1

    if not _ensure_helper(logger):
        print('helper daemon not running', file=sys.stderr)
        return 1

    helper = HelperClient(logger)
    if not helper.connect(SOCKET_PATH, timeout=120.0):
        print('could not connect', file=sys.stderr)
        return 1

    t0 = time.time()
    resp = helper.send_command('partial', x=x, y=y, w=w, h=h, mode=mode, path=path)
    dt = time.time() - t0
    if resp and resp.get('success'):
        print(f'OK ({dt * 1000:.0f}ms):', resp.get('message'))
        return 0
    print('FAILED:', resp)
    return 1


if __name__ == '__main__':
    sys.exit(main())
