# Active Context — tint4

## Current focus
tint4 is now a focused **custom eInk cover-display** tool: upload grayscale
images to the T-CON over USB and show them while the OLED stays primary. No
display switching.

## Recent changes
- 2026-10-05: Solved "upload succeeds but never displays" — corrected 0xA5
  write (no ZLP) + 0x34 buffer-1 display trigger. Integrated as
  `show-image` / `carousel-start` socket commands in HelperDaemon.
- 2026-10-05: Decluttered — moved first-wave code + funkypitt's display-switching
  layer (GUI, DisplayManager, reader, indicator, etc.) to `archive/`. tint4
  root now holds only the focused core (EInkUSBController, ECController,
  HelperDaemon, HelperClient, WatchdogTimer, show-image.py, carousel.py).

## Active constraints (CORRECTED 2026-10-06)
- Dev shell is a **Flatpak VSCodium sandbox** (`app-flatpak-com.vscodium.codium`).
  `/usr` is READ-ONLY; **no `sudo`, no `pkexec`**. System Python is now **3.13.15**
  (was 3.12 — the upgrade broke `.venv` and dropped system-wide pyusb/evdev/portio).
- pyusb 1.3.1 / evdev / portio now installed to the **user site** (flatpak path)
  and import as `mds` — but the T-CON `/dev/bus/usb/003/002` opens **O_RDONLY only**;
  **O_RDWR is denied** by the sandbox. Hardware probing must run on the **HOST**
  (outside the sandbox), as before.
- `evdev` is a SOFT dep (GlobalHotkeyListener disables hotkeys if absent).
- Helper daemon needs root (euid==0) + T-CON O_RDWR + EC `ioperm` — none available
  from inside the sandbox.
- T-CON USB (048d:8957 "ITE T-CON") is owned by the helper; keep the GUI closed
  when using the standalone `tcon.py` reference tool.

## Hardware state
- ThinkBook Plus Gen 4: OLED eDP-1 (2880x1800), color eInk eDP-2 (2560x1600).
- T-CON USB EP OUT 0x02 / IN 0x81. Upload buffer 0x0237F5D0, display pointer
  0x027675D0. Status reg 0x83 @ 0x180013C0 cycles 50↔00 (idle/busy), tail 45 89.

## Next step — ANIMATION (partial refresh → 4 Hz)

Handoff for the animation task.

**Implemented & working:**
- Full-frame upload + display (`show-image`, mode 5) ✅
- Refresh-mode map confirmed: mode 6 (A2) and 1 (DU) are the fast/instant modes ✅
- `write_region(x,y,w,h,raw)` + `display_area(x,y,w,h,mode,buf)` + `partial` socket
  command + `partial.py` CLI (all in place, syntax-checked).

**Remaining blocker (the "nothing" result):**
The partial update `write_region` + `display_area(region, mode=6 A2)` produced
**no visible change** when run right after a `show-image` (no re-enable). By
contrast, the *buggy* version — which called `enable_eink()` first — DID show the
200×200 checkerboard square (but on a white panel, because enable clears the
panel to white via its 0x34→buffer2).

So: region write+display works *after* an enable/clear, but not after a normal
full display. To investigate (next agent):
1. Does A2 (mode 6) region refresh require a prior full GC16 clear?
2. Is `x/y/w/h` alignment required (e.g. 16-byte or full-row)?
3. Is `write_region`'s row addressing correct? (address = buf + (y+r)*2560 + x)
4. Does the T-CON compare against a "previous frame" buffer pointer that we
   haven't set (ITECpyImageAPI / second buffer)?

**REFINED root-cause hypothesis (2026-10-06, from code analysis — needs HW verify):**
`partial_image()` writes the region into the **SAME buffer it is currently
displaying** (`BUF_UPLOAD` = buffer 1 = 0x0237F5D0), then `display_area(mode=6,
buffer=buffer1)`. The A2/partial LUT diffs the new region against the
previous-frame buffer. After a full `show-image` (mode 5 → buffer 1), the
previous frame IS buffer 1, so the in-place overwrite makes new==previous →
empty diff → **nothing renders**. After `enable_eink()` the panel points at
buffer 2 (empty/white), so writing buffer 1 + displaying from buffer 1 produces
a visible diff (the 200×200 square on white). This is hypothesis #4 with a
concrete mechanism.
**Fix to test (ping-pong):** write the region to the ALTERNATE buffer
(0x027675D0) and `display_area(..., buffer=alt)`, OR re-establish the previous
frame with a full GC16 re-display before A2 partials. Requires a `buffer=`
param on `partial_image`/`partial` (currently hardcoded to buffer 1).

**Proposed animation loop (once blocker resolved):**
```
enable_eink()  # once
loop: write_region(x,y,w,h) → display_area(x,y,w,h, mode=6) → sleep 0.25s
```
(run inside the helper, resetting the watchdog per frame like `_carousel_loop`).

**Other optional items (unchanged):**
- SPI-flash persistent boot image.
- Color via CFA mapping (replicate `CFA_mapping.dll`).
- Auto-start helper from CLIs.

