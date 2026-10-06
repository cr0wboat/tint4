# Decision Log — tint4

Format: `[Decision] -> [Constraint] -> [Alternative Failure Path]`

## Log
- 2026-10-06 `[Install pyusb/evdev/portio to user site]` -> `[sandbox /usr is read-only + no sudo/pkexec, so system-wide install is impossible]` -> `[daemon still needs root+O_RDWR; hardware must run on host, packages only aid import/syntax checks here]`
- 2026-10-06 `[Refine "nothing" blocker to ping-pong buffer hypothesis]` -> `[partial_image writes+displays the same buffer (buffer 1), so A2 diff is empty after a full display]` -> `[write region to alternate buffer 0x027675D0, or GC16 re-display before A2]`
