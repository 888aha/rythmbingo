from __future__ import annotations

import json
import unittest
from pathlib import Path


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _bingo_lines_3x3(rids: list[str]) -> list[list[str]]:
    if len(rids) != 9:
        raise ValueError(f"Expected 9 rhythm IDs for 3x3, got {len(rids)}")

    idx_lines: list[list[int]] = [
        # rows (top->bottom)
        [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],
        # cols (left->right)
        [0, 3, 6],
        [1, 4, 7],
        [2, 5, 8],
        # diagonals (main, anti)
        [0, 4, 8],
        [2, 4, 6],
    ]
    return [[rids[i] for i in idxs] for idxs in idx_lines]


class TestPoolFairnessV02(unittest.TestCase):
    """Artifact-based tests for pool fairness guarantees (spec v0.2).

    These tests validate the *produced* artifacts:
      - out/deck_order.json
      - out/pools.json

    If artifacts are missing, tests are skipped with a clear message.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.out_dir = cls.repo_root / "out"
        cls.deck_path = cls.out_dir / "deck_order.json"
        cls.pools_path = cls.out_dir / "pools.json"

        if not cls.deck_path.is_file() or not cls.pools_path.is_file():
            raise unittest.SkipTest(
                "Missing build artifacts. Run the pipeline first (e.g. `python main.py` or `run.bat`). "
                "Expected: out/deck_order.json and out/pools.json"
            )

        cls.deck_doc = _read_json(cls.deck_path)
        cls.pools_doc = _read_json(cls.pools_path)

        cls.cards = cls.deck_doc.get("cards") or []
        if not cls.cards:
            raise unittest.SkipTest("deck_order.json has no cards; cannot test pools fairness.")

        cls.pools = cls.pools_doc.get("pools") or []
        if not cls.pools:
            raise unittest.SkipTest("pools.json has no pools; cannot test pools fairness.")

    def test_deck_integrity_each_card_has_9_unique_rhythms(self) -> None:
        for i0, c in enumerate(self.cards):
            card_id = str(c.get("card_id") or f"C{i0+1:03d}")
            rids = list(c.get("rhythm_ids") or [])
            self.assertEqual(
                len(rids),
                9,
                msg=f"{card_id}: expected 9 rhythm_ids, got {len(rids)}",
            )
            self.assertEqual(
                len(set(rids)),
                9,
                msg=f"{card_id}: duplicate rhythm_id within card (must be unique per 3×3)",
            )

    def test_each_pool_satisfies_acceptance_checks_A_B_D(self) -> None:
        for p in self.pools:
            pool_id = str(p.get("pool_id") or "")
            sym = str(p.get("symbol") or "?")
            k_eff = int(p.get("k_effective") or 0)

            self.assertGreater(
                k_eff, 0, msg=f"{sym} ({pool_id}): k_effective must be >= 1"
            )
            self.assertLessEqual(
                k_eff, len(self.cards), msg=f"{sym} ({pool_id}): k_effective exceeds deck size"
            )

            callable_ids = list(p.get("callable_rhythm_ids") or [])
            callable_set = set(callable_ids)

            # D1: non-empty
            self.assertGreaterEqual(
                len(callable_set), 1, msg=f"{sym} ({pool_id}): callable set must be non-empty"
            )

            sub_cards = self.cards[:k_eff]

            # D2: no ghost rhythms (Callable ⊆ rhythms on Cards(p))
            rhythms_on_cards: set[str] = set()
            for c in sub_cards:
                rhythms_on_cards.update(c.get("rhythm_ids") or [])
            ghosts = callable_set - rhythms_on_cards
            self.assertFalse(
                ghosts,
                msg=f"{sym} ({pool_id}): ghost rhythms not present on cards 1..{k_eff}: {sorted(ghosts)}",
            )

            # A: bingo guarantee (everyone)
            failures = []
            for i0, c in enumerate(sub_cards):
                card_id = str(c.get("card_id") or f"C{i0+1:03d}")
                rids = list(c.get("rhythm_ids") or [])
                lines = _bingo_lines_3x3(rids)
                ok = any(all(x in callable_set for x in line) for line in lines)
                if not ok:
                    failures.append(card_id)

            self.assertEqual(
                len(failures),
                0,
                msg=(
                    f"{sym} ({pool_id}): bingo guarantee failed for {len(failures)} card(s): "
                    f"{', '.join(failures[:10])}"
                    + (" ..." if len(failures) > 10 else "")
                ),
            )

            # B: full-card guarantee (at least one)
            full_candidates = 0
            for c in sub_cards:
                rids = set(c.get("rhythm_ids") or [])
                if rids.issubset(callable_set):
                    full_candidates += 1

            self.assertGreaterEqual(
                full_candidates,
                1,
                msg=f"{sym} ({pool_id}): full-card guarantee failed (no full-card candidates among 1..{k_eff})",
            )

            # Optional: if pools.json contains guarantees flags, assert them.
            g = p.get("guarantees")
            if isinstance(g, dict):
                self.assertIs(
                    g.get("bingo_all_cards"),
                    True,
                    msg=f"{sym} ({pool_id}): guarantees.bingo_all_cards must be true",
                )
                self.assertIs(
                    g.get("full_card_exists"),
                    True,
                    msg=f"{sym} ({pool_id}): guarantees.full_card_exists must be true",
                )


if __name__ == "__main__":
    unittest.main()
