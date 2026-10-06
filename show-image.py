#!/usr/bin/env python3
"""Show an image on the eInk via the helper daemon (no display switching).

Sends the 'show-image' socket command, which uploads the image to T-CON
buffer 1 and displays it with the OLED untouched. See tint4 tcon-protocol/.

Usage: show-image.py IMAGE_PATH
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
    logger = logging.getLogger('show-image')

    if len(sys.argv) < 2:
        print('usage: show-image.py IMAGE_PATH', file=sys.stderr)
        return 1

    path = os.path.abspath(sys.argv[1])
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

    try:
        resp = helper.send_command('show-image', path=path)
    except Exception as e:
        print(f'error: {e}', file=sys.stderr)
        return 1

    if resp and resp.get('success'):
        print('OK:', resp.get('message'))
        return 0
    print('FAILED:', resp)
    return 1


if __name__ == '__main__':
    sys.exit(main())
