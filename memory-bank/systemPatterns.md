# System Patterns — tint4

## Architecture / layout
<!-- How the system is put together. -->

## Pinouts & bus topology
<!-- Explicit electrical topography: pin -> signal -> destination. -->

## Recurring patterns
- Two frame buffers (ping-pong): buffer 1 = 0x0237F5D0 (upload target), buffer 2 =
  0x027675D0 (enable-sequence display pointer); Δ = 0x3E8000 = one 2560×1600 frame.
  Full display = mode 5 → buffer 1. Partial/A2 must write the ALTERNATE buffer and
  display from it, else the A2 diff is empty.

## Environment quirks (verified 2026-10-06)
- THREE Pythons: **daemon = 3.14** (`sudo python3` / `sudo python3 -m pip`),
  **apt/system = 3.12** (bare `sudo pip` → `/usr/lib/python3/dist-packages`),
  **sandbox = 3.13** (Flatpak VSCodium, `/usr` read-only, no sudo/pkexec, T-CON
  `/dev/bus/usb/003/002` O_RDWR denied). The daemon runs on 3.14 and sees
  `/usr/local/lib/python3.14/dist-packages`; it does NOT see apt's dir.
- Hardware probing + the daemon run on the HOST; the sandbox is analysis/tooling only.

## Session rules (learned 2026-10-06 — do not repeat)
- Diagnose the interpreter FIRST: `sudo python3 -c "import sys; print(sys.executable, sys.version); [print(p) for p in sys.path]"` before any env/install work.
- Always `sudo python3 -m pip install …`; never bare `pip` / `sudo pip` (binds to the wrong Python and reports a false "already satisfied").
- Tag every env fact `[host]` vs `[sandbox]`; never write a sandbox fact into the host's durable record. Verify before editing memory-bank.
- Clear `__pycache__/` after Python edits — note host `sudo python3` makes it root-owned (cpython-314), so clear from the HOST with `sudo rm -rf __pycache__` (the sandbox can't write it).

## Known quirks / gotchas
<!-- Things that bite. -->

## Reusable components discovered here
<!-- Promote to shared store with: bd components add "..." --tags "..." --origin tint4 -->
