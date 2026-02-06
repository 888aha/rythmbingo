from __future__ import annotations

"""Generate a deterministic *raw* student deck (JSON), fixed 3x3.

This script creates the card definitions (rhythm IDs per card) but does not
perform the greedy ordering.

Canonical rhythm universe comes from rendered tiles in tiles_svg/:
  R001 <-> tiles_svg/rhythm_001(.preview).svg

Output: deck_raw.json
"""

from pathlib import Path
import argparse
import random

from rb_utils import (
    parse_deck_config,
    read_json,
    write_json,
    rhythm_id,
    list_tile_previews,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate deterministic raw deck (fixed 3x3).")
    ap.add_argument("--config", required=True, help="Path to config_pools.json")
    ap.add_argument("--bank", default="rhythms.txt", help="(ignored) rhythm bank file; deck is derived from tiles_svg/")
    ap.add_argument("--tiles", default="tiles_svg", help="Tiles directory (tiles_svg).")
    ap.add_argument("--out", required=True, help="Output deck_raw.json")
    args = ap.parse_args()

    cfg = read_json(Path(args.config))
    deck_cfg = parse_deck_config(cfg)

    tiles_dir = Path(args.tiles)

    # Canonical rhythm universe = whatever tiles exist
    tile_paths = list_tile_previews(tiles_dir)
    n_rhythms = len(tile_paths)
    if n_rhythms < deck_cfg.card_size:
        raise SystemExit(
            f"Need at least {deck_cfg.card_size} rhythms (tiles), found {n_rhythms} in {tiles_dir}."
        )

    all_rids = [rhythm_id(i) for i in range(1, n_rhythms + 1)]
    rng = random.Random(deck_cfg.seed)

    # Enforce: no duplicates within a card (sample does this)
    # Enforce: no two cards have identical rhythm sets (as per spec)
    seen_sets: set[frozenset[str]] = set()
    cards: list[dict] = []

    max_attempts_per_card = 2000
    for ci in range(1, deck_cfg.n_cards + 1):
        for attempt in range(1, max_attempts_per_card + 1):
            chosen = rng.sample(all_rids, deck_cfg.card_size)
            key = frozenset(chosen)
            if key in seen_sets:
                continue
            seen_sets.add(key)
            cards.append({"card_id": f"C{ci:03d}", "rhythm_ids": chosen})
            break
        else:
            raise SystemExit(
                f"Failed to generate a unique card after {max_attempts_per_card} attempts. "
                f"Try reducing n_cards or increasing the number of rendered tiles."
            )

    out = {
        "version": "v0.1",
        "deck": {
            "n_cards": deck_cfg.n_cards,
            "seed": deck_cfg.seed,
            "rows": deck_cfg.rows,
            "cols": deck_cfg.cols,
            "card_size": deck_cfg.card_size,
        },
        "rhythm_universe": {
            "tiles_dir": str(tiles_dir.as_posix()),
            "count": n_rhythms,
            "id_scheme": "R### = 1-based tile index (rhythm_###.svg / rhythm_###.preview.svg)",
        },
        "cards": cards,
    }

    write_json(Path(args.out), out)
    print(f"Wrote raw deck: {args.out} ({deck_cfg.n_cards} cards, {deck_cfg.card_size} tiles each)")


if __name__ == "__main__":
    main()
