from __future__ import annotations

from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF


def load_bank_lines(bank_path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in bank_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def tile_path(tile_dir: Path, idx1: int) -> Path:
    # idx1 is 1-based
    p = tile_dir / f"rhythm_{idx1:03d}.preview.svg"
    if not p.exists():
        # fallback if preview isn't used
        p2 = tile_dir / f"rhythm_{idx1:03d}.svg"
        if p2.exists():
            return p2
        raise FileNotFoundError(f"Missing tile for #{idx1:03d}: {p}")
    return p


def draw_svg_fit(
    c: canvas.Canvas,
    svg_path: Path,
    x: float,
    y: float,
    w: float,
    h: float,
    pad: float = 3 * mm,
) -> None:
    drawing = svg2rlg(str(svg_path))
    aw = max(1.0, w - 2 * pad)
    ah = max(1.0, h - 2 * pad)

    sx = aw / drawing.width
    sy = ah / drawing.height

    # Catalog: allow modest enlarge for readability, but don’t go crazy
    s = min(1.4, sx, sy)

    drawing.scale(s, s)

    dw = drawing.width * s
    dh = drawing.height * s
    dx = x + (w - dw) / 2.0
    dy = y + (h - dh) / 2.0

    renderPDF.draw(drawing, c, dx, dy)


def main() -> None:
    bank_path = Path("rhytms.txt")          # match your current filename
    tile_dir = Path("tiles_svg")
    out_pdf = Path("rhythm_catalog.pdf")

    # Page setup
    page = A4                 # portrait
    # page = landscape(A4)    # uncomment for A4 landscape catalog
    page_w, page_h = page

    # Layout
    margin = 12 * mm
    cols = 2
    rows = 10                  # 20 items/page
    cell_gap_x = 6 * mm
    cell_gap_y = 4 * mm

    # Cell sizes
    usable_w = page_w - 2 * margin
    usable_h = page_h - 2 * margin
    cell_w = (usable_w - (cols - 1) * cell_gap_x) / cols
    cell_h = (usable_h - (rows - 1) * cell_gap_y) / rows

    lines = load_bank_lines(bank_path)
    n = len(lines)
    if n == 0:
        raise SystemExit(f"No rhythms found in {bank_path}")

    c = canvas.Canvas(str(out_pdf), pagesize=page)

    c.setFont("Helvetica", 9)

    for i in range(1, n + 1):
        # 0-based index within page
        j = (i - 1) % (rows * cols)
        r = j // cols
        col = j % cols

        x = margin + col * (cell_w + cell_gap_x)
        y = page_h - margin - (r + 1) * cell_h - r * cell_gap_y

        # Outline each entry (optional but helpful)
        c.setLineWidth(0.5)
        c.rect(x, y, cell_w, cell_h)

        # Label
        c.drawString(x + 2 * mm, y + cell_h - 4 * mm, f"{i:03d}")

        # Draw the tile
        svg = tile_path(tile_dir, i)
        draw_svg_fit(c, svg, x, y, cell_w, cell_h, pad=4 * mm)

        # New page
        if j == rows * cols - 1 and i != n:
            c.showPage()
            c.setFont("Helvetica", 9)

    c.save()
    print(f"Wrote catalog: {out_pdf} ({n} rhythms)")


if __name__ == "__main__":
    main()
