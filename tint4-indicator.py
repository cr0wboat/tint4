#!/usr/bin/env python3
"""
tint4 tray indicator — carousel status + preference management.

Sits in the panel as a StatusNotifier/AppIndicator icon. Talks to HelperDaemon
over the Unix socket via HelperClient (no D-Bus, no root). On --autostart it
starts the carousel with the saved preferences, so logging in restores the
eInk slideshow automatically.

Preferences persist to ~/.config/tint4/config.json.

Menu:
  - status line (carousel running / current image / daemon state)
  - Start / Stop carousel
  - Image folder…
  - Interval (submenu)
  - Refresh mode (submenu)
  - Brightness (submenu)
  - Quit

Depends on: gir1.2-ayatanaappindicator3-0.1 (or gir1.2-appindicator3-0.1) + GTK3.
"""

import os
import sys
import json
import logging
import subprocess

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib  # noqa: E402

try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # noqa: E402
except (ValueError, ImportError):
    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3  # noqa: E402
    except (ValueError, ImportError):
        AppIndicator3 = None

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from HelperClient import HelperClient  # noqa: E402

SOCKET_PATH = '/tmp/tinta4plusu.sock'
ICON_DIR = os.path.join(HERE, 'icons')
CONFIG_DIR = os.path.expanduser('~/.config/tint4')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
POLL_S = 2

ICON_RUNNING = 'tinta4plusu-eink-symbolic'
ICON_STOPPED = 'tinta4plusu-off-symbolic'

MODE_NAMES = {
    5: 'GLD16 (default)', 2: 'GC16 (flash)', 6: 'A2 (fast)', 1: 'DU (fast)',
    3: 'GL16', 4: 'GLR16', 7: 'GL4',
}
INTERVALS = [5, 15, 30, 60, 300, 900, 1800, 3600]

# How to (re)start the daemon when the socket is down. Overridable in config.
# The CLI tools use `pkexec tinta4plusu-helper`; to run the source daemon set
# daemon_cmd to ["pkexec", "python3", "/path/to/HelperDaemon.py"].
DEFAULT_DAEMON_CMD = ['pkexec', 'tinta4plusu-helper']

DEFAULT_CONFIG = {
    'image_dir': os.path.expanduser('~/Pictures/eink'),
    'interval': 60,
    'mode': 5,
    'brightness': 4,
    'daemon_cmd': DEFAULT_DAEMON_CMD,
}

log = logging.getLogger('tint4-indicator')


def _fmt_interval(sec):
    if sec < 60:
        return f'{sec}s'
    if sec < 3600:
        return f'{sec // 60}m'
    return f'{sec // 3600}h'


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    out = dict(DEFAULT_CONFIG)
    out.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG})
    return out


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        log.warning(f'could not save config: {e}')


class Tint4Indicator:
    def __init__(self, autostart=False):
        self.autostart = autostart
        self.config = load_config()
        self.client = HelperClient(log)
        self._updating = False
        self._connected = False
        self._carousel = None
        self._daemon_starting = False

        self.ind = AppIndicator3.Indicator.new(
            'tint4', ICON_STOPPED, AppIndicator3.IndicatorCategory.HARDWARE)
        self.ind.set_icon_theme_path(ICON_DIR)
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_title('tint4 eInk')

        self._build_menu()
        self._poll()
        GLib.timeout_add_seconds(POLL_S, self._poll)
        if autostart:
            GLib.timeout_add_seconds(3, self._autostart)

    # ------------------------------------------------------------------
    # Daemon plumbing
    # ------------------------------------------------------------------

    def _ensure_connected(self):
        if self.client.is_connected():
            return True
        if self.client.connect(SOCKET_PATH, timeout=2.0, quiet=True):
            return True
        if not self._daemon_starting:
            self._daemon_starting = True
            cmd = self.config.get('daemon_cmd') or DEFAULT_DAEMON_CMD
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                log.info(f'starting daemon: {cmd}')
            except Exception as e:
                log.error(f'could not start daemon: {e}')
        return False

    def _send(self, command, **params):
        if not self._ensure_connected():
            return None
        try:
            return self.client.send_command(command, **params)
        except Exception as e:
            log.error(f'{command} failed: {e}')
            return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_carousel(self, _w=None):
        running = bool(self._carousel and self._carousel.get('running'))
        if running:
            self._send('carousel-stop')
        else:
            self._start_carousel()
        self._poll()

    def _start_carousel(self):
        self._send('carousel-start', dir=self.config['image_dir'],
                   interval=self.config['interval'], mode=self.config['mode'])

    def _restart_carousel(self):
        """Re-apply interval/mode/folder to a running carousel."""
        if self._carousel and self._carousel.get('running'):
            self._send('carousel-stop')
            self._start_carousel()

    def _set_interval(self, _w, sec):
        self.config['interval'] = sec
        save_config(self.config)
        self._restart_carousel()
        self._poll()

    def _set_mode(self, _w, mode):
        self.config['mode'] = mode
        save_config(self.config)
        self._restart_carousel()
        self._poll()

    def _set_brightness(self, _w, level):
        self.config['brightness'] = level
        save_config(self.config)
        self._send('set-brightness', level=level)
        self._poll()

    def _choose_folder(self, _w=None):
        dlg = Gtk.FileChooserDialog(
            title='Choose image folder', action=Gtk.FileChooserAction.SELECT_FOLDER)
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dlg.set_current_folder(self.config['image_dir'])
        if dlg.run() == Gtk.ResponseType.OK:
            self.config['image_dir'] = dlg.get_filename()
            save_config(self.config)
            self._restart_carousel()
        dlg.destroy()
        self._poll()

    def _autostart(self):
        self._ensure_connected()
        if self.client.is_connected():
            self._start_carousel()
        self._poll()
        return False  # one-shot

    def _quit(self, _w=None):
        self.client.close()
        Gtk.main_quit()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_menu(self):
        menu = Gtk.Menu()

        self.it_status = Gtk.MenuItem(label='tint4 — connecting…')
        self.it_status.set_sensitive(False)
        menu.append(self.it_status)

        self.it_toggle = Gtk.MenuItem(label='Start carousel')
        self.it_toggle.connect('activate', self._toggle_carousel)
        menu.append(self.it_toggle)

        menu.append(Gtk.SeparatorMenuItem())

        it_folder = Gtk.MenuItem(label='Image folder…')
        it_folder.connect('activate', self._choose_folder)
        menu.append(it_folder)

        menu.append(self._build_interval_submenu())
        menu.append(self._build_mode_submenu())
        menu.append(self._build_brightness_submenu())

        menu.append(Gtk.SeparatorMenuItem())

        it_quit = Gtk.MenuItem(label='Quit')
        it_quit.connect('activate', self._quit)
        menu.append(it_quit)

        menu.show_all()
        self.ind.set_menu(menu)

    def _build_interval_submenu(self):
        item = Gtk.MenuItem(label='Interval')
        sub = Gtk.Menu()
        group = []
        for sec in INTERVALS:
            r = Gtk.RadioMenuItem.new_with_label(group, _fmt_interval(sec))
            r.connect('activate', self._set_interval, sec)
            if sec == self.config['interval']:
                r.set_active(True)
            sub.append(r)
            group = r.get_group()
        item.set_submenu(sub)
        return item

    def _build_mode_submenu(self):
        item = Gtk.MenuItem(label='Refresh mode')
        sub = Gtk.Menu()
        group = []
        for mode, name in MODE_NAMES.items():
            r = Gtk.RadioMenuItem.new_with_label(group, name)
            r.connect('activate', self._set_mode, mode)
            if mode == self.config['mode']:
                r.set_active(True)
            sub.append(r)
            group = r.get_group()
        item.set_submenu(sub)
        return item

    def _build_brightness_submenu(self):
        item = Gtk.MenuItem(label='Brightness')
        sub = Gtk.Menu()
        group = []
        for level in range(0, 9):
            r = Gtk.RadioMenuItem.new_with_label(group, str(level))
            r.connect('activate', self._set_brightness, level)
            if level == self.config['brightness']:
                r.set_active(True)
            sub.append(r)
            group = r.get_group()
        item.set_submenu(sub)
        return item

    def _poll(self):
        if self.client.is_connected() or self._ensure_connected():
            cs = self._send('carousel-status')
            self._carousel = (cs or {}).get('carousel') if cs else None
            self._connected = True
        else:
            self._carousel = None
            self._connected = False

        self._updating = True
        try:
            if not self._connected:
                self.it_status.set_label('tint4 — daemon not connected')
                self.it_toggle.set_label('Start carousel')
                self.it_toggle.set_sensitive(False)
                self.ind.set_icon_full(ICON_STOPPED, 'tint4: daemon not connected')
            else:
                c = self._carousel
                running = bool(c and c.get('running'))
                if running:
                    cur = c.get('current')
                    name = os.path.basename(cur) if cur else '…'
                    total = c.get('total', 0)
                    self.it_status.set_label(f'tint4 — carousel: {name} ({total})')
                    self.it_toggle.set_label('Stop carousel')
                    self.ind.set_icon_full(ICON_RUNNING, f'tint4: {name}')
                else:
                    self.it_status.set_label('tint4 — carousel stopped')
                    self.it_toggle.set_label('Start carousel')
                    self.ind.set_icon_full(ICON_STOPPED, 'tint4: stopped')
                self.it_toggle.set_sensitive(True)
        finally:
            self._updating = False
        return True  # keep polling


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    if AppIndicator3 is None:
        print('ERROR: AppIndicator binding missing. '
              'Install gir1.2-ayatanaappindicator3-0.1', file=sys.stderr)
        return 1
    Tint4Indicator(autostart='--autostart' in sys.argv)
    Gtk.main()
    return 0


if __name__ == '__main__':
    sys.exit(main())

