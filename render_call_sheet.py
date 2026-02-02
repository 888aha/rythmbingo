from __future__ import annotations

"""Render a teacher-friendly call sheet (text) in two parts.

Inputs:
  - out/pools.json
  - out/deck_qc.csv
Output:
  - out/call_sheet.txt

Design goals:
  - Part 1: simple, teacher-facing instructions + recommended rhythm sets per symbol
  - Part 2: statistics table (from deck_qc.csv) with short explanations
"""

from pathlib import Path
import argparse
import csv

from rb_utils import read_json


def _read_deck_qc_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"Missing deck QC CSV: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        rows = [dict(row) for row in r]
    if not rows:
        raise SystemExit(f"Empty deck QC CSV: {path}")
    return rows


def _format_table(rows: list[dict[str, str]], cols: list[str]) -> list[str]:
    # Compute column widths from header + data
    widths: dict[str, int] = {c: len(c) for c in cols}
    for row in rows:
        for c in cols:
            widths[c] = max(widths[c], len(str(row.get(c, ""))))

    def fmt_row(d: dict[str, str]) -> str:
        return "  ".join(str(d.get(c, "")).ljust(widths[c]) for c in cols)

    header = "  ".join(c.ljust(widths[c]) for c in cols)
    sep = "  ".join(("-" * widths[c]) for c in cols)
    out = [header, sep]
    out.extend(fmt_row(r) for r in rows)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Render call_sheet.txt in two parts (teacher-facing + statistics).")
    ap.add_argument("--pools", required=True, help="Path to out/pools.json")
    ap.add_argument("--deck-qc-csv", required=True, help="Path to out/deck_qc.csv")
    ap.add_argument("--out", required=True, help="Output out/call_sheet.txt")
    args = ap.parse_args()

    pools_doc = read_json(Path(args.pools))
    pools = pools_doc.get("pools") or []
    if not pools:
        raise SystemExit(f"No pools in {args.pools}")

    qc_rows = _read_deck_qc_csv(Path(args.deck_qc_csv))

    lines: list[str] = []
    lines.append("Rhythm Bingo — Call Sheet")
    lines.append("")
    lines.append("PART 1 — How to run the game")
    lines.append("---------------------------")
    lines.append("")
    lines.append("Each student bingo card has:")
    lines.append("• a card number (ID)")
    lines.append("• a symbol (★ ■ ▲ …)")
    lines.append("")
    lines.append("You may select cards in either of two ways:")
    lines.append("")
    lines.append("Method A — Card number")
    lines.append("Pick bingo cards in number order until everyone has a card.")
    lines.append("")
    lines.append("Method B — Symbol")
    lines.append("Choose one symbol (★, ■, ▲ …).")
    lines.append("Distribute only the cards marked with that symbol and skip the others.")
    lines.append("")
    lines.append("Both methods ensure that:")
    lines.append("• everyone can get bingo")
    lines.append("• at least one full card is possible")
    lines.append("• rhythms are well distributed for the chosen group size")
    lines.append("")
    lines.append("PART 2 — Recommended rhythm sets by group size")
    lines.append("---------------------------------------------")
    lines.append("")

    for p in pools:
        sym = str(p.get("symbol") or "").strip()
        cmin = int(p.get("children_min") or 0)
        cmax = int(p.get("children_max") or 0)
        k_eff = int(p.get("k_effective") or p.get("k") or 0)
        ids = list(p.get("callable_rhythm_ids") or [])

        # Teacher-facing block (no QC jargon here)
        lines.append(f"{sym}  ({cmin}–{cmax} children)")
        lines.append("")
        lines.append("Call among these rhythms")
        lines.append(f"(or use the rhythm cards marked with {sym}):")
        lines.append("")
        if ids:
            # Wrap at ~100 chars for readability in monospaced text
            cur = ""
            for rid in ids:
                add = (rid + " ")
                if len(cur) + len(add) > 100:
                    lines.append(cur.rstrip())
                    cur = ""
                cur += add
            if cur.strip():
                lines.append(cur.rstrip())
        else:
            lines.append("(no callable rhythms — check pools.json / deck_qc.csv)")
        lines.append("")

    lines.append("PART 3 — Statistics and quality metrics")
    lines.append("--------------------------------------")
    lines.append("")
    lines.append("These statistics describe how well the generated student deck works")
    lines.append("for each recommended group size interval.")
    lines.append("")
    lines.append("Source: deck_qc.csv")
    lines.append("")
    lines.append("Key columns:")
    lines.append("• k: number of student cards (1..k) used for the interval")
    lines.append("• union_size: number of distinct rhythms seen on cards 1..k")
    lines.append("• call_pool_size: how many rhythms are callable for this interval")
    lines.append("• min_occ_used: 2 means 'appears at least twice' core rule; 1 means fallback was needed")
    lines.append("• bingo_guarantee_ok: True means every card 1..k has at least one fully-callable bingo line")
    lines.append("• full_card_possible_ok: True means at least one card 1..k can become a full card")
    lines.append("• duplicate_pairs: must be 0 (no identical cards in 1..k)")
    lines.append("• max_overlap / mean_overlap: similarity diagnostics (higher = more similar cards)")
    lines.append("")

    # Render table: show all CSV columns (whatever compute_deck_qc.py emits)
    cols = list(qc_rows[0].keys())
    # Prefer a stable, readable order if present
    preferred = [
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
        "duplicate_pairs",
        "max_overlap",
        "mean_overlap",
    ]
    cols_eff = [c for c in preferred if c in cols] + [c for c in cols if c not in preferred]
    lines.extend(_format_table(qc_rows, cols_eff))
    lines.append("")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote call sheet: {out_path}")


if __name__ == "__main__":
    main()
