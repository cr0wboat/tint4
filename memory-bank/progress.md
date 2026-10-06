# Progress — tint4

## Done
- 2026-10-05: **T-CON USB image upload + display WORKS on Linux** (first time —
  the original May 2026 blocker "upload succeeds but never displays" is solved).
  `tcon-protocol/tcon.py`: 67×0xA5 chunks (no ZLP, plain address `0x0237F5D0 +
  idx*0xF000`) + a 0x34 mailbox payload pointing at buffer 1 renders a 2560×1600
  image with the OLED untouched. Status reg cycle: `50 00 45 89` (idle) →
  `00 00 45 89` (busy) → `50 00 45 89` (idle).
- 2026-10-05: **Grayscale carousel works end-to-end** via the helper daemon
  (`carousel-start`/`carousel-stop`; enable-once + re-upload + 0x34 per frame;
  watchdog reset each ≤30s). tint4 decluttered into a focused cover-display
  tool — old first-wave code + funkypitt's display-switching layer moved to
  `archive/`. Root now: EInkUSBController, ECController, HelperDaemon,
  HelperClient, WatchdogTimer, GlobalHotkeyListener, show-image.py, carousel.py.
- 2026-10-06: **Refresh-mode map confirmed on hardware** via phone-video analysis
  (Goertzel beep segmentation + frame mean/std flash detection): mode 1=DU,
  2=GC16, 3=GL16, 4=GLR16, 6=A2, 7=GL4, 8=invalid. Fast modes = 6 (A2) and 1 (DU).
  Technique documented in tcon-protocol/PROTOCOL.md.
- 2026-10-06: **Partial write implemented** — `write_bytes`/`write_region` +
  `display_area(region)` + `partial` command + `partial.py`. Partial region
  update works AFTER an `enable_eink()` (square rendered), but does NOTHING
  without a prior enable — remaining blocker for 4 Hz animation (see
  activeContext.md).
- 2026-10-06: **Environment audited (host vs sandbox)** — the Cline shell is a
  Flatpak VSCodium sandbox (Python 3.13, `/usr` read-only, no sudo/pkexec, T-CON
  O_RDWR denied) so hardware probing can't run there. The **HOST** (Linux Mint,
  Python 3.12) already has every daemon dep: python3-usb/evdev/pil (apt) + portio
  0.6.2 (`/usr/local/lib/python3.12`); `sudo python3 HelperDaemon.py` is the runtime.
  Sandbox pyusb/evdev/portio (user-site) are import/syntax aids only.
- 2026-10-06: **Code analysis of the "nothing" blocker** — refined hypothesis:
  `partial_image()` writes into the same buffer it displays (buffer 1), so the A2
  diff is empty after a full display. Fix = ping-pong the two buffers (write to
  alternate 0x027675D0) or re-establish previous frame with GC16. See activeContext.

## In progress
<!-- Started but not finished. -->

## Next
<!-- Queued work. -->

## Known issues / blockers
<!-- Open problems and what blocks them. -->

## Migrated from `bd remember`
- Architecture: Two-process model — Tinta4Plus.py (tkinter GUI, user) ↔ Unix socket (/tmp/tinta4plusu.sock) ↔ HelperDaemon.py (root via pkexec). 9 modules total: GUI, Daemon, DisplayManager, ThemeManager, HelperClient, ECController, EInkUSBController, EInkImageController, CarouselManager, WatchdogTimer, GlobalHotkeyListener.
- Hardware: Lenovo ThinkBook Plus Gen 4 IRU. OLED 2880x1800 eDP-1, color eInk 2560x1600 eDP-2. T-CON USB VID 048d PID 8957, EP OUT 0x02, EP IN 0x81. EC ports 0x66/0x62.
- T-CON is 'Generic Storage RamDisc 1.00' over WinUSB. Uses Bulk-Only Transport with CBW/CSW. Command codes: 0x81 ReadMem, 0x83 ReadReg, 0xA5 WriteMem, 0xA8 Mailbox, 0xA9 MailboxRead. Universal CBWCB format: FE 00 <addr_BE4> <opcode> <len_BE2> 00...
- Windows protocol confirmed from USBPcapCMD captures: Init A8→A9→A8→A9→83, then 67×A5 chunks (61KB each, D0 flag, counter addressing), commit→A8→A9→A8→A9→0x94 display trigger. ZLP between CBW→data and data→CSW.
- Critical pitfall: Windows-captured init payloads (INIT_PAYLOAD_1/2) and display payload are TOXIC on this T-CON firmware — they permanently hang the IN endpoint. Only full USB reset recovers. Never send them.
- Critical pitfall: 0xA8 zero-payload keepalive to cold T-CON hangs IN endpoint. Only send keepalives after enable-eink has succeeded. Gate on eink_enabled=True.
- Known: T-CON disappears after suspend/lid close. Workaround: restart daemon or full app. Future fix: PrepareForSleep D-Bus listener calling reconnect().
- Key files: /opt/tinta4plusu symlinks to this repo. Edit here, runs there. Clear __pycache__/ after every Python edit. Never cp files to /opt.
- Build: PyInstaller 6.19.0, Python 3.12.3. Two spec files: tinta4plusu.spec (GUI, console=False), tinta4plusu-helper.spec (daemon, console=True). Build with bash build.sh.
- 2026-07-28: Tinta4PlusU passed off to funkypitt for continued work on the eInk display protocol. Key unsolved: image upload succeeds but panel never displays — likely missing SDRAM-to-SPI-flash copy step or display trigger sequence. Full Windows protocol analysis done (A5 CBWCB, 67-chunk, D0 flag, ZLP delimiters). See EInkUSBController.py and CONTRIBUTIONS.md for all findings.

