from __future__ import annotations

from pathlib import Path
import random

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF


def list_tiles(tile_dir: Path) -> list[Path]:
    tiles = sorted(tile_dir.glob("*.preview.svg"))
    if not tiles:
        raise SystemExit(f"No *.preview.svg found in {tile_dir}")
    return tiles


def draw_grid(
    c: canvas.Canvas, x0: float, y0: float, w: float, h: float, rows: int, cols: int, lw: float = 1.0
) -> None:
    c.setLineWidth(lw)
    c.rect(x0, y0, w, h)
    for j in range(1, cols):
        x = x0 + w * j / cols
        c.line(x, y0, x, y0 + h)
    for i in range(1, rows):
        y = y0 + h * i / rows
        c.line(x0, y, x0 + w, y)


def place_svg_in_cell(
    c: canvas.Canvas,
    svg_path: Path,
    cell_x: float,
    cell_y: float,
    cell_w: float,
    cell_h: float,
    pad: float = 6 * mm,
) -> None:
    drawing = svg2rlg(str(svg_path))

    # Available box inside the cell
    aw = max(1.0, cell_w - 2 * pad)
    ah = max(1.0, cell_h - 2 * pad)

    # Scale to fit (preserve aspect ratio)
    sx = aw / drawing.width
    sy = ah / drawing.height
    s = min(1.0, sx, sy)   # never enlarge, only shrink if needed


    # IMPORTANT: renderPDF.draw doesn't respect drawing.scale reliably across versions
    # if you also adjust drawing.width/height. So we scale via transform.
    drawing.scale(s, s)

    # Center in the cell
    dw = drawing.width * s
    dh = drawing.height * s
    dx = cell_x + (cell_w - dw) / 2.0
    dy = cell_y + (cell_h - dh) / 2.0

    renderPDF.draw(drawing, c, dx, dy)


def main() -> None:
    # Settings
    tile_dir = Path("tiles_svg")
    out_pdf = Path("bingo_cards.pdf")
    rows, cols = 3, 3
    cards = 30
    seed = 42

    # Page geometry (A4 landscape)
    page_w, page_h = landscape(A4)

    # Grid area margins
    margin = 10 * mm
    grid_x0 = margin
    grid_y0 = margin
    grid_w = page_w - 2 * margin
    grid_h = page_h - 2 * margin

    tiles = list_tiles(tile_dir)
    if len(tiles) < rows * cols:
        raise SystemExit(f"Need at least {rows*cols} tiles, found {len(tiles)}.")

    rng = random.Random(seed)
    c = canvas.Canvas(str(out_pdf), pagesize=(page_w, page_h))

    cell_w = grid_w / cols
    cell_h = grid_h / rows

    for k in range(1, cards + 1):
        chosen = rng.sample(tiles, rows * cols)  # unique per card

        # Draw grid (boxes)
        draw_grid(c, grid_x0, grid_y0, grid_w, grid_h, rows, cols, lw=1.2)

        # Place tiles (row 0 at top)
        idx = 0
        for r in range(rows):
            for col in range(cols):
                cell_x = grid_x0 + col * cell_w
                cell_y = grid_y0 + (rows - 1 - r) * cell_h

                place_svg_in_cell(
                    c,
                    chosen[idx],
                    cell_x,
                    cell_y,
                    cell_w,
                    cell_h,
                    pad=7 * mm,
                )
                idx += 1

        c.showPage()

    c.save()
    print(f"Wrote {cards} cards to {out_pdf}")


if __name__ == "__main__":
    main()
