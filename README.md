# tint4

Custom-image controller for the Lenovo **ThinkBook Plus Gen 4 IRU** color eInk
cover display. Uploads grayscale images directly to the panel's USB T-CON and
shows them **while the OLED stays the primary display** — no display switching,
no window churn.

The T-CON USB image-upload protocol was reverse-engineered here (see
[`tcon-protocol/PROTOCOL.md`](tcon-protocol/PROTOCOL.md)).

> ⚠️ **Use entirely at your own risk.** This writes to low-level hardware (the
> Embedded Controller and the eInk T-CON) and can temporarily or permanently
> damage hardware or expose personal data. See [Safety](#safety).

## Lineage & license

A derivative of [Tinta4Plus](https://github.com/joncox123/Tinta4Plus) by
**Jon Cox**, extended by
[funkypitt](https://github.com/funkypitt/Tinta4Plus-Universal), then re-focused
here on direct T-CON upload + a carousel + a tray indicator.

> **License: pending.** Upstream declares **no license** ("Copyright (c) 2025
> Jon Cox. All rights reserved."). Do not redistribute until this is resolved.

## Status

- ✅ Full-frame upload + display (`show-image`, mode 5)
- ✅ Grayscale carousel (daemon + tray indicator + autostart)
- ✅ Refresh-mode map confirmed on hardware (DU / GC16 / GL16 / GLR16 / GLD16 / A2 / GL4)
- ✅ Spatial refresh-wave patterns (`sweep`: ripple, center-radiation, spiral, …)
- ⚠️ Partial (A2) refresh shows "nothing" after a full display — ping-pong buffer
  fix in progress (4 Hz animation)
- ⏳ Color (CFA mapping) and SPI-flash persistent boot image

## Requirements

- Lenovo ThinkBook Plus Gen 4 IRU (T-CON USB `048d:8957`)
- Linux; **root** for the daemon (EC + USB access)
- Python with `pyusb`, `portio`, `Pillow`, `evdev` (installed by `install.sh`)

## Install

```bash
./install.sh
```

Installs the indicator runtime deps, the login autostart entry, a
"Restart tint4" app-finder launcher, and scaffolds
`~/.config/tint4/config.json`.

## Usage

```bash
# daemon (root)
sudo python3 HelperDaemon.py &

# show one image
python3 show-image.py path/to/image.jpg

# carousel
python3 carousel.py start ~/Pictures/eink 60
python3 carousel.py stop

# partial-region refresh
python3 partial.py image.png --x 0 --y 0 --w 400 --h 400 --mode 6

# spatial refresh-wave sweep (7 patterns)
python3 sweep.py image.png --pattern ripple --mode 2

# tray indicator (status + preferences)
python3 tint4-indicator.py --autostart
```

Images are converted to **2560×1600 grayscale** (1 byte/pixel).

## Files

| File | Role |
|------|------|
| `HelperDaemon.py` | privileged daemon (root): T-CON USB + EC, Unix socket |
| `EInkUSBController.py` | T-CON USB: enable, `0xA5` upload, `0x34` display |
| `ECController.py` | frontlight/brightness (EC ports 0x66/0x62) |
| `RefreshPatterns.py` | spatial refresh-wave orderings (7 patterns) |
| `HelperClient.py` | socket client (JSON, length-prefix framing) |
| `show-image.py` / `carousel.py` / `partial.py` / `sweep.py` | CLIs |
| `tint4-indicator.py` | tray indicator (status + preferences) |
| `install.sh` | one-step setup |
| `tcon-protocol/` | reverse-engineering notes + `analyze_refresh.py` |

## Protocol (summary)

67 × `0xA5` FAST_WRITE_MEM chunks into buffer `0x0237F5D0`, then one `0x34`
mailbox payload pointing at that buffer renders the image. Full details and
pitfalls in [`tcon-protocol/PROTOCOL.md`](tcon-protocol/PROTOCOL.md).

## Safety

- Requires **root**; frontlight needs **Secure Boot disabled**.
- Never send the Windows-captured init/display payloads — they permanently hang
  the IN endpoint (see PROTOCOL.md "Pitfalls").
- If the panel gets stuck, a full reboot usually recovers; see upstream's EC
  reset procedure.
