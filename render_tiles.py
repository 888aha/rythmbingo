from __future__ import annotations
from pathlib import Path
import subprocess
import re


_WS_RE = re.compile(r"\s+")


def _normalize_rhythm_line(line: str) -> str:
    """Normalize a rhythm bank line for duplicate detection.

    We want to catch *render-identical* rhythms in a RhythmicStaff where pitch is
    irrelevant. So we:

    - collapse whitespace
    - map any note pitch (a..g, with optional octave marks) to a canonical 'c'
    - keep rests ('r') as rests

    This is a heuristic (not a full LilyPond parser), but it correctly dedupes
    the main cases we expect in a classroom rhythm bank.
    """
    s = _WS_RE.sub(" ", line.strip())
    if not s:
        return ""

    out_toks: list[str] = []
    for tok in s.split(" "):
        if not tok:
            continue
        t = tok.strip()
        if not t:
            continue

        lead = t[0].lower()

        # Rest tokens: keep as-is (except whitespace normalization)
        if lead == "r":
            out_toks.append("r" + t[1:])
            continue

        # Note tokens: canonicalize pitch to 'c' and remove octave marks
        if lead in "abcdefg":
            rest = t[1:]
            while rest and rest[0] in ("'", ","):
                rest = rest[1:]
            out_toks.append("c" + rest)
            continue

        # Unknown token kind: keep verbatim so we don't incorrectly merge things.
        out_toks.append(t)

    return " ".join(out_toks)

TILE_LY = r"""
\version "2.22.2"

#(set-global-staff-size 30)

\paper {
  indent = 0
  tagline = ##f
  top-margin = 0\mm
  bottom-margin = 0\mm
  left-margin = 0\mm
  right-margin = 0\mm
}

\layout {
  ragged-right = ##t
  ragged-last = ##t

  \context {
    \RhythmicStaff
    \remove "Time_signature_engraver"
  }
}

\score {
  \new RhythmicStaff {
    \time 4/4
    \stemUp
    \override StaffSymbol.line-count = #1
    \override StaffSymbol.staff-space = #(magstep -2)
    \override BarLine.stencil = ##f
\override StaffSymbol.line-count = #1
\override StaffSymbol.stencil = ##f


\override Rest.font-size = #2
\override Rest.Y-offset = #0
%\override MultiMeasureRest.font-size = #2



    %(RHYTHM)

\bar ""

  }
}
"""


def main() -> None:
    bank_path = Path("rhythms.txt")
    out_dir = Path("tiles_svg")
    out_dir.mkdir(parents=True, exist_ok=True)

    # CLEAN old generated files so stale tiles can't survive bank edits
    for p in out_dir.glob("rhythm_*.ly"):
        p.unlink(missing_ok=True)
    for p in out_dir.glob("rhythm_*.svg"):
        p.unlink(missing_ok=True)

    # Enforce: rhythm bank lines are unique (no duplicate non-comment lines).
    # No fail-fast: duplicates are automatically commented out in-place.
    raw_lines = bank_path.read_text(encoding="utf-8").splitlines()
    seen_norm: dict[str, int] = {}  # normalized -> first (1-based) line number
    rewritten: list[str] = []
    rhythms_to_render: list[str] = []
    changed = False

    for lineno1, raw in enumerate(raw_lines, start=1):
        stripped = raw.strip()

        # Preserve blanks and existing comments verbatim
        if not stripped or stripped.startswith("#"):
            rewritten.append(raw)
            continue

        norm = _normalize_rhythm_line(stripped)
        if norm and norm in seen_norm:
            first = seen_norm[norm]
            rewritten.append(f"# DUPLICATE of line {first}: {stripped}")
            changed = True
            continue

        if norm:
            seen_norm[norm] = lineno1
        rewritten.append(stripped)
        rhythms_to_render.append(stripped)

    if changed:
        bank_path.write_text("\n".join(rewritten).rstrip() + "\n", encoding="utf-8")
        print(f"NOTE: Updated {bank_path} (commented out duplicate rhythm lines).")

    for i, rhythm in enumerate(rhythms_to_render, start=1):
        ly = TILE_LY.replace("%(RHYTHM)", rhythm)
        tile_ly = out_dir / f"rhythm_{i:03d}.ly"
        tile_ly.write_text(ly, encoding="utf-8")

        # -dpreview => tight cropping
        # --svg => vector output
        subprocess.run(
            ["lilypond", "-dpreview", "--svg", "-o", str(out_dir / f"rhythm_{i:03d}"), str(tile_ly)],
            check=True,
        )

    print(f"Rendered {len(rhythms_to_render)} tiles into {out_dir}/")

if __name__ == "__main__":
    main()
