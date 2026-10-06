#!/usr/bin/env python3
"""Start/stop the eInk image carousel via the helper daemon.

Usage:
    carousel.py start DIR [INTERVAL]   # rotate images in DIR every INTERVAL s (default 30)
    carousel.py stop
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
    """Ensure the helper is running; start it via pkexec if not.

    Returns True once the socket is up.
    """
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

    logger.info("helper not running — starting via pkexec (a password prompt may appear)")
    try:
        subprocess.Popen(['pkexec', 'tinta4plusu-helper'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        logger.error("pkexec not found — cannot start helper")
        return False
    except Exception as e:
        logger.error(f"could not launch helper: {e}")
        return False

    deadline = time.time() + 20.0
    while not _up() and time.time() < deadline:
        time.sleep(0.5)
    return _up()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger('carousel')

    mode = 5
    if '--mode' in sys.argv:
        mi = sys.argv.index('--mode')
        try:
            mode = int(sys.argv[mi + 1])
        except (IndexError, ValueError):
            print('--mode requires a number', file=sys.stderr)
            return 1
        sys.argv = sys.argv[:mi] + sys.argv[mi + 2:]

    if len(sys.argv) < 2 or sys.argv[1] not in ('start', 'stop'):
        print('usage: carousel.py start DIR [INTERVAL] [--mode N] | carousel.py stop', file=sys.stderr)
        return 1

    if not _ensure_helper(logger):
        print('helper daemon not running', file=sys.stderr)
        return 1

    helper = HelperClient(logger)
    if not helper.connect(SOCKET_PATH, timeout=120.0):
        print('could not connect to helper daemon', file=sys.stderr)
        return 1

    if sys.argv[1] == 'stop':
        resp = helper.send_command('carousel-stop')
    else:
        if len(sys.argv) < 3:
            print('usage: carousel.py start DIR [INTERVAL]', file=sys.stderr)
            return 1
        image_dir = os.path.abspath(sys.argv[2])
        interval = float(sys.argv[3]) if len(sys.argv) > 3 else 30
        resp = helper.send_command('carousel-start', dir=image_dir, interval=interval, mode=mode)

    if resp and resp.get('success'):
        print('OK:', resp.get('message'))
        return 0
    print('FAILED:', resp)
    return 1


if __name__ == '__main__':
    sys.exit(main())
