from __future__ import annotations

"""Compute deck diagnostics (Deck QC) for each recommended k.

Inputs:
  - config_pools.json
  - out/deck_order.json
  - out/pools.json (optional but used for callable set + pool labels)
Outputs:
  - out/deck_qc.json
  - out/deck_qc.csv

v0.2 additions:
  - Per pool, compute the two fairness booleans (A/B) and their counts.
  - Surface diagnostic sizes (core/final/added) when present in pools.json.
"""

from pathlib import Path
import argparse
import csv
import math

from rb_utils import read_json, write_json


def _bingo_lines_3x3(rids: list[str]) -> list[list[str]]:
    if len(rids) != 9:
        raise ValueError(f"Expected 9 rhythm IDs for 3x3, got {len(rids)}")
    idx_lines: list[list[int]] = [
        # rows
        [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],
        # cols
        [0, 3, 6],
        [1, 4, 7],
        [2, 5, 8],
        # diagonals
        [0, 4, 8],
        [2, 4, 6],
    ]
    return [[rids[i] for i in idxs] for idxs in idx_lines]


def _bingo_guarantee_failures(cards: list[dict], callable_set: set[str]) -> int:
    failures = 0
    for card in cards:
        rids = list(card.get("rhythm_ids") or [])
        ok = any(all(x in callable_set for x in line) for line in _bingo_lines_3x3(rids))
        if not ok:
            failures += 1
    return failures


def _full_card_candidates(cards: list[dict], callable_set: set[str]) -> int:
    return sum(set((c.get("rhythm_ids") or [])).issubset(callable_set) for c in cards)


def _quantiles(vals: list[int]) -> dict[str, float]:
    if not vals:
        return {"min": math.nan, "p10": math.nan, "median": math.nan, "max": math.nan}
    v = sorted(vals)

    def pick(p: float) -> float:
        idx = int(round(p * (len(v) - 1)))
        idx = max(0, min(len(v) - 1, idx))
        return float(v[idx])

    return {
        "min": float(v[0]),
        "p10": pick(0.10),
        "median": pick(0.50),
        "max": float(v[-1]),
    }


def _overlap_hist(card_sets: list[set[str]]) -> tuple[dict[str, int], int, float, int]:
    hist: dict[str, int] = {}
    n = len(card_sets)
    if n < 2:
        return hist, 0, 0.0, 0
    total = 0
    count = 0
    max_ov = 0
    for i in range(n):
        si = card_sets[i]
        for j in range(i + 1, n):
            ov = len(si & card_sets[j])
            max_ov = max(max_ov, ov)
            hist[str(ov)] = hist.get(str(ov), 0) + 1
            total += ov
            count += 1
    mean = (total / count) if count else 0.0
    return hist, max_ov, float(mean), count


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute Deck QC diagnostics")
    ap.add_argument("--config", required=True, help="Path to config_pools.json")
    ap.add_argument("--deck", required=True, help="Path to out/deck_order.json")
    ap.add_argument("--pools", required=False, help="Path to out/pools.json")
    ap.add_argument("--out-json", required=True, help="Output deck_qc.json")
    ap.add_argument("--out-csv", required=True, help="Output deck_qc.csv")
    args = ap.parse_args()

    cfg = read_json(Path(args.config))
    deck_doc = read_json(Path(args.deck))
    deck = deck_doc.get("deck") or {}
    cards = deck_doc.get("cards") or []
    if not cards:
        raise SystemExit(f"No cards in {args.deck}")

    n_cards = int(deck.get("n_cards", len(cards)))
    card_size = int(deck.get("card_size", 9))

    intervals = ((cfg.get("pools") or {}).get("intervals")) or []

    pools_doc = read_json(Path(args.pools)) if args.pools else None
    pools_by_id = {p.get("pool_id"): p for p in ((pools_doc or {}).get("pools") or []) if p.get("pool_id")}

    # Precompute full-deck duplicates (exact set match)
    seen: set[frozenset[str]] = set()
    duplicate_pairs_full = 0
    for c in cards:
        key = frozenset(c.get("rhythm_ids") or [])
        if key in seen:
            duplicate_pairs_full += 1
        seen.add(key)

    rows_out: list[dict] = []
    for rec in intervals:
        pool_id = str(rec["pool_id"])
        symbol = str(rec["symbol"])
        cmin = int(rec["children_min"])
        cmax = int(rec["children_max"])
        k = int(rec["k"])
        k_eff = min(k, n_cards)

        # Use pools.json's effective if present
        p = pools_by_id.get(pool_id)
        if p:
            k_eff = int(p.get("k_effective", k_eff))
            symbol = str(p.get("symbol", symbol))

        sub_cards = cards[:k_eff]
        sets = [set(c.get("rhythm_ids") or []) for c in sub_cards]
        union = set().union(*sets) if sets else set()

        # Frequency over union
        freq: dict[str, int] = {r: 0 for r in union}
        for s in sets:
            for r in s:
                freq[r] = freq.get(r, 0) + 1

        q = _quantiles(list(freq.values()))

        # Callable pool + fairness checks, from pools.json if available
        call_pool_size = math.nan
        min_occ_used = math.nan
        bingo_ok = math.nan
        full_ok = math.nan
        cards_with_no_bingo_line = math.nan
        full_card_candidates = math.nan
        core_callable_size = math.nan
        final_callable_size = math.nan
        added_for_bingo_size = math.nan
        added_for_full_card_size = math.nan

        if p:
            callable_ids = list(p.get("callable_rhythm_ids") or [])
            call_pool_size = int(len(callable_ids))
            min_occ_used = int(p.get("min_occ_used", math.nan))

            callable_set = set(callable_ids)
            failures = _bingo_guarantee_failures(sub_cards, callable_set)
            candidates = _full_card_candidates(sub_cards, callable_set)
            cards_with_no_bingo_line = int(failures)
            full_card_candidates = int(candidates)
            bingo_ok = (failures == 0)
            full_ok = (candidates >= 1)

            # Surface diagnostic sizes if present (computed in compute_pools.py v0.2)
            if "core_callable_size" in p:
                core_callable_size = int(p.get("core_callable_size"))
            if "final_callable_size" in p:
                final_callable_size = int(p.get("final_callable_size"))
            if "added_for_bingo_size" in p:
                added_for_bingo_size = int(p.get("added_for_bingo_size"))
            if "added_for_full_card_size" in p:
                added_for_full_card_size = int(p.get("added_for_full_card_size"))

        # Duplicates among 1..k (pairwise identical rhythm sets)
        dup_pairs = 0
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                if sets[i] == sets[j]:
                    dup_pairs += 1

        hist, max_ov, mean_ov, pair_count = _overlap_hist(sets)

        rows_out.append(
            {
                "k": k_eff,
                "children_interval": f"{cmin}–{cmax}",
                "symbol": symbol,
                "union_size": int(len(union)),
                "freq_min": q["min"],
                "freq_p10": q["p10"],
                "freq_median": q["median"],
                "freq_max": q["max"],
                "call_pool_size": call_pool_size,
                "min_occ_used": min_occ_used,
                "bingo_guarantee_ok": bingo_ok,
                "full_card_possible_ok": full_ok,
                "cards_with_no_bingo_line": cards_with_no_bingo_line,
                "full_card_candidates": full_card_candidates,
                "core_callable_size": core_callable_size,
                "final_callable_size": final_callable_size,
                "added_for_bingo_size": added_for_bingo_size,
                "added_for_full_card_size": added_for_full_card_size,
                "duplicate_pairs": int(dup_pairs),
                "max_overlap": int(max_ov),
                "mean_overlap": float(mean_ov),
                "overlap_hist": hist,
                "pair_count": int(pair_count),
            }
        )

    out = {
        "version": "v0.2",
        "deck": {
            "n_cards": n_cards,
            "card_size": card_size,
            "rows": int(deck.get("rows", 3)),
            "cols": int(deck.get("cols", 3)),
            "seed": int(deck.get("seed", 0)),
        },
        "duplicate_pairs_full_deck": int(duplicate_pairs_full),
        "rows": rows_out,
    }
    write_json(Path(args.out_json), out)

    csv_cols = [
        "k",
        "children_interval",
        "symbol",
        "union_size",
        "call_pool_size",
        "min_occ_used",
        "bingo_guarantee_ok",
        "full_card_possible_ok",
        "cards_with_no_bingo_line",
        "full_card_candidates",
        "core_callable_size",
        "final_callable_size",
        "added_for_bingo_size",
        "added_for_full_card_size",
        "duplicate_pairs",
        "max_overlap",
        "mean_overlap",
    ]

    with Path(args.out_csv).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols)
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r.get(k) for k in csv_cols})

    print(f"Wrote deck QC JSON: {args.out_json}")
    print(f"Wrote deck QC CSV : {args.out_csv}")


if __name__ == "__main__":
    main()
