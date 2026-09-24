# Reproducing the experiments

Use Python 3.10 or 3.11 and the [installation commands](../README.md#run-and-verify)
in the repository README. `requirements.txt` pins Stim 1.15.0, PyMatching 2.4.0,
NumPy 1.26.4, and SciPy 1.15.3.

## Simulation inputs

Each configuration contains `control_x.stim` and/or `target_z.stim`, results
CSVs, and ten noisy inputs per readout in `noisy_circuits/`. The filenames
`p001` through `p010` correspond to `p_link = 0.001` through `0.010`.

The runner selects the saved noisy circuit for the requested `--p-link`.
It loads the saved detector error model (DEM) or regenerates it using the
recorded settings and verifies its checksum. DEM extraction uses decomposed
errors, with no disjoint-error approximations or ignored decomposition failures.
See [noise and decoding](SCIENTIFIC_LIMITATIONS.md) for the noise model.

Each experiment's `control_x_metadata.json` or `target_z_metadata.json` under
`scripts/data/` records the circuit inputs, decoder settings, archived counts,
and checksums. Its directory mirrors the public configuration path.

## New simulations

Use the [simulation commands](../README.md#run-and-verify) to select a circuit,
link-error rate, and number of shots. Each run saves its counts, error rates,
confidence intervals, and seed in `new_runs/`. These are new Monte Carlo
samples; the published counts remain in the configuration's results CSV.

## Provenance files

The provenance JSON files under `scripts/data/` record circuit and data sources
and validation results, linking the published data to their simulation inputs.

From the repository root, run `.venv/bin/python scripts/verify_release.py` to
verify the archived files and counts. Add `--models` to check all decoder models.
