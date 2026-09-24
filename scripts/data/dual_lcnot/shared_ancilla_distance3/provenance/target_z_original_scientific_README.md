> **Archived 2M-shot study.** Counts and commands below describe the original workspace. For the current 45M-shot study, see [results](../../../../../dual_lcnot/shared_ancilla_distance3/target_z_results.csv), [metadata](../target_z_metadata.json), and [reproduction commands](../../../../../README.md#run-and-verify).

# First-merge link-noise repair and LER comparison

The selected repair extends the first merged-bus syndrome extraction from four
rounds to six. It inserts one alternating A/B pair before the original tick 38,
while retaining every original quantum operation in its original order.

Use `repaired_z.stim` for the modified experiment. Its observable order remains
**0 = bottom target Z, 1 = top target Z**. It includes all 976 detector checks and
both updated `OBSERVABLE_INCLUDE` annotations. Old record offsets must not be
pasted into the longer circuit.

Historical comparison figure: `before_after_correlated.png` (not included in this release).

## Completed LER result

All 20,000,000 fresh after-repair shots are complete. At p_link=0.010 (1%),
with 2,000,000 shots in each before/after experiment:

| Decoder and observable | Before failures | After failures | Before LER | After LER |
|---|---:|---:|---:|---:|
| Correlation-aware, top Z | 204 | 67 | 1.02e-4 | 3.35e-5 |
| Correlation-aware, bottom Z | 97 | 73 | 4.85e-5 | 3.65e-5 |
| Standard, top Z | 402 | 98 | 2.01e-4 | 4.90e-5 |
| Standard, bottom Z | 145 | 99 | 7.25e-5 | 4.95e-5 |

At this link probability, the top-Z estimate is 67.2% lower with correlation-aware
decoding and 75.6% lower with standard decoding. The top and bottom rates in the
modified circuit are compatible within sampling uncertainty. Improvement is not
claimed at every individual low-noise point, where statistical uncertainty and
local noise matter. The confidence intervals are shown in the plots and CSV.

Both decoders passed all 14,783 raw single-fault mechanism checks at every one
of the ten link probabilities before sampling. All results are per full circuit,
so the longer duration and extra noisy operations are included under the stated
no-idle-noise model.

## What changed, and where

The inserted A round copies original ticks 38–46; the inserted B round copies
original ticks 29–37. They run before the original tick 38 A round. This retains
the alternating extraction schedule. The added rounds occur while the first
control/bus merge is active, before the control-side seams are measured out.

| Quantity | Before | After |
|---|---:|---:|
| First-merge syndrome rounds | 4 | 6 |
| Qubits | 199 | 199 |
| Circuit ticks | 110 | 128 |
| Measurements | 977 | 1,155 |
| Total CX gates | 2,816 | 3,410 |
| Inter-QPU CX gates | 56 | 70 |
| Distinct inter-QPU links | 7 | 7 |
| Detector checks | 802 | 976 |

The seam X readout moves from tick 54 to tick 72. The target-seam reset moves
from tick 56 to tick 74, the bus Z readout from tick 92 to tick 110, and final
data readout from tick 110 to tick 128. The boundary remains x < 8 versus x >= 8.
This is a temporal-protection change with additional noisy operations, not a
change to the inter-QPU partition or a reduction in assigned gate noise.

## Why this addresses the identified weakness

The original circuit admits two different pairs of physical link faults with
the same entire detector syndrome but opposite top-Z observable flips. This
makes perfect discrimination impossible from that syndrome alone.

For the longer circuit, all 543,375 possible pairs of physical link faults at
distinct crossing-CX locations were enumerated. Each of the 70 locations has
15 possible nonidentity Pauli errors. All other noise is absent in this test.
No identical detector syndromes have conflicting logical labels for either
observable. Both ordinary standard and correlation-aware PyMatching also decode
every one of these pairs correctly using the full-noise p_link=0.01,
p_local=0.0001 weights.

| Exact two-link-fault patterns misdecoded | Before | After |
|---|---:|---:|
| Standard: top Z | 320 | 0 |
| Correlation-aware: top Z | 134 | 0 |
| Standard: bottom Z | 0 | 0 |
| Correlation-aware: bottom Z | 0 | 0 |

The before counts cover 346,500 allowed pairs; the after counts cover 543,375.
These are exhaustive pattern counts, not Monte Carlo failure counts. The test
does not exclude failures involving local noise, mixed faults or three or more
link faults. The LER comparison includes those effects.

## Logical and detector validation

- Both target-Z relations pass signed flow checks without the initial logical
  data resets, so checking the relations is not limited to the zero-input case.
- All seven valid canonical Pauli relations of the original open circuit remain
  valid.
- All 16 computational-basis logical inputs were tested with 100 sampled
  histories each. The target outputs are C2 XOR T2 and C1 XOR T1 respectively;
  both control Z outputs are preserved.
- The only input-dependent detector is the upper-control consistency check,
  D975. This has the same role as the input-specific check in the original
  fixed-zero-input benchmark. No other logical input was made into a detector.
- There are 976 independent signed-valid detector checks. Together with four
  independent logical readout relations, they span the 980-dimensional
  deterministic measurement space.
- Fresh TQECD annotation contributes 943 independent rows within the validated
  detector span; 33 supplemental rows complete that same span. This local basis
  permits strict DEM decomposition without ignored failures or disjoint-error
  approximations. No decoder exceptions are used.

The candidate was selected using these flow, information and decoder checks,
before observing its Monte Carlo results.

## Matched Monte Carlo settings

- Same partition: x < 8 versus x >= 8.
- Link CX noise: DEPOLARIZE2(p_link), for p_link=0.001, 0.002, ..., 0.010.
- Local CX noise: DEPOLARIZE2(0.0001).
- Reset/H noise: DEPOLARIZE1(0.0001) after each operation.
- Measurement-result flip probability: 0.0001.
- No idle noise, matching the previous plot.
- Standard and correlation-aware PyMatching use identical sampled shots within
  each point. Both observables are measured on those same shots.
- 2,000,000 fresh shots per point; 20,000,000 after-repair shots in total.
- Before-repair counts come from the completed `../marked_observables_ler_x8/`
  experiment, also 2,000,000 shots per point. Before and after samples are
  independent.
- Rates are logical Z readout failures per complete circuit execution, without
  per-round normalization, postselection or discarded shots.
- Error bars are pointwise 95% Wilson binomial intervals.

The runner checks both decoders against every raw single-fault DEM mechanism at
each noise point before sampling. The source hash, checks, gate counts, versions
and fixed seeds are recorded in `run_manifest.json`.

## Files and reproduction

- `repaired_z.stim`: selected modified circuit with detectors and observables.
- `selected_candidate.json`: selected circuit hash, counts, scope and provenance.
- `results.csv`, `raw_results.json`: after-repair estimates and raw counts.
- `before_after_correlated.png`, `.pdf`, `.svg`: primary before/after comparison.
- `before_after_standard.png`, `.pdf`, `.svg`: standard-decoder comparison.
- `after_ler.png`, `.pdf`, `.svg`: top/bottom curves for the modified circuit in
  the same two-decoder layout as the original plot.
- `run_ler.py`, `noise_model.py`, `plot_comparison.py`: sampling and plotting.
- `extend_merge_rounds.py`: physical construction from the original circuit.
- `annotate_extended_merge.py`, `tqecd/rebase_plus2.py`: detector construction.
- `extended_channel_audit.json`, `extended_merge_plus2_input_scope.json`, and
  `extended_merge_plus2_schedule_changes.json`: logical and schedule checks.
- `diagnostics/`: exact physical link-fault pair tests and information audit.

From this folder:

```sh
python3 run_ler.py
python3 plot_comparison.py
```

The runner reuses matching completed checkpoints. Its fresh sample seed base is
202609106500; each point adds round(1000 * p_link). Batches have 100,000 shots.
Exact random sample streams can depend on Stim version, hardware and batching.
