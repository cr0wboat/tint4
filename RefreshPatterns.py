#!/usr/bin/env python3
"""Spatial refresh-wave patterns for the T-CON partial refresh (display_area).

Each pattern is a deterministic ORDERING of rectangular tiles over the panel.
Sweeping display_area() over the tiles in that order makes the refresh front
move across the panel with that shape.

Reverse-engineered from the "New Refresh Innovations of 10.1-inch E-ink Photo
Frame" video. These are orthogonal to the LUT mode (GC16/A2/DU/...): the mode
selects *how* each pixel transitions + whether the panel flashes, while these
select the *spatial/temporal order* the refresh sweeps.

Patterns:
  edge-aware        changed tiles first (requires old + new frames)
  ripple            round rings expanding from the center
  center-radiation  rayed ("flower") front expanding from the center
  center-spiral     single arm spiraling out from the center
  rectangular-grad  square front expanding from the center (Chebyshev)
  clockwise-grad    angular sweep like a clock hand
  diagonal-grad     diagonal stripe sweep

`old`/`new` for edge-aware are numpy uint8 arrays shaped (height, width).
"""

import math

PATTERNS = (
    'edge-aware', 'ripple', 'center-radiation', 'center-spiral',
    'rectangular-grad', 'clockwise-grad', 'diagonal-grad',
)

# amplitude of the angular "rays" in center-radiation (0..1 fraction of radius)
_RAD_AMP = 0.12


def _tiles(w, h, tw, th):
    """Raster tiles covering (0,0,w,h); right/bottom edges may be smaller."""
    tiles = []
    for y in range(0, h, th):
        for x in range(0, w, tw):
            tiles.append((x, y, min(tw, w - x), min(th, h - y)))
    return tiles


def _edge_aware(tiles, old, new):
    """Order tiles by descending mean absolute change (changed regions first)."""
    import numpy as np
    if old is None or new is None:
        raise ValueError("edge-aware requires old= and new= frames (numpy hxw arrays)")
    diff = np.abs(new.astype(np.float64) - old.astype(np.float64))
    scored = []
    for (x, y, tw, th) in tiles:
        d = float(diff[y:y + th, x:x + tw].mean())
        scored.append((d, y, x, tw, th))
    scored.sort(key=lambda s: (-s[0], s[1], s[2]))  # biggest change first, then raster
    return [(x, y, tw, th) for (_, y, x, tw, th) in scored]


def _key(pattern, dx, dy, r, ang, rmax, rays, turns, diag_deg):
    """Scalar sort key (lower = refresh earlier) for one tile center."""
    rn = r / rmax if rmax else 0.0
    angn = (ang + math.pi) / (2.0 * math.pi)  # 0..1, 0 = pointing left (-x)
    if pattern == 'ripple':
        return rn
    if pattern == 'center-radiation':
        # radius with an angular scallop -> a rayed/spiky front
        return rn * (1.0 + _RAD_AMP * math.cos(rays * ang))
    if pattern == 'center-spiral':
        # one arm that rotates `turns` times while expanding to the edge
        return rn + turns * angn
    if pattern == 'rectangular-grad':
        return (max(abs(dx), abs(dy)) / rmax) if rmax else 0.0
    if pattern == 'clockwise-grad':
        return angn
    if pattern == 'diagonal-grad':
        phi = math.radians(diag_deg)
        return ((dx * math.cos(phi) + dy * math.sin(phi)) / rmax + 0.5) if rmax else 0.5
    raise ValueError(pattern)


def ordered_tiles(pattern, w, h, tile_w=256, tile_h=256, center=None, rays=8,
                  turns=1.5, diag_deg=45.0, direction=1.0, old=None, new=None):
    """Return the list of (x, y, w, h) tiles in refresh order for `pattern`.

    panel = w x h pixels; tiles are tile_w x tile_h (last row/col may be clipped).
    `center` = (cx, cy) pixel anchor (default panel center).
    `direction` = +1.0 (forward) or -1.0 (reverse the sweep).
    """
    if pattern not in PATTERNS:
        raise ValueError(f"unknown pattern {pattern!r}; choose from {list(PATTERNS)}")
    tiles = _tiles(w, h, tile_w, tile_h)
    if pattern == 'edge-aware':
        return _edge_aware(tiles, old, new)

    cx = center[0] if center else w / 2.0
    cy = center[1] if center else h / 2.0
    rmax = math.hypot(w / 2.0, h / 2.0)

    def k(t):
        x, y, tw, th = t
        dx = (x + tw / 2.0) - cx
        dy = (y + th / 2.0) - cy
        r = math.hypot(dx, dy)
        ang = math.atan2(dy, dx)
        return _key(pattern, dx, dy, r, ang, rmax, rays, turns, diag_deg) * direction

    tiles.sort(key=k)
    return tiles


if __name__ == '__main__':
    import numpy as np
    w, h, tw, th = 800, 600, 100, 100
    for p in PATTERNS:
        old = new = None
        if p == 'edge-aware':
            rng = np.random.default_rng(0)
            old = rng.integers(0, 255, (h, w), dtype=np.uint8)
            new = old.copy()
            new[100:300, 100:500] = 255  # one changed block
        tiles = ordered_tiles(p, w, h, tw, th, old=old, new=new)
        first = tiles[0] if tiles else None
        print(f'{p:18s} tiles={len(tiles):3d} first={first}')
