from __future__ import annotations
from pathlib import Path
import subprocess
import re
from fractions import Fraction

_WS_RE = re.compile(r"\s+")
_DUR_RE = re.compile(r"^(?P<num>\d+)(?P<dots>\.*)$")

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

def _strip_lilypond_wrappers(tok: str) -> str:
    """Remove a few common wrapper characters that are irrelevant for duration sums.

    This is intentionally small and conservative. We are NOT trying to parse LilyPond.
    We only want to tolerate benign notation clutter that might appear in rhythm banks.
    """
    t = tok.strip()
    if not t:
        return ""

    # Remove beaming / grouping / slur parens, and bar separators if someone typed them.
    # Keep the inside unchanged.
    t = t.replace("[", "").replace("]", "")
    t = t.replace("(", "").replace(")", "")
    t = t.replace("{", "").replace("}", "")
    t = t.replace("|", "")

    # Remove ties (we treat tied notes as separate duration-bearing tokens if present).
    t = t.replace("~", "")

    return t.strip()


def _token_duration_to_fraction(tok: str, *, last_dur: str | None) -> tuple[Fraction, str | None]:
    """Parse a single LilyPond-ish token and return (duration_fraction, new_last_dur).

    Supported token shapes (very small subset):
      - c4, r8, d16., c2.. etc
      - pitch is ignored; only duration matters
      - duration may be omitted to repeat previous duration (LilyPond behavior)

    Returns:
      - (0, last_dur) for tokens that do not carry duration (ignored tokens)
      - raises ValueError on malformed duration when the token looks like a note/rest
    """
    t = _strip_lilypond_wrappers(tok)
    if not t:
        return Fraction(0), last_dur

    # Quick ignore of common non-duration commands if they appear (conservative list)
    if t.startswith("\\"):
        return Fraction(0), last_dur

    lead = t[0].lower()
    if lead not in "abcdefgr":
        # Unknown token kind: ignore for sum purposes (don’t guess)
        return Fraction(0), last_dur

    # Strip pitch and octave marks: a''4 -> 4, c, -> (duration may be missing)
    i = 1
    while i < len(t) and t[i] in ("'", ","):
        i += 1
    rest = t[i:]

    # If duration is omitted, reuse previous duration (LilyPond shorthand)
    if rest == "":
        if not last_dur:
            raise ValueError(f"Missing duration with no previous duration: {tok!r}")
        rest = last_dur

    m = _DUR_RE.match(rest)
    if not m:
        raise ValueError(f"Malformed duration part {rest!r} in token {tok!r}")

    num = int(m.group("num"))
    dots = m.group("dots") or ""

    if num <= 0:
        raise ValueError(f"Invalid duration denominator {num} in token {tok!r}")

    # Base duration: 1 -> whole, 2 -> half, 4 -> quarter, ...
    base = Fraction(1, num)

    # Dots: 1 dot = +1/2 base, 2 dots = +1/2 +1/4 base, etc.
    dur = base
    add = base
    for _ in dots:
        add = add / 2
        dur += add

    new_last = f"{num}{dots}"
    return dur, new_last


def _rhythm_line_total_duration(line: str) -> Fraction:
    """Return the exact total duration of a rhythm line as a Fraction of a whole note.

    - Very small subset: sums durations of note/rest tokens.
    - Ignores unknown tokens (but does not attempt to “fix” them).
    - Supports LilyPond shorthand where duration may be omitted and repeats last.
    """
    s = _WS_RE.sub(" ", line.strip())
    if not s:
        return Fraction(0)

    total = Fraction(0)
    last_dur: str | None = None
    for raw_tok in s.split(" "):
        if not raw_tok:
            continue
        d, last_dur = _token_duration_to_fraction(raw_tok, last_dur=last_dur)
        total += d
    return total


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

        # Enforce: each rhythm is exactly one bar of 4/4 (total duration == 1 whole note).
        # No fail-fast: invalid lines are commented out with a diagnostic.
        try:
            total = _rhythm_line_total_duration(stripped)
        except Exception as e:
            rewritten.append(f"# INVALID (parse error): {stripped}  # {e}")
            changed = True
            continue

        if total != Fraction(1, 1):
            rewritten.append(
                f"# INVALID (sum={total} of whole note; expected 1): {stripped}"
            )
            changed = True
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
        print(f"NOTE: Updated {bank_path} (commented out invalid and/or duplicate rhythm lines).")

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
