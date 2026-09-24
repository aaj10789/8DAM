# Data dictionary

Each configuration contains `control_x_results.csv` and/or
`target_z_results.csv`. Rates describe the named logical readout per complete
circuit. Each point uses 45,000,000 shots with no discards.

## Single-LCNOT results

| Columns | Meaning |
| --- | --- |
| `p_link` | Inter-QPU two-qubit depolarizing probability. |
| `p1`, `bulk_p2` | Local one- and two-qubit noise probabilities. |
| `shots`, `retained_shots`, `discards` | Sample counts before and after discards. |
| `logical_errors`, `ler` | Readout failures and `logical_errors / retained_shots`. |
| `clopper_pearson_95_low`, `clopper_pearson_95_high` | Two-sided 95% Clopper-Pearson interval. |
| `boundary_x` | Geometrical partition between QPUs. |
| `crossing_two_qubit_locations` | Number of crossing-gate applications in the circuit. |
| `shortest_graphlike_error` | Recorded graphlike-distance check. |
| `circuit_sha256`, `noisy_circuit_sha256` | Checksums of the original noise-free circuit and saved noisy input. |
| `strict_dem_sha256`, `native_dem_sha256` | Checksums of normalized detector error models. |

Other source and aggregation hashes identify the associated provenance records.

## Dual-LCNOT and reference results

| Columns | Meaning |
| --- | --- |
| `series` | `dual_bottom`, `dual_top`, `dual_either`, `single_d3`, or `two_independent_d3`. |
| `source_shots`, `source_errors` | Counts used to calculate the estimate. |
| `ler`, `ci95_low`, `ci95_high` | Error rate and pointwise 95% confidence interval. |

Direct estimates use Wilson intervals. The `two_independent_d3` curve applies
`f(q) = 2*q - q*q` to the single-CNOT rate and its interval endpoints. Its source
counts are from the underlying single circuit. Dual aggregate records also
include `both`, with `either = top + bottom - both`.

## Supporting files

Metadata JSON files in `scripts/data/` identify each experiment's inputs,
decoder settings, counts, and checksums. Circuit paths are relative to the
public configuration folder; saved DEM paths are relative to its matching
support folder. `scripts/data/release_manifest.json` indexes the experiments.
`SHA256SUMS` verifies the repository files.
