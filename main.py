# main.py
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_py(script: str, *args: str) -> None:
    """Run one of our project scripts using the current Python interpreter."""
    subprocess.run([sys.executable, script, *args], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Rhythm Bingo: deterministic build pipeline")
    ap.add_argument("--out-dir", default="out", help="Directory for computed artifacts (JSON/CSV/call sheet).")
    ap.add_argument("--config", default="out/config_pools.json", help="Pools config JSON.")
    ap.add_argument("--bank", default="rhythms.txt", help="Rhythm bank file.")
    ap.add_argument("--tiles-dir", default="tiles_svg", help="Directory for rendered SVG tiles.")
    ap.add_argument("--skip-tiles", action="store_true", help="Skip LilyPond tile rendering stage.")
    ap.add_argument("--skip-catalog", action="store_true", help="Skip rhythm catalog PDF.")
    ap.add_argument("--skip-cards", action="store_true", help="Skip student bingo cards PDF.")
    ap.add_argument("--skip-caller", action="store_true", help="Skip caller cards PDF.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Missing config: {config_path}. Expected default at out/config_pools.json")

    deck_raw = out_dir / "deck_raw.json"
    deck_order = out_dir / "deck_order.json"
    pools_json = out_dir / "pools.json"
    call_sheet_txt = out_dir / "call_sheet.txt"
    deck_qc_json = out_dir / "deck_qc.json"
    deck_qc_csv = out_dir / "deck_qc.csv"
    caller_cards_pdf = out_dir / "caller_cards.pdf"
    bingo_cards_pdf = out_dir / "bingo_cards.pdf"

    if not args.skip_tiles:
        run_py("render_tiles.py")

    if not args.skip_catalog:
        run_py("catalog_rhythms.py")

    run_py(
        "generate_deck_raw.py",
        "--config",
        str(config_path),
        "--bank",
        str(args.bank),
        "--out",
        str(deck_raw),
    )

    # Deterministic greedy ordering
    run_py(
        "compute_deck_order.py",
        "--in",
        str(deck_raw),
        "--out",
        str(deck_order),
    )

    run_py(
        "compute_pools.py",
        "--config",
        str(config_path),
        "--deck",
        str(deck_order),
        "--out",
        str(pools_json),
        "--call-sheet",
        str(call_sheet_txt),
    )

    run_py(
        "compute_deck_qc.py",
        "--config",
        str(config_path),
        "--deck",
        str(deck_order),
        "--pools",
        str(pools_json),
        "--out-json",
        str(deck_qc_json),
        "--out-csv",
        str(deck_qc_csv),
    )

    if not args.skip_caller:
        run_py(
            "render_caller_cards.py",
            "--pools",
            str(pools_json),
            "--tiles",
            str(args.tiles_dir),
            "--out",
            str(caller_cards_pdf),
        )

    if not args.skip_cards:
        run_py(
            "compose_cards.py",
            "--deck",
            str(deck_order),
            "--tiles",
            str(args.tiles_dir),
            "--pools",
            str(pools_json),
            "--out",
            str(bingo_cards_pdf),
        )

    print("Done.")
    print("Key outputs:")
    print(f" - {Path(args.tiles_dir)}/")
    print(" - rhythm_catalog.pdf")
    print(f" - {bingo_cards_pdf}")
    print(f" - {pools_json}")
    print(f" - {caller_cards_pdf}")
    print(f" - {call_sheet_txt}")
    print(f" - {deck_qc_csv}")


if __name__ == "__main__":
    main()
