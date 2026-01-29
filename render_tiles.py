from __future__ import annotations
from pathlib import Path
import subprocess

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
    bank_path = Path("rhytms.txt")
    out_dir = Path("tiles_svg")
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [ln.strip() for ln in bank_path.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.strip().startswith("#")]

    for i, rhythm in enumerate(lines, start=1):
        ly = TILE_LY.replace("%(RHYTHM)", rhythm)
        tile_ly = out_dir / f"rhythm_{i:03d}.ly"
        tile_ly.write_text(ly, encoding="utf-8")

        # -dpreview => tight cropping
        # --svg => vector output
        subprocess.run(
            ["lilypond", "-dpreview", "--svg", "-o", str(out_dir / f"rhythm_{i:03d}"), str(tile_ly)],
            check=True,
        )

    print(f"Rendered {len(lines)} tiles into {out_dir}/")

if __name__ == "__main__":
    main()
