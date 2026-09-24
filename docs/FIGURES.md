# Rebuilding the manuscript figures

Find PDFs, TeX sources, and data in the [single-LCNOT](../single_lcnot/figures/readme.md)
and [dual-LCNOT](../dual_lcnot/figures/readme.md) figure folders.

## Dependencies

Use Python 3.10+ (standard library only), XeLaTeX, `standalone`, `fontspec`,
`unicode-math`, and PGFPlots 1.18+ with TikZ, `plotmarks`, and `groupplots`.
Install **Times New Roman** and **STIX Two Math** for XeLaTeX; fonts are not
bundled or substituted.

## Commands

Run from the repository root:

```sh
python3 scripts/rebuild_figures.py --list
python3 scripts/rebuild_figures.py
```

The second command rebuilds all five figures. Select figures with `--figure`:

```sh
python3 scripts/rebuild_figures.py --figure small_x
python3 scripts/rebuild_figures.py --figure large_x --figure large_z --output reproduced_figures/large
```

| Figure ID | Experiment |
|---|---|
| `small_x` | Small-footprint control-X comparison |
| `small_z` | Small-footprint target-Z comparison |
| `large_x` | Large-footprint control-X comparison |
| `large_z` | Large-footprint target-Z comparison |
| `dual_z` | Dual target-Z and independent single-CNOT reference comparison |

If XeLaTeX is not on `PATH`, specify its executable:

```sh
python3 scripts/rebuild_figures.py --engine /path/to/xelatex
```

Outputs are saved under `reproduced_figures/single_lcnot/figures/` and
`reproduced_figures/dual_lcnot/figures/`. Existing figure outputs are not
overwritten. For another build, choose a fresh `--output` directory within
`reproduced_figures/` or outside the repository, but not an ancestor of it.

## Plotted data

The script compiles data embedded in the TeX files. **CSV edits do not change
the rebuilt figures.** To plot revised results, update the TeX series,
confidence-interval endpoints, and inset tables.

See the [data dictionary](DATA_DICTIONARY.md) for interval methods and the
independent-pair calculation, [methods](METHODS.md) for simulation commands,
and [noise and decoding](SCIENTIFIC_LIMITATIONS.md) for settings.
