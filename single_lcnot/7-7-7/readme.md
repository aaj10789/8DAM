# Single-LCNOT: 7-7-7

Control-X and target-Z results give the failure probability of each logical readout per complete circuit.

| Readout | Simulation circuit | Crumble circuit | Results | Detector slices |
| --- | --- | --- | --- | --- |
| Control X | [control_x.stim](control_x.stim) | [View source](control_x_crumble.stim) | [Data](control_x_results.csv) | [All ticks SVG](detector_slices/control_x_all_ticks.svg) |
| Target Z | [target_z.stim](target_z.stim) | [View source](target_z_crumble.stim) | [Data](target_z_results.csv) | [All ticks SVG](detector_slices/target_z_all_ticks.svg) |

## Explore in Crumble

Copy a Crumble source from the table using **Raw** on GitHub. In [Crumble](https://algassert.com/crumble), select **Show Import/Export**, paste the text, and select **Import from Stim Circuit**.

After downloading the repository, open an HTML launcher or copy the full URL into a browser:

- [control_x_crumble.html](control_x_crumble.html); [full circuit URL](control_x_crumble_url.txt).
- [target_z_crumble.html](target_z_crumble.html); [full circuit URL](target_z_crumble_url.txt).

## Data and simulation

For each readout, [noisy_circuits](noisy_circuits) contains ten inputs: `<readout>_p001.stim` through `<readout>_p010.stim`, for `p_link = 0.001, 0.002, ..., 0.010`. Each point uses 45,000,000 complete circuit shots, no discards, and standard PyMatching with correlations disabled.

Error bars are two-sided 95% Clopper-Pearson intervals. See the [figures](../figures/readme.md).

From the repository root, check one readout without sampling:

```sh
.venv/bin/python scripts/run_simulation.py single_lcnot/7-7-7/control_x.stim --p-link 0.01 --check-only
```

[Setup and simulation](../../docs/METHODS.md) | [Repository overview](../../README.md)
