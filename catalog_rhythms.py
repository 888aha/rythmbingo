from __future__ import annotations

from pathlib import Path
import argparse

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

from rb_utils import list_tile_previews, rhythm_id, tile_path_from_rhythm_id


def draw_svg_fit(
    c: canvas.Canvas,
    svg_path: Path,
    x: float,
    y: float,
    w: float,
    h: float,
    pad: float = 3 * mm,
    max_enlarge: float = 1.4,
) -> None:
    drawing = svg2rlg(str(svg_path))

    aw = max(1.0, w - 2 * pad)
    ah = max(1.0, h - 2 * pad)

    sx = aw / drawing.width
    sy = ah / drawing.height

    # Catalog: allow modest enlarge for readability
    s = min(max_enlarge, sx, sy)

    drawing.scale(s, s)

    dw = drawing.width * s
    dh = drawing.height * s
    dx = x + (w - dw) / 2.0
    dy = y + (h - dh) / 2.0

    renderPDF.draw(drawing, c, dx, dy)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render rhythm catalog PDF from rendered tiles.")
    ap.add_argument("--tiles", default="tiles_svg", help="Tiles directory.")
    ap.add_argument("--out", default="rhythm_catalog.pdf", help="Output PDF.")
    ap.add_argument("--cols", type=int, default=3, help="Number of columns per page.")
    ap.add_argument("--rows", type=int, default=5, help="Number of rows per page.")
    ap.add_argument("--portrait", action="store_true", help="Use A4 portrait (default is landscape).")
    args = ap.parse_args()

    tiles_dir = Path(args.tiles)
    out_pdf = Path(args.out)

    # Canonical rhythm universe = rendered tiles
    tile_paths = list_tile_previews(tiles_dir)
    n = len(tile_paths)
    if n <= 0:
        raise SystemExit(f"No tiles found in {tiles_dir}.")

    # Page setup
    page = A4 if args.portrait else landscape(A4)
    page_w, page_h = page

    # Layout
    margin = 12 * mm
    cols = int(args.cols)
    rows = int(args.rows)
    if cols <= 0 or rows <= 0:
        raise SystemExit("cols and rows must be positive integers.")

    cell_gap_x = 6 * mm
    cell_gap_y = 4 * mm

    usable_w = page_w - 2 * margin
    usable_h = page_h - 2 * margin
    cell_w = (usable_w - (cols - 1) * cell_gap_x) / cols
    cell_h = (usable_h - (rows - 1) * cell_gap_y) / rows

    c = canvas.Canvas(str(out_pdf), pagesize=page)

    label_font = "Helvetica"
    label_size = 10

    per_page = rows * cols

    for i in range(1, n + 1):
        j = (i - 1) % per_page
        r = j // cols
        col = j % cols

        x = margin + col * (cell_w + cell_gap_x)
        y = page_h - margin - (r + 1) * cell_h - r * cell_gap_y

        # Outline each entry (optional but helpful)
        c.setLineWidth(0.5)
        c.rect(x, y, cell_w, cell_h)

        # Label (R###)
        rid = rhythm_id(i)
        c.setFont(label_font, label_size)
        c.drawString(x + 2 * mm, y + cell_h - 5 * mm, rid)

        # Tile
        svg = tile_path_from_rhythm_id(tiles_dir, rid)
        draw_svg_fit(c, svg, x, y, cell_w, cell_h, pad=4 * mm)

        # New page boundary
        if j == per_page - 1 and i != n:
            c.showPage()

    c.save()
    print(f"Wrote catalog: {out_pdf} ({n} rhythms)")


if __name__ == "__main__":
    main()
