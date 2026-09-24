# Independent pair of 3-3-3 lCNOTs: single-circuit target-Z reference

Standard 3-3-3 target-Z reference circuit. The two-independent-CNOT pair curve is computed from its single-circuit error probability `q` as `2*q - q^2`.

| Readout | Simulation circuit | Crumble circuit | Results | Detector slices |
| --- | --- | --- | --- | --- |
| Target Z | [target_z.stim](target_z.stim) | [View source](target_z_crumble.stim) | [Data](target_z_results.csv) | [All ticks SVG](detector_slices/target_z_all_ticks.svg) |

## Explore in Crumble

Copy a Crumble source from the table using **Raw** on GitHub. In [Crumble](https://algassert.com/crumble), select **Show Import/Export**, paste the text, and select **Import from Stim Circuit**.

After downloading the repository, open an HTML launcher or copy the full URL into a browser:

- [target_z_crumble.html](target_z_crumble.html); [full circuit URL](target_z_crumble_url.txt).

## Data and simulation

For each readout, [noisy_circuits](noisy_circuits) contains ten inputs: `<readout>_p001.stim` through `<readout>_p010.stim`, for `p_link = 0.001, 0.002, ..., 0.010`. Each point uses 45,000,000 complete circuit shots, no discards, and standard PyMatching with correlations disabled.

The comparison uses pointwise 95% Wilson intervals. See [noise and decoding](../../docs/SCIENTIFIC_LIMITATIONS.md).

From the repository root, check one readout without sampling:

```sh
.venv/bin/python scripts/run_simulation.py dual_lcnot/independent_3-3-3_pair/target_z.stim --p-link 0.01 --check-only
```

[Setup and simulation](../../docs/METHODS.md) | [Repository overview](../../README.md)
