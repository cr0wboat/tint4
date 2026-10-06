# T-CON USB Protocol — corrected working notes

Reverse-engineering the Lenovo ThinkBook Plus Gen 4 IRU eInk T-CON
(USB `048d:8957`) to upload and display images directly, without switching
the display output (the goal: clean login splash + carousel + boot image).

## Sources
- funkypitt/Tinta4Plus-Universal `tcon-protocol.md` (corrected re-derivation)
- Windows `EInkTcon.dll` reverse-engineering (72 exports)
- Two USBPcap captures (`captures/tcon-capture.pcap`, `captures/capture2`)
- funkypitt's proven `EInkUSBController.py` (enable/disable/mailbox)

## Transport
USB Bulk-Only Transport (BOT): 31-byte CBW (`USBC`), optional data phase,
13-byte CSW (`USBS`). The 16-byte command block starts `FE 00` with the opcode
at byte 6.

## Opcodes

| Opcode | Dir | CBWCB (16 bytes) | Data phase |
|--------|-----|------------------|-----------|
| 0xA8 | OUT | `FE 00 00 00 00 00 A8 00 00 00 00 00 00 00 00 00` | 36-byte mailbox |
| 0xA9 | IN  | `FE 00 00 00 00 00 A9 00 00 04 00 00 00 00 00 00` | 4 bytes (`03 00 00 00`) |
| 0x83 | IN  | `FE 00 18 00 13 C0 83 00 04 00 00 00 00 00 00 00` | 4 bytes (status) |
| 0xA5 | OUT | `FE 00 <addr_BE4> A5 <len_BE2> 00 00 00 00 00 00 00` | `len` bytes pixel data |
| 0x81 | IN  | `FE 00 <addr_BE4> 81 <len_BE2> ...` | ReadMem (format unconfirmed) |

## 0xA5 FAST_WRITE_MEM — corrected
- Address = plain 32-bit big-endian at CBWCB[2:6].
- Starts `0x0237F5D0`, advances `0xF000` per chunk.
- 67 chunks: 66 × `0xF000` (61440) + 1 × `0xA000` (40960) = 4,096,000 bytes.
- **No ZLP delimiters** (zero-length records in USBPcap are completion-log
  artifacts, not real packets).
- **No "D0 flag"** — `D0` is just the low byte of `0x0237F5D0`.

## Two frame buffers (the key to displaying an uploaded image)

| Buffer | Address | Used by |
|--------|---------|---------|
| 1 | `0x0237F5D0` | 0xA5 upload target |
| 2 | `0x027675D0` | enable sequence's 0x34 display pointer |

Δ = `0x3E8000` = exactly one 4,096,000-byte frame.

The 0x34 mailbox payload carries width (2560), height (1600), and the buffer
address it points the panel at:
- Enable sequence → `d0 75 76 02` = `0x027675D0` (buffer 2).
- "Show logo"    → `d0 f5 37 02` = `0x0237F5D0` (buffer 1).

### Display trigger — CONFIRMED 2026-10-05
After uploading to buffer 1, send the 0x34 payload pointing at buffer 1.
funkypitt's `DISABLE_EINK` even contains it commented out as "the show thinkbook
logo command":

```
34 00 9b be 00 00 00 00 00 0a 40 06 05 00 d0 f5 37 02
00 00 00 00 00 00 40 06 00 00 00 00 00 00 40 f7 9f f6
```

This is the missing step behind "upload succeeds but never displays."

**CONFIRMED 2026-10-05:** a 67-chunk upload followed by this 0x34 payload rendered
a 2560×1600 test pattern on the panel, OLED untouched. No 0x94 or extra A8/A9
commit handshake was needed.

### Display-area command (0x34) — decoded from EInkTcon.dll (2026-10-05)

`ITEDisplayAreaAPI(x, y, w, h, mode, buffer_addr, wait)` builds this 0x34 mailbox:

```
34 00 ?? ?? | X:u16 | Y:u16 | W:u16 | H:u16 | mode:u16 | buffer_addr:u32 LE | 00 00 ...
```

- X/Y/W/H: region (DLL enforces W ≤ 2560, H ≤ 1600).
- mode: refresh/LUT selection. **mode = 5** = full-screen grayscale (our SHOW_BUF1).
  Fast modes (A2/DU) use other values — not yet mapped.
- buffer_addr: source SDRAM buffer (0x0237F5D0 = buffer 1, 0x027675D0 = buffer 2).

**Partial refresh = same 0x34 with a sub-region + fast mode** (plus writing only that
region's pixels). `ITESetFA2` (cmd 0x4b, payload `4b 00 [on/off:u16] 06 00 06 00`)
toggles the A2 fast mode. Mode values for A2/DU are the remaining unknown.

### Refresh modes (LUT) — hardware-confirmed 2026-10-06

The 0x34 display-area `mode` field selects the waveform/LUT. Confirmed against the
standard IT8951 table by probing each value on hardware (see video-analysis note):

| mode | Type | Refresh |
|------|------|---------|
| 1 | DU | 1-bit, fast/instant, ghosting |
| 2 | GC16 | full 16-gray, flash (white→black) |
| 3 | GL16 | 16-gray, flash |
| 4 | GLR16 | 16-gray, flash |
| 5 | GLD16 | 16-gray + dither (default full display) |
| 6 | A2 | 1-bit, fast/instant |
| 7 | GL4 | 4-gray, flash |
| 8 | — | invalid (no-op / black) |

Fast modes for animation / partial refresh: **6 (A2)** and **1 (DU)**.

### Video-analysis technique (reusable)

To reverse-engineer refresh modes without a USB capture:
1. Record the panel (phone video) while a probe plays N beeps then displays each
   candidate mode.
2. Extract audio; detect the 880 Hz beep bursts with a **Goertzel filter** →
   segment the video into per-mode regions (beep count = mode number).
3. Extract frames (~10 fps), compute per-frame **mean/std** brightness. A FLASH
   (GC16) shows a transient spike→dip at the transition (panel clears white then
   black); an INSTANT (A2/DU) shows a flat/monotonic change.

### Status register (0x83 @ 0x180013C0)
| Value | Meaning |
|-------|---------|
| `50 00 45 89` | idle/ready (also the boot-time value) |
| `00 00 45 89` | busy (after write, before display) |
| `45 89` (tail) | constant — device/firmware marker |

Observed cycle: idle → (write) → busy → (0x34 display) → idle.

## Enable sequence (proven)
12 × 36-byte 0xA8 mailbox payloads (`ENABLE_EINK`), back-to-back with ~50ms
gaps. Payload #5 is the 0x34 buffer-2 pointer. Never send keepalive to a cold
T-CON.

## Pitfalls (do not repeat)
- Windows-captured INIT_PAYLOAD_1/2 and DISPLAY_PAYLOAD hang this firmware's
  IN endpoint permanently — never send them.
- 0xA8 zero-payload keepalive to a cold T-CON hangs the IN endpoint.
- USB reset (`_reset_device`) drops the T-CON off the bus.
- Preemptive `CLEAR_FEATURE(ENDPOINT_HALT)` is not in the captures — don't send it.
- `enable_eink()` clears the panel to white (its 0x34 points at empty buffer 2).
  Enable ONCE, then do partial `write_region` + `display_area` without re-enabling.

## Open questions
- Does the corrected 0xA5 write (no ZLP) avoid the old ~95s crash?
- Does the 0x34 buffer-1 trigger actually render the uploaded frame?
- 0x81 ReadMem returned a CSW instead of data — CBWCB needs work.
- SPI flash (`IT8951SFIPageWriteAPI`) for a persistent boot image — unexplored.

## Test plan (incremental, hardware-gated)
1. connect + enable-eink + 0x83 status poll (proven).
2. single 0xA5 chunk (no ZLP) → poll 0x83 → no crash.
3. 10 → 67 chunks.
4. 0x34 buffer-1 trigger → image renders.
5. SPI flash persistence.

## Analysis tooling

Runnable version of the video-analysis technique: `analyze_refresh.py` (this
directory). Run `python3 analyze_refresh.py VIDEO` to get the beep-mode boundaries
plus a per-frame mean/std timeline.
