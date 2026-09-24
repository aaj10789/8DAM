# Circuit detector slices

Each circuit has one SVG showing operations and detector support at every tick, including the initial and final intervals. A circuit with `N` `TICK` instructions has frames `Tick 0` through `Tick N`, inclusive.

The diagrams use Stim 1.15.0 `detslice-with-ops-svg`. Red, green, and blue indicate X, Y, and Z Pauli support. All detector coordinates are included; logical observable slices are excluded. Control-X and target-Z labels identify the readout circuit, not a detector filter.

Open an SVG and zoom in to inspect individual frames. If a repository preview is unavailable, download the SVG and open it in a browser.

## Single LCNOT

| Configuration | Control X | Target Z |
|---|---|---|
| 3-3-3 | [All ticks SVG](../single_lcnot/3-3-3/detector_slices/control_x_all_ticks.svg) | [All ticks SVG](../single_lcnot/3-3-3/detector_slices/target_z_all_ticks.svg) |
| 3-7-3 | [All ticks SVG](../single_lcnot/3-7-3/detector_slices/control_x_all_ticks.svg) | [All ticks SVG](../single_lcnot/3-7-3/detector_slices/target_z_all_ticks.svg) |
| 5-5-5 | [All ticks SVG](../single_lcnot/5-5-5/detector_slices/control_x_all_ticks.svg) | [All ticks SVG](../single_lcnot/5-5-5/detector_slices/target_z_all_ticks.svg) |
| 5-11-5 | [All ticks SVG](../single_lcnot/5-11-5/detector_slices/control_x_all_ticks.svg) | [All ticks SVG](../single_lcnot/5-11-5/detector_slices/target_z_all_ticks.svg) |
| 7-7-7 | [All ticks SVG](../single_lcnot/7-7-7/detector_slices/control_x_all_ticks.svg) | [All ticks SVG](../single_lcnot/7-7-7/detector_slices/target_z_all_ticks.svg) |
| 9-9-9 | [All ticks SVG](../single_lcnot/9-9-9/detector_slices/control_x_all_ticks.svg) | [All ticks SVG](../single_lcnot/9-9-9/detector_slices/target_z_all_ticks.svg) |

## Dual LCNOT simulation and reference

| Circuit | Detector slices |
|---|---|
| Shared-ancilla dual LCNOT target-Z circuit | [All ticks SVG](../dual_lcnot/shared_ancilla_distance3/detector_slices/target_z_all_ticks.svg) |
| Independent-pair reference circuit | [All ticks SVG](../dual_lcnot/independent_3-3-3_pair/detector_slices/target_z_all_ticks.svg) |

The independent-pair reference diagram shows its underlying single 3-3-3 target-Z circuit; the pair error probability is `2*q-q^2`, where `q` is the single-CNOT error rate.

## Regenerate the diagrams

From the repository root, after [installing the dependencies](../README.md#run-and-verify), regenerate all diagrams:

```sh
.venv/bin/python scripts/export_detector_slices.py --all --output generated_detector_slices
```

SVGs and shared READMEs go to `generated_detector_slices/<configuration>/detector_slices/`. Rendering JSON records go to `generated_detector_slices/scripts/data/<configuration>/detector_slices/`. Here, `<configuration>` is a repository path such as `single_lcnot/3-7-3`.

For one readout circuit:

```sh
.venv/bin/python scripts/export_detector_slices.py single_lcnot/3-7-3/control_x.stim --output generated_views/3-7-3_control_x
```

This writes the SVG and `readme.md` directly into the requested directory, with the rendering JSON under its `scripts/data/<configuration>/detector_slices/` path.

Omit `--output` to use the packaged locations. Identical files are accepted; different existing files are not overwritten. Rendering uses the archived noiseless circuits and draws no simulation shots.
