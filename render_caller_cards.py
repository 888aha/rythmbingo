from __future__ import annotations

"""Render caller cards (one per rhythm) stamped with pool symbols.

Input:
  - pools.json
  - tiles_svg/ (rhythm_###.preview.svg)
Output:
  - caller_cards.pdf
"""

from pathlib import Path
import argparse

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

from rb_utils import (
    list_tile_previews,
    read_json,
    rhythm_id,
    tile_path_from_rhythm_id,
    try_register_unicode_font,
)


def draw_svg_fit(c: canvas.Canvas, svg_path: Path, x: float, y: float, w: float, h: float, pad: float = 8 * mm) -> None:
    drawing = svg2rlg(str(svg_path))
    aw = max(1.0, w - 2 * pad)
    ah = max(1.0, h - 2 * pad)
    sx = aw / drawing.width
    sy = ah / drawing.height
    s = min(sx, sy)
    drawing.scale(s, s)
    dw = drawing.width * s
    dh = drawing.height * s
    dx = x + (w - dw) / 2.0
    dy = y + (h - dh) / 2.0
    renderPDF.draw(drawing, c, dx, dy)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render caller cards PDF")
    ap.add_argument("--pools", required=True, help="Path to pools.json")
    ap.add_argument("--tiles", required=True, help="Tiles directory (tiles_svg)")
    ap.add_argument("--out", required=True, help="Output caller_cards.pdf")
    args = ap.parse_args()

    pools_doc = read_json(Path(args.pools))
    pools = pools_doc.get("pools") or []
    tiles_dir = Path(args.tiles)

    # Determine how many rhythms exist by scanning tiles (1 rhythm = 1 tile)
    tile_paths = list_tile_previews(tiles_dir)
    n_rhythms = len(tile_paths)

    # Invert pools: rhythm_id -> list of symbols (sorted by pool order, deduped)
    rid_to_syms: dict[str, list[str]] = {rhythm_id(i): [] for i in range(1, n_rhythms + 1)}

    pool_order = [str(p.get("pool_id") or "") for p in pools]
    pool_rank = {pid: i for i, pid in enumerate(pool_order) if pid}

    for p in pools:
        pid = str(p.get("pool_id") or "")
        sym = str(p.get("symbol", ""))
        if not sym:
            continue
        for rid in (p.get("callable_rhythm_ids") or []):
            if rid in rid_to_syms:
                rid_to_syms[rid].append(sym)

    # After collecting, dedupe + sort by pool order (using the pool record that introduced the symbol)
    # If symbol appears in multiple pools (shouldn’t), we keep first occurrence deterministically.
    for rid, syms in rid_to_syms.items():
        syms = list(dict.fromkeys(syms))  # dedupe preserving insertion order
        # If you ever want symbol ordering by pool_id, you’d need symbol->pool_id mapping.
        # For now, pools are iterated in pool order, so this preserves that deterministically.
        rid_to_syms[rid] = syms

    # PDF setup: A4 portrait, 1 caller card per page
    page_w, page_h = A4
    c = canvas.Canvas(str(args.out), pagesize=A4)

    font_name, warn = try_register_unicode_font()
    text_font = font_name or "Helvetica"
    if warn:
        print(f"WARNING: {warn}")

    for i in range(1, n_rhythms + 1):
        rid = rhythm_id(i)

        # Layout
        margin = 16 * mm
        tile_box_x = margin
        tile_box_y = margin + 30 * mm
        tile_box_w = page_w - 2 * margin
        tile_box_h = page_h - 2 * margin - 40 * mm

        # Tile
        svg = tile_path_from_rhythm_id(tiles_dir, rid)
        draw_svg_fit(c, svg, tile_box_x, tile_box_y, tile_box_w, tile_box_h, pad=10 * mm)

        # Footer: rhythm id + pool symbols
        c.setFont("Helvetica", 14)
        c.drawString(margin, margin + 18 * mm, rid)

        syms = rid_to_syms.get(rid) or []
        syms_txt = " ".join(syms)
        c.setFont(text_font, 18)
        c.drawRightString(page_w - margin, margin + 16 * mm, syms_txt)

        # Optional: tiny pool order hint (not teacher-facing critical)
        c.setFont("Helvetica", 8)
        c.drawString(margin, margin + 6 * mm, "caller pools: " + " ".join(str(x) for x in pool_order if x))

        c.showPage()

    c.save()
    print(f"Wrote caller cards: {args.out} ({n_rhythms} pages)")


if __name__ == "__main__":
    main()
