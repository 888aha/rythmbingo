from __future__ import annotations

"""Compute callable rhythm pools and a text call sheet.

Inputs:
  - out/config_pools.json
  - out/deck_order.json
Outputs:
  - out/pools.json
  - out/call_sheet.txt
"""

from pathlib import Path
import argparse

from rb_utils import read_json, write_json


def _freq_over_cards(cards: list[dict], k: int) -> dict[str, int]:
    freq: dict[str, int] = {}
    for c in cards[:k]:
        for rid in c.get("rhythm_ids") or []:
            freq[rid] = freq.get(rid, 0) + 1
    return freq


def _bingo_lines_3x3(rids: list[str]) -> list[tuple[int, int, list[str]]]:
    """Return bingo lines with deterministic tie-break metadata.

    Returns a list of (kind_rank, pos_rank, line_rhythm_ids).

    kind_rank order:
      0 = row (top -> bottom)
      1 = col (left -> right)
      2 = diag (main, anti)
    """
    if len(rids) != 9:
        raise ValueError(f"Expected 9 rhythm IDs for 3x3, got {len(rids)}")

    # Indices into the flattened 3x3 grid.
    idx_lines: list[tuple[int, int, list[int]]] = [
        # rows
        (0, 0, [0, 1, 2]),
        (0, 1, [3, 4, 5]),
        (0, 2, [6, 7, 8]),
        # cols
        (1, 0, [0, 3, 6]),
        (1, 1, [1, 4, 7]),
        (1, 2, [2, 5, 8]),
        # diagonals
        (2, 0, [0, 4, 8]),  # main
        (2, 1, [2, 4, 6]),  # anti
    ]
    return [(kind, pos, [rids[i] for i in idxs]) for (kind, pos, idxs) in idx_lines]


def _enforce_bingo_guarantee(cards: list[dict], callable_set: set[str]) -> None:
    """Enforce Acceptance Check A by adding the minimal missing line per card."""
    for card in cards:
        rids = list(card.get("rhythm_ids") or [])
        if len(rids) != 9:
            raise SystemExit(f"Card {card.get('card_id')} has {len(rids)} rhythms; expected 9.")

        best_missing: set[str] | None = None
        best_key: tuple[int, int, int, tuple[str, ...]] | None = None

        for kind_rank, pos_rank, line in _bingo_lines_3x3(rids):
            missing = {x for x in line if x not in callable_set}
            # Deterministic tie-break (spec v0.2):
            #  1) minimal |missing|
            #  2) rows before cols before diagonals
            #  3) top->bottom / left->right / main->anti
            #  4) lexicographic order of rhythm IDs
            key = (len(missing), kind_rank, pos_rank, tuple(sorted(line)))
            if best_key is None or key < best_key:
                best_key = key
                best_missing = missing

        if best_missing:
            callable_set.update(best_missing)


def _bingo_guarantee_failures(cards: list[dict], callable_set: set[str]) -> int:
    """Return count of cards with zero fully-callable bingo lines."""
    failures = 0
    for card in cards:
        rids = list(card.get("rhythm_ids") or [])
        ok = False
        for _kind, _pos, line in _bingo_lines_3x3(rids):
            if all(x in callable_set for x in line):
                ok = True
                break
        if not ok:
            failures += 1
    return failures


def _full_card_candidates(cards: list[dict], callable_set: set[str]) -> int:
    """Return number of cards whose full 3x3 set is callable."""
    n = 0
    for card in cards:
        rids = set(card.get("rhythm_ids") or [])
        if rids and rids.issubset(callable_set):
            n += 1
    return n


def _enforce_full_card_guarantee(cards: list[dict], callable_set: set[str]) -> None:
    """Enforce Acceptance Check B by adding the missing rhythms for the closest card."""
    if _full_card_candidates(cards, callable_set) >= 1:
        return

    best_missing: set[str] | None = None
    best_key: tuple[int, str] | None = None

    for card in cards:
        card_id = str(card.get("card_id") or "")
        rids = set(card.get("rhythm_ids") or [])
        missing = {x for x in rids if x not in callable_set}
        key = (len(missing), card_id)
        if best_key is None or key < best_key:
            best_key = key
            best_missing = missing

    if best_missing:
        callable_set.update(best_missing)


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute attendance pools + call sheet")
    ap.add_argument("--config", required=True, help="Path to out/config_pools.json")
    ap.add_argument("--deck", required=True, help="Path to out/deck_order.json")
    ap.add_argument("--out", required=True, help="Output pools.json")
    ap.add_argument("--call-sheet", required=True, help="Output call_sheet.txt")
    args = ap.parse_args()

    cfg = read_json(Path(args.config))
    deck_doc = read_json(Path(args.deck))
    deck = deck_doc.get("deck") or {}
    cards = deck_doc.get("cards") or []
    if not cards:
        raise SystemExit(f"No cards in {args.deck}")

    n_cards = int(deck.get("n_cards", len(cards)))
    intervals = ((cfg.get("pools") or {}).get("intervals")) or []
    call_cfg = ((cfg.get("pools") or {}).get("call_pool")) or {}
    min_occ_default = int(call_cfg.get("min_occ", 2))
    min_pool_size = int(call_cfg.get("min_pool_size", 20))

    pools_out = []
    for rec in intervals:
        pool_id = str(rec["pool_id"])
        symbol = str(rec["symbol"])
        cmin = int(rec["children_min"])
        cmax = int(rec["children_max"])
        k = int(rec["k"])
        k_eff = min(k, n_cards)

        # Step 1: determine card subset (Cards(p) = first k cards)
        sub_cards = cards[:k_eff]

        # Step 2: initial callable core based on frequency threshold
        freq = _freq_over_cards(cards, k_eff)
        core = sorted([rid for rid, f in freq.items() if f >= min_occ_default])
        min_occ_used = min_occ_default

        # Keep the old "min_pool_size" guardrail, but correctness is now defined
        # by the fairness guarantees (A/B), not by this heuristic.
        if len(core) < min_pool_size:
            core = sorted([rid for rid, f in freq.items() if f >= 1])
            min_occ_used = 1

        callable_set = set(core)

        # Step 3: enforce bingo guarantee (A) by construction
        _enforce_bingo_guarantee(sub_cards, callable_set)

        # Step 4: enforce full-card guarantee (B) by construction
        _enforce_full_card_guarantee(sub_cards, callable_set)

        # Step 5: final callable set (single list)
        pool = sorted(callable_set)

        # Sanity guardrails (D)
        if len(pool) < 1:
            raise SystemExit(f"Pool {symbol} produced empty callable set (unexpected).")

        all_on_cards: set[str] = set()
        for c in sub_cards:
            all_on_cards.update(c.get("rhythm_ids") or [])
        ghosts = set(pool) - all_on_cards
        if ghosts:
            raise SystemExit(f"Pool {symbol} has ghost rhythms not on cards 1..{k_eff}: {sorted(ghosts)}")

        # Validate guarantees (hard fail)
        bingo_failures = _bingo_guarantee_failures(sub_cards, set(pool))
        full_candidates = _full_card_candidates(sub_cards, set(pool))
        bingo_ok = bingo_failures == 0
        full_ok = full_candidates >= 1
        if not bingo_ok or not full_ok:
            raise SystemExit(
                f"Pool {symbol} failed fairness guarantees: "
                f"bingo_ok={bingo_ok} (failures={bingo_failures}), "
                f"full_ok={full_ok} (candidates={full_candidates})."
            )

        pools_out.append(
            {
                "pool_id": pool_id,
                "symbol": symbol,
                "children_min": cmin,
                "children_max": cmax,
                "k": k,
                "k_effective": k_eff,
                "min_occ_used": min_occ_used,
                "callable_rhythm_ids": pool,
                "guarantees": {
                    "bingo_all_cards": True,
                    "full_card_exists": True,
                },
            }
        )

    out = {
        "version": "v0.2",
        "deck": {
            "n_cards": n_cards,
            "rows": int(deck.get("rows", 3)),
            "cols": int(deck.get("cols", 3)),
            "seed": int(deck.get("seed", 0)),
        },
        "config": {
            "min_occ_default": min_occ_default,
            "min_pool_size": min_pool_size,
        },
        "pools": pools_out,
    }

    write_json(Path(args.out), out)

    # Call sheet (text fallback, teacher-facing)
    lines = []
    lines.append("Rhythm Bingo — Call Sheet (text fallback)\n")
    lines.append("Recommendation: for today’s attendance, use student cards 1–k and the caller symbol for that interval.\n")
    lines.append("All listed rhythms guarantee bingo for every marked card, and at least one full-card is possible.\n")
    lines.append("")
    for p in pools_out:
        sym = p["symbol"]
        cmin = p["children_min"]
        cmax = p["children_max"]
        k_eff = p["k_effective"]
        ids = p["callable_rhythm_ids"]
        lines.append(f"{sym}  ({cmin}–{cmax} children)  Use student cards 1–{k_eff}")
        if ids:
            lines.append(" ".join(ids))
        else:
            lines.append("(no callable rhythms — check deck_qc)")
        lines.append("")

    Path(args.call_sheet).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote pools: {args.out}")
    print(f"Wrote call sheet: {args.call_sheet}")


if __name__ == "__main__":
    main()
