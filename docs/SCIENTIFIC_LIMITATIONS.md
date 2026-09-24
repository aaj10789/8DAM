# Noise and decoding

The simulations use local gate, reset, and measurement noise at `1e-4` and
inter-QPU two-qubit depolarizing noise with `p_link` from `0.001` to `0.010`.
Idle noise, link-generation failures and latency, and leakage are not included.

Decoding uses standard PyMatching, with correlated matching disabled during
compilation and decoding. The simulation scripts use the archived detector
error models or verify regenerated models against the recorded checksums.
