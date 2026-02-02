from __future__ import annotations

"""Compute deterministic greedy ordering of a raw deck, 
    and renumber cards in ordered output.

Input : deck_raw.json
Output: deck_order.json (same cards, reordered)
"""

from pathlib import Path
import argparse
import random

from rb_utils import read_json, write_json


def score_candidate(
    C: frozenset[str],
    *,
    selected: list[frozenset[str]],
    union: set[str],
    freq: dict[str, int],
    w_new: int = 1000,
    w_shared: int = 1,
    w_maxover: int = 50,
) -> tuple[int, int, int]:
    """Return (score, new_count, max_overlap) with fixed, stable semantics."""
    new_count = len(C - union)
    if selected:
        max_overlap = max(len(C & s) for s in selected)
    else:
        max_overlap = 0

    shared_gain = sum(freq.get(r, 0) for r in (C & union))
    score = w_new * new_count + w_shared * shared_gain - w_maxover * max_overlap
    return score, new_count, max_overlap


def main() -> None:
    ap = argparse.ArgumentParser(description="Greedy ordering for deck_raw.json")
    ap.add_argument("--in", dest="inp", required=True, help="Input deck_raw.json")
    ap.add_argument("--out", required=True, help="Output deck_order.json")
    ap.add_argument("--seed", type=int, default=None, help="Optional tie-break RNG seed override")
    args = ap.parse_args()

    doc = read_json(Path(args.inp))
    deck = doc.get("deck") or {}
    cards_in = doc.get("cards") or []
    if not cards_in:
        raise SystemExit(f"No cards in {args.inp}")

    seed = int(args.seed) if args.seed is not None else int(deck.get("seed", 0))
    rng = random.Random(seed)

    # Normalize: keep original order index for deterministic tie-break
    items = []
    for ix, c in enumerate(cards_in):
        rids = c.get("rhythm_ids") or []
        items.append(
            {
                "orig_index": ix,
                "card_id": c.get("card_id") or f"C{ix+1:03d}",
                "rhythm_ids": list(rids),
                "set": frozenset(rids),
            }
        )

    remaining = items[:]
    selected: list[dict] = []
    selected_sets: list[frozenset[str]] = []
    union: set[str] = set()
    freq: dict[str, int] = {}

    while remaining:
        # Evaluate all remaining cards
        scored = []
        for it in remaining:
            s, new_count, max_ov = score_candidate(it["set"], selected=selected_sets, union=union, freq=freq)
            scored.append((s, new_count, -max_ov, -it["orig_index"], it))

        # Pick best score; break ties by original index (lowest wins), then RNG among exact ties
        scored.sort(reverse=True, key=lambda t: t[:4])
        best_score = scored[0][0]
        ties = [t for t in scored if t[0] == best_score and t[1] == scored[0][1] and t[2] == scored[0][2]]
        if len(ties) == 1:
            chosen = ties[0][4]
        else:
            # deterministic tie-break: stable sort by orig_index, then seeded shuffle, then pick first
            tie_items = [t[4] for t in ties]
            tie_items.sort(key=lambda it: it["orig_index"])
            rng.shuffle(tie_items)
            chosen = tie_items[0]

        # Teacher-facing card numbering must match the ordered-deck prefix semantics
        # used by pools ("use cards 1..k"). Therefore we renumber cards here so that
        # deck_order.json has C001..C{N} in *ordered* sequence.
        new_card_id = f"C{len(selected) + 1:03d}"

        # Keep the previous id for debugging/traceability (optional; not used by PDFs).
        selected.append(
            {
                "card_id": new_card_id,
                "card_id_raw": chosen["card_id"],
                "rhythm_ids": chosen["rhythm_ids"],
            }
        )

        selected_sets.append(chosen["set"])

        # Update union/freq
        for r in chosen["set"]:
            union.add(r)
            freq[r] = freq.get(r, 0) + 1

        remaining = [it for it in remaining if it is not chosen]

    out = dict(doc)
    out["ordering"] = {
        "method": "greedy",
        "score": "1000*new_count + shared_gain - 50*max_overlap",
        "tie_break": "orig_index then seeded RNG",
        "seed": seed,
    }
    out["cards"] = selected

    write_json(Path(args.out), out)
    print(f"Wrote ordered deck: {args.out} ({len(selected)} cards)")


if __name__ == "__main__":
    main()
