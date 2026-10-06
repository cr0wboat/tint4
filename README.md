# tint4

Custom-image controller for the Lenovo ThinkBook Plus Gen 4 IRU **color eInk**
cover display. Shows grayscale images directly on the eInk via the USB T-CON
**while the OLED stays the primary display** — no display switching, no window
churn.

The T-CON USB image-upload protocol was reverse-engineered here (see
`tcon-protocol/PROTOCOL.md`). Lineage: fork of
[Tinta4Plus](https://github.com/joncox123/Tinta4Plus) by **Jon Cox**, extended
by **funkypitt** ([Tinta4Plus-Universal](https://github.com/funkypitt/Tinta4Plus-Universal)),
then re-focused here on direct T-CON upload.

## Architecture

Two-process model (as upstream):

- `HelperDaemon.py` — privileged daemon (root via pkexec): owns the T-CON USB
  and frontlight EC, serves a Unix socket (`/tmp/tinta4plusu.sock`).
- `show-image.py` / `carousel.py` — unprivileged CLIs that talk to the daemon.

## Files

| File | Role |
|------|------|
| `EInkUSBController.py` | T-CON USB: enable/disable, 0xA5 upload, 0x34 display trigger |
| `ECController.py` | frontlight/brightness (EC ports 0x66/0x62) |
| `HelperDaemon.py` | socket server: `show-image`, `carousel-start/stop`, etc. |
| `HelperClient.py` | socket client (JSON, length-prefix framing) |
| `WatchdogTimer.py` | daemon idle watchdog |
| `show-image.py` | show one image on the eInk |
| `carousel.py` | rotate images in a directory |
| `tcon-protocol/` | protocol research (`PROTOCOL.md` + `tcon.py` reference) |

## Usage

```bash
# start the daemon (root)
pkexec python3 HelperDaemon.py &

# show one image
python3 show-image.py /path/to/image.jpg

# carousel (rotate every 30s)
python3 carousel.py start /path/to/images 30
python3 carousel.py stop
```

Images are converted to **2560×1600 grayscale** (1 byte/pixel). Color requires
CFA mapping (`CFA_mapping.dll` equivalent) — future work; grayscale displays
crisp but with CFA color-fringe texture (see PROTOCOL.md).

## Protocol (summary)

67 × `0xA5` FAST_WRITE_MEM chunks (61 KB each, **no ZLP**, plain address
`0x0237F5D0 + idx×0xF000`) into buffer 1, then a single `0x34` mailbox payload
pointing at buffer 1 renders the image. Full details + pitfalls in
`tcon-protocol/PROTOCOL.md`.

## Warning

Writes to low-level hardware (Embedded Controller, USB T-CON). Use entirely at
your own risk — see upstream EULA.
