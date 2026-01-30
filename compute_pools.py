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

        freq = _freq_over_cards(cards, k_eff)

        # Primary callable set
        pool2 = sorted([rid for rid, f in freq.items() if f >= min_occ_default])
        min_occ_used = min_occ_default
        pool = pool2

        if len(pool) < min_pool_size:
            pool = sorted([rid for rid, f in freq.items() if f >= 1])
            min_occ_used = 1

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
            }
        )

    out = {
        "version": "v0.1",
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

    # Call sheet (text fallback)
    lines = []
    lines.append("Rhythm Bingo — Call Sheet (text fallback)\n")
    lines.append("Recommendation: for today’s attendance, use student cards 1–k and the caller symbol for that interval.\n")
    lines.append("")
    for p in pools_out:
        sym = p["symbol"]
        cmin = p["children_min"]
        cmax = p["children_max"]
        k = p["k_effective"]
        ids = p["callable_rhythm_ids"]
        lines.append(f"{sym}  ({cmin}–{cmax} children)  Use student cards 1–{k}  (min_occ_used={p['min_occ_used']})")
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
