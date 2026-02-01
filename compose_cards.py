# compose_cards.py
from __future__ import annotations

from pathlib import Path
import argparse
import random

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

from rb_utils import (
    read_json,
    tile_path_from_rhythm_id,
    try_register_unicode_font,
    pool_symbols_for_card_index,
)


def list_tiles(tile_dir: Path) -> list[Path]:
    tiles = sorted(tile_dir.glob("rhythm_*.preview.svg"))
    if not tiles:
        tiles = sorted(tile_dir.glob("rhythm_*.svg"))
    if not tiles:
        raise SystemExit(f"No rhythm_*.svg / rhythm_*.preview.svg found in {tile_dir}")
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
    s = min(1.0, sx, sy)  # never enlarge, only shrink if needed

    # IMPORTANT: renderPDF.draw doesn't respect drawing.scale reliably across versions
    # if you also adjust drawing.width/height. So we scale via transform.
    drawing.scale(s, s)

    # Center in the cell
    dw = drawing.width * s
    dh = drawing.height * s
    dx = cell_x + (cell_w - dw) / 2.0
    dy = cell_y + (cell_h - dh) / 2.0

    renderPDF.draw(drawing, c, dx, dy)


def _draw_card_header(
    c: canvas.Canvas,
    *,
    page_w: float,
    page_h: float,
    margin: float,
    card_id: str,
    card_index_1based: int,
    pools: list[dict],
    sym_font: str,
) -> None:
    """
    Header is intentionally outside the grid area (in the top margin band),
    so it doesn't compete visually with the rhythms.
    """
    y_header = page_h - margin + 2 * mm

    # Left: Card ID
    c.setFont("Helvetica", 12)
    c.drawString(margin, y_header, card_id)

    # Right: pool symbols (call-sheet semantics via rb_utils.pool_symbols_for_card_index)
    if pools:
        syms = pool_symbols_for_card_index(card_index_1based, pools)
        if syms:
            c.setFont(sym_font, 14)
            c.drawRightString(page_w - margin, y_header, " ".join(syms))


def _render_from_deck_json(
    deck_path: Path,
    *,
    tiles_dir: Path,
    out_pdf: Path,
    pools: list[dict],
    sym_font: str,
) -> None:
    doc = read_json(deck_path)
    deck = doc.get("deck") or {}
    cards = doc.get("cards") or []

    rows = int(deck.get("rows", 3))
    cols = int(deck.get("cols", 3))
    if rows != 3 or cols != 3:
        raise SystemExit(f"compose_cards.py currently supports fixed 3x3 only. Got rows={rows}, cols={cols}.")

    if not cards:
        raise SystemExit(f"No cards in {deck_path}")

    # Page geometry (A4 landscape)
    page_w, page_h = landscape(A4)

    margin = 10 * mm
    grid_x0 = margin
    grid_y0 = margin
    grid_w = page_w - 2 * margin
    grid_h = page_h - 2 * margin

    c = canvas.Canvas(str(out_pdf), pagesize=(page_w, page_h))
    cell_w = grid_w / cols
    cell_h = grid_h / rows

    for i0, card in enumerate(cards):
        i1 = i0 + 1  # 1-based card index (matches call-sheet semantics)

        rids = card.get("rhythm_ids") or []
        if len(rids) != rows * cols:
            raise SystemExit(f"Card {card.get('card_id')} has {len(rids)} rhythms; expected {rows*cols}.")

        card_id = str(card.get("card_id") or f"C{i1:03d}")
        _draw_card_header(
            c,
            page_w=page_w,
            page_h=page_h,
            margin=margin,
            card_id=card_id,
            card_index_1based=i1,
            pools=pools,
            sym_font=sym_font,
        )

        draw_grid(c, grid_x0, grid_y0, grid_w, grid_h, rows, cols, lw=1.2)

        idx = 0
        for r in range(rows):
            for col in range(cols):
                cell_x = grid_x0 + col * cell_w
                cell_y = grid_y0 + (rows - 1 - r) * cell_h

                svg_path = tile_path_from_rhythm_id(tiles_dir, rids[idx])
                place_svg_in_cell(c, svg_path, cell_x, cell_y, cell_w, cell_h, pad=7 * mm)
                idx += 1

        c.showPage()

    c.save()


def _render_random(cards: int, *, tiles_dir: Path, out_pdf: Path, seed: int) -> None:
    """
    Legacy mode: random cards. We still print Card IDs, but we do NOT print pool symbols,
    because pool applicability is defined over the ordered deck (call-sheet semantics).
    """
    rows, cols = 3, 3

    page_w, page_h = landscape(A4)

    margin = 10 * mm
    grid_x0 = margin
    grid_y0 = margin
    grid_w = page_w - 2 * margin
    grid_h = page_h - 2 * margin

    tiles = list_tiles(tiles_dir)
    if len(tiles) < rows * cols:
        raise SystemExit(f"Need at least {rows*cols} tiles, found {len(tiles)}.")

    rng = random.Random(seed)
    c = canvas.Canvas(str(out_pdf), pagesize=(page_w, page_h))

    cell_w = grid_w / cols
    cell_h = grid_h / rows

    for i1 in range(1, cards + 1):
        chosen = rng.sample(tiles, rows * cols)  # unique per card

        # Header (Card ID only)
        y_header = page_h - margin + 2 * mm
        c.setFont("Helvetica", 12)
        c.drawString(margin, y_header, f"C{i1:03d}")

        draw_grid(c, grid_x0, grid_y0, grid_w, grid_h, rows, cols, lw=1.2)

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


def main() -> None:
    ap = argparse.ArgumentParser(description="Render student bingo cards (fixed 3x3).")
    ap.add_argument("--deck", type=str, default=None, help="Path to deck_order.json (preferred).")
    ap.add_argument("--tiles", type=str, default="tiles_svg", help="Tiles directory.")
    ap.add_argument("--out", type=str, default="bingo_cards.pdf", help="Output PDF.")
    ap.add_argument("--cards", type=int, default=30, help="(Legacy) number of random cards if --deck is not used.")
    ap.add_argument("--seed", type=int, default=42, help="(Legacy) seed for random cards if --deck is not used.")
    ap.add_argument(
        "--pools",
        type=str,
        default=None,
        help="Optional pools.json; if provided, pool symbols are printed on each student card.",
    )
    args = ap.parse_args()

    pools: list[dict] = []
    if args.pools:
        pools = (read_json(Path(args.pools)).get("pools") or [])

    font_name, _warn = try_register_unicode_font()
    sym_font = font_name or "Helvetica"

    tiles_dir = Path(args.tiles)
    out_pdf = Path(args.out)

    if args.deck:
        _render_from_deck_json(
            Path(args.deck),
            tiles_dir=tiles_dir,
            out_pdf=out_pdf,
            pools=pools,
            sym_font=sym_font,
        )
    else:
        _render_random(args.cards, tiles_dir=tiles_dir, out_pdf=out_pdf, seed=args.seed)


if __name__ == "__main__":
    main()
