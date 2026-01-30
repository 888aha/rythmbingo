from __future__ import annotations

"""Compute deck diagnostics (Deck QC) for each recommended k.

Inputs:
  - out/config_pools.json
  - out/deck_order.json
  - out/pools.json (optional but used for symbols/interval labels)
Outputs:
  - out/deck_qc.json
  - out/deck_qc.csv
"""

from pathlib import Path
import argparse
import csv
import math

from rb_utils import read_json, write_json


def _quantiles(vals: list[int]) -> dict[str, float]:
    if not vals:
        return {"min": math.nan, "p10": math.nan, "median": math.nan, "max": math.nan}
    v = sorted(vals)
    def pick(p: float) -> float:
        # nearest-rank on 0..1
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
    # histogram keys as strings for JSON stability
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
    ap.add_argument("--config", required=True, help="Path to out/config_pools.json")
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

    # Optional symbol/interval source of truth: pools.json (after clamp)
    pools_doc = read_json(Path(args.pools)) if args.pools else None
    pools_by_id = {p["pool_id"]: p for p in ((pools_doc or {}).get("pools") or [])}

    # Precompute full-deck duplicates (exact set match)
    seen: set[frozenset[str]] = set()
    duplicate_pairs_full = 0
    for i in range(len(cards)):
        si = frozenset(cards[i].get("rhythm_ids") or [])
        if si in seen:
            duplicate_pairs_full += 1
        seen.add(si)

    rows_out = []
    for rec in intervals:
        pool_id = str(rec["pool_id"])
        symbol = str(rec["symbol"])
        cmin = int(rec["children_min"])
        cmax = int(rec["children_max"])
        k = int(rec["k"])
        k_eff = min(k, n_cards)

        # Use pools.json's effective if present
        if pool_id in pools_by_id:
            p = pools_by_id[pool_id]
            k_eff = int(p.get("k_effective", k_eff))
            symbol = str(p.get("symbol", symbol))

        sub_cards = cards[:k_eff]
        sets = [set(c.get("rhythm_ids") or []) for c in sub_cards]
        union = set().union(*sets) if sets else set()

        # Frequency over union
        freq = {r: 0 for r in union}
        for s in sets:
            for r in s:
                freq[r] = freq.get(r, 0) + 1

        freq_vals = list(freq.values())
        q = _quantiles(freq_vals)

        # Callable pool size + min_occ used from pools.json if available
        call_pool_size = math.nan
        min_occ_used = math.nan
        if pool_id in pools_by_id:
            call_pool_size = int(len(pools_by_id[pool_id].get("callable_rhythm_ids") or []))
            min_occ_used = int(pools_by_id[pool_id].get("min_occ_used", math.nan))

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
                "duplicate_pairs": int(dup_pairs),
                "max_overlap": int(max_ov),
                "mean_overlap": float(mean_ov),
                "overlap_hist": hist,
                "pair_count": int(pair_count),
            }
        )

    out = {
        "version": "v0.1",
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

    # CSV (compact)
    csv_cols = [
        "k",
        "children_interval",
        "symbol",
        "union_size",
        "call_pool_size",
        "min_occ_used",
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
