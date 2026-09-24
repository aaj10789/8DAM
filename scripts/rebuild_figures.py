#!/usr/bin/env python3
"""Compile the archived, self-contained figure TeX into a separate directory.

The plotted data are embedded in the TeX. This does not read or alter CSVs,
resample circuits, or overwrite the archived paper figures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reproduced_figures"
FIGURES = {
    "small_x": "single_lcnot/figures/small_footprint_logical_x_LER.tex",
    "small_z": "single_lcnot/figures/small_footprint_logical_z_LER.tex",
    "large_x": "single_lcnot/figures/large_footprint_logical_x_LER.tex",
    "large_z": "single_lcnot/figures/large_footprint_logical_z_LER.tex",
    "dual_z": "dual_lcnot/figures/publication_ler_standard_linear_inset_45m.tex",
}
PREFLIGHT = r"""\documentclass[tikz,border=2pt]{standalone}
\usepackage{fontspec}
\usepackage{unicode-math}
\usepackage{pgfplots}
\usepgfplotslibrary{groupplots}
\usetikzlibrary{plotmarks}
\IfFontExistsTF{Times New Roman}{}{\errmessage{Required font missing: Times New Roman}}
\IfFontExistsTF{STIX Two Math}{}{\errmessage{Required font missing: STIX Two Math}}
\setmainfont{Times New Roman}
\setmathfont{STIX Two Math}
\pgfplotsset{compat=1.18}
\begin{document}Figure dependencies: $X,Z$\end{document}
"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_tex(engine: str, source: Path, *, passes: int) -> str:
    """Run XeLaTeX directly, with shell escape disabled and bounded execution."""
    logs = []
    for _ in range(passes):
        completed = subprocess.run(
            [engine, "-no-shell-escape", "-interaction=nonstopmode",
             "-halt-on-error", "-file-line-error", source.name],
            cwd=source.parent, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=180,
            check=False,
        )
        logs.append(completed.stdout)
        if completed.returncode:
            raise RuntimeError(
                f"XeLaTeX failed for {source.name}. Check that standalone, "
                "fontspec, unicode-math, PGFPlots 1.18 or later, Times New Roman, "
                "and STIX Two Math are installed. No font substitutions are made.\n"
                + "\n".join(completed.stdout.splitlines()[-35:])
            )
    if not source.with_suffix(".pdf").is_file():
        raise RuntimeError(f"The compiler produced no PDF for {source.name}")
    return "\n".join(logs)


def output_path(raw: Path) -> Path:
    output = raw.expanduser().resolve()
    # Within the repository, keep generated output in the designated subtree.
    # Reject ancestors too, so a custom root cannot address archived paths.
    if ROOT.is_relative_to(output):
        raise ValueError("The output directory cannot be the repository or its ancestor")
    if output.is_relative_to(ROOT) and not output.is_relative_to(DEFAULT_OUTPUT):
        raise ValueError(
            "Within the repository, use reproduced_figures/ (or a subdirectory). "
            "An output directory outside the repository is also supported."
        )
    if output.exists() and not output.is_dir():
        raise ValueError(f"The output path is not a directory: {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List figure IDs without requiring LaTeX")
    parser.add_argument("--figure", action="append", choices=["all", *FIGURES],
                        help="Figure to compile; repeat to select several (default: all)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Separate output root (default: repository/reproduced_figures)")
    parser.add_argument("--engine", default="xelatex",
                        help="XeLaTeX command or path to its executable (default: xelatex on PATH)")
    args = parser.parse_args()
    if args.list:
        for figure, relative in FIGURES.items():
            print(f"{figure}\t{relative}")
        return 0
    selected = list(FIGURES) if not args.figure or "all" in args.figure else list(dict.fromkeys(args.figure))
    try:
        output = output_path(args.output)
        engine = shutil.which(args.engine)
        if engine is None:
            raise ValueError(
                f"XeLaTeX executable not found: {args.engine}. Install a TeX distribution "
                "with XeLaTeX, or pass --engine /path/to/xelatex. See docs/FIGURES.md."
            )
        # Keep the xelatex executable name: TeX engines select their format from
        # argv[0], so resolving a xelatex -> xetex symlink would change behavior.
        engine = str(Path(engine).absolute())
        sources = [(figure, Path(FIGURES[figure])) for figure in selected]
        for _, relative in sources:
            if not (ROOT / relative).is_file():
                raise ValueError(f"Archived TeX source is missing: {relative}")
            directory = output / relative.parent
            if directory.exists() and any(directory.glob(relative.stem + ".*")):
                raise ValueError(
                    f"Output already exists for {relative.stem}; choose a fresh --output directory."
                )
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".figure-build-", dir=output) as temporary:
            staging = Path(temporary)
            preflight = staging / "dependency_check.tex"
            preflight.write_text(PREFLIGHT, encoding="utf-8")
            compile_tex(engine, preflight, passes=1)
            builds = []
            for figure, relative in sources:
                source = ROOT / relative
                folder = staging / figure
                folder.mkdir()
                copied = folder / relative.name
                shutil.copyfile(source, copied)
                log = compile_tex(engine, copied, passes=2)
                copied.with_suffix(".compile.txt").write_text(log, encoding="utf-8")
                report = {
                    "figure": figure,
                    "source": relative.as_posix(),
                    "source_sha256": digest(source),
                    "output_pdf_sha256": digest(copied.with_suffix(".pdf")),
                    "method": "Two XeLaTeX passes over an unchanged copy of the archived TeX; data embedded in TeX",
                    "csv_read": False,
                    "simulation_performed": False,
                }
                copied.with_suffix(".build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                builds.append((relative, folder))
            # Publish outputs only after every selected figure compiles successfully.
            for relative, folder in builds:
                destination = output / relative.parent
                destination.mkdir(parents=True, exist_ok=True)
                for artifact in folder.iterdir():
                    if artifact.is_file():
                        target = destination / artifact.name
                        # Exclusive creation also protects against a concurrent build.
                        with target.open("xb") as handle:
                            handle.write(artifact.read_bytes())
                print(destination / relative.with_suffix(".pdf").name)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
