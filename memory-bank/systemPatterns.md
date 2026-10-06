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

## Environment quirks
- Two environments: **HOST** (Linux Mint, Python 3.12, all daemon deps present,
  sudo works) vs **SANDBOX** (Flatpak VSCodium, Python 3.13, `/usr` read-only, no
  sudo/pkexec, `/dev/bus/usb/003/002` O_RDWR denied). Daemon + hardware probing run
  on the HOST; the sandbox is analysis/tooling only.

## Known quirks / gotchas
<!-- Things that bite. -->

## Reusable components discovered here
<!-- Promote to shared store with: bd components add "..." --tags "..." --origin tint4 -->
