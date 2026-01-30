#rb_utils.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re


RHYTHM_ID_RE = re.compile(r"^R(\d{3})$")



def rhythm_id(idx1: int) -> str:
    """Canonical rhythm id from 1-based index."""
    if idx1 <= 0:
        raise ValueError("idx1 must be 1-based")
    return f"R{idx1:03d}"


def rhythm_index_from_id(rid: str) -> int:
    m = RHYTHM_ID_RE.match(rid.strip())
    if not m:
        raise ValueError(f"Invalid rhythm id: {rid!r} (expected R###)")
    idx1 = int(m.group(1))
    if idx1 <= 0:
        raise ValueError(f"Invalid rhythm id: {rid!r} (index must be >= 1)")
    return idx1



def list_tile_previews(tile_dir: Path) -> list[Path]:
    tiles = sorted(tile_dir.glob("rhythm_*.preview.svg"))
    if tiles:
        return tiles
    tiles = sorted(tile_dir.glob("rhythm_*.svg"))
    if tiles:
        return tiles
    raise FileNotFoundError(f"No rhythm_*.preview.svg or rhythm_*.svg found in {tile_dir}")



def tile_path_from_rhythm_id(tile_dir: Path, rid: str) -> Path:
    idx1 = rhythm_index_from_id(rid)
    p = tile_dir / f"rhythm_{idx1:03d}.preview.svg"
    if p.exists():
        return p
    p2 = tile_dir / f"rhythm_{idx1:03d}.svg"
    if p2.exists():
        return p2
    raise FileNotFoundError(f"Missing tile for {rid}: expected {p.name} or {p2.name} in {tile_dir}")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to read JSON: {path} ({e})") from e



def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class DeckConfig:
    n_cards: int
    seed: int
    rows: int = 3
    cols: int = 3

    @property
    def card_size(self) -> int:
        return int(self.rows) * int(self.cols)


def parse_deck_config(cfg: dict) -> DeckConfig:
    d = cfg.get("deck") or {}
    n_cards = int(d.get("n_cards", 40))
    seed = int(d.get("seed", 12345))
    rows = int(d.get("rows", 3))
    cols = int(d.get("cols", 3))
    if rows != 3 or cols != 3:
        # Spec decision: default is fixed 3x3; allow override but warn via raised error to avoid silent drift.
        raise ValueError(f"This project currently fixes student card grid to 3x3. Got rows={rows}, cols={cols}.")
    if n_cards <= 0:
        raise ValueError("n_cards must be > 0")
    if seed < 0:
        raise ValueError("seed must be >= 0")
    return DeckConfig(n_cards=n_cards, seed=seed, rows=rows, cols=cols)


def try_register_unicode_font() -> tuple[str | None, str | None]:
    """Try to register a Unicode-capable TTF for pool symbols.

    Returns (font_name, warning). If no font is registered, font_name is None and
    warning contains a short message.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None, "ReportLab TTFont not available"

    # Convention: user can drop a font file here for portable builds.
    font_path = Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"
    if not font_path.exists():
        return None, "Missing fonts/DejaVuSans.ttf; pool symbols may not render on some systems"

    font_name = "DejaVuSans"
    try:
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
        return font_name, None
    except Exception as e:
        return None, f"Failed to register {font_path.name}: {e}"
