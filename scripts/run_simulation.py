#!/usr/bin/env python3
"""Sample an archived noisy circuit without regenerating detectors or noise.

This creates a NEW run. It never extends or modifies paper counts.
Fresh seeds are needed for independent samples: reusing a seed can duplicate a
previous sample stream and must not be pooled as additional independent shots.
Use --check-only to verify the circuit and decoder model without drawing shots.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import uuid

import numpy as np
import pymatching
import scipy
from scipy.stats import beta
import stim

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "scripts" / "data"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalized(obj):
    return (str(obj).rstrip() + "\n").encode()


def contained_path(directory, relative):
    """Resolve an archived relative path without permitting traversal/symlink escapes."""
    directory = Path(directory).resolve()
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"Expected a nonempty relative archive path: {relative!r}")
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory):
        raise ValueError(f"Archive path escapes its directory: {relative!r}")
    return path


def resolve_dataset(dataset):
    """Resolve a published circuit, dataset ID, or support metadata file.

    The release manifest is authoritative: public circuit paths come from each
    registered metadata file, while simulation support stays in scripts/data.
    Relative paths may be repository-relative or relative to the current working
    directory; ambiguous aliases are rejected.
    """
    requested = str(dataset)
    path = Path(requested).expanduser()
    candidates = {path.resolve()}
    if not path.is_absolute():
        candidates.add((ROOT / path).resolve())
    manifest = json.loads((DATA_ROOT / "release_manifest.json").read_text())
    matches = []
    for entry in manifest["datasets"]:
        public_dir = contained_path(ROOT, entry["path"])
        support_dir = contained_path(DATA_ROOT, entry["path"])
        metadata_path = contained_path(support_dir, entry["metadata"])
        meta = json.loads(metadata_path.read_text())
        if meta["id"] != entry["id"]:
            raise ValueError(f"Metadata ID differs from the release manifest: {entry['id']}")
        circuit_path = contained_path(public_dir, meta["clean_circuit"]["path"])
        if requested == entry["id"] or candidates.intersection({circuit_path, metadata_path}):
            matches.append((public_dir, support_dir, entry, meta))
    if len(matches) != 1:
        raise ValueError(
            "Choose one registered circuit path or dataset ID, e.g. "
            "single_lcnot/3-7-3/control_x.stim or single_lcnot/3-7-3:control_x"
        )
    return matches[0]


def validate_observables(observables):
    if not isinstance(observables, list) or not observables:
        raise ValueError("Expected at least one observable specification")
    ids = [o.get("id") for o in observables]
    labels = [o.get("label") for o in observables]
    if any(type(i) is not int for i in ids) or sorted(ids) != list(range(len(ids))):
        raise ValueError("Observable IDs must be unique and exactly 0 through N-1")
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ValueError("Observable labels must be nonempty strings")
    if len(set(labels)) != len(labels):
        raise ValueError("Observable labels must be unique")


def interval(k, n, method):
    if not isinstance(k, (int, np.integer)) or not isinstance(n, (int, np.integer)) or n <= 0 or not 0 <= k <= n:
        raise ValueError("Intervals require integer counts satisfying 0 <= k <= n and n > 0")
    if method == "clopper_pearson":
        return [0.0 if k == 0 else float(beta.ppf(.025, k, n-k+1)),
                1.0 if k == n else float(beta.ppf(.975, k+1, n-k))]
    if method == "wilson":
        z = 1.959963984540054
        p = k / n
        scale = 1 + z*z/n
        center = (p + z*z/(2*n))/scale
        radius = z*((p*(1-p)/n + z*z/(4*n*n))**.5)/scale
        return [0.0 if k == 0 else max(0.0, center-radius),
                1.0 if k == n else min(1.0, center+radius)]
    raise ValueError(f"Unknown interval method: {method}")


def load_dataset(dataset, p_link):
    """Load one registered observable dataset and its archived decoder model."""
    directory, support_dir, _, meta = resolve_dataset(dataset)
    validate_observables(meta["observables"])
    if not math.isfinite(p_link):
        raise ValueError("p_link must be finite")
    points = [p for p in meta["points"] if abs(p["p_link"]-p_link) < 1e-12]
    if len(points) != 1:
        raise ValueError("Choose an archived p_link value (0.001 through 0.010)")
    point = points[0]
    spec = point["noisy_circuit"]
    path = contained_path(directory, spec["path"])
    raw = path.read_bytes()
    if digest(raw) != spec["sha256"]:
        raise ValueError("Noisy circuit checksum mismatch")
    circuit = stim.Circuit(raw.decode())
    dem_spec = point["dem"]
    if "path" in dem_spec:
        dem_path = contained_path(support_dir, dem_spec["path"])
        dem_raw = dem_path.read_bytes()
        if digest(dem_raw) != dem_spec["sha256"]:
            raise ValueError("Archived DEM checksum mismatch")
        dem = stim.DetectorErrorModel(dem_raw.decode())
    else:
        dem = circuit.detector_error_model(**dem_spec["options"])
        if digest(normalized(dem)) != dem_spec["sha256"]:
            raise ValueError("Rebuilt DEM differs from the archived model; use pinned dependencies")
    if circuit.num_observables != len(meta["observables"]):
        raise ValueError("Unexpected observable count")
    if dem.num_detectors != circuit.num_detectors or dem.num_observables != circuit.num_observables:
        raise ValueError("Archived DEM dimensions differ from the circuit detector/observable basis")
    matching = pymatching.Matching.from_detector_error_model(dem, enable_correlations=False)
    if matching.num_detectors != circuit.num_detectors or matching.num_fault_ids != circuit.num_observables:
        raise ValueError("Decoder dimensions differ from the circuit detector/observable basis")
    if meta.get("derived_independent_pair_reference") and circuit.num_observables != 1:
        raise ValueError("Independent-pair reference requires exactly one single-CNOT observable")
    return meta, point, circuit, matching


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset",
                        help="Circuit path or dataset ID, e.g. single_lcnot/3-7-3/control_x.stim")
    parser.add_argument("--p-link", type=float, required=True)
    parser.add_argument("--shots", type=int, help="New shots; required unless --check-only")
    parser.add_argument("--batch-size", type=int, default=10000)
    parser.add_argument("--seed", type=int, help="Optional reproducibility seed; defaults to fresh entropy. Reused seeds can duplicate shots and must not be pooled as independent samples.")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.batch_size <= 0 or (not args.check_only and (args.shots is None or args.shots <= 0)):
        parser.error("Positive --shots and --batch-size are required for sampling")
    if args.seed is not None and not 0 <= args.seed < 2**64:
        parser.error("--seed must be an integer in [0, 2**64)")
    meta, point, circuit, matching = load_dataset(args.dataset, args.p_link)
    if args.check_only:
        print(json.dumps({"status": "PASS", "dataset": meta["id"], "shots_drawn": 0,
                          "detectors": circuit.num_detectors, "observables": circuit.num_observables}))
        return
    seed = args.seed if args.seed is not None else int.from_bytes(__import__("os").urandom(8), "little")
    sampler = circuit.compile_detector_sampler(seed=seed)
    totals = np.zeros(circuit.num_observables, dtype=np.int64)
    union = joint = done = 0
    while done < args.shots:
        n = min(args.batch_size, args.shots-done)
        det, obs = sampler.sample(n, separate_observables=True)
        predicted = matching.decode_batch(det, enable_correlations=False)
        if predicted.shape != obs.shape:
            raise ValueError("Decoder predictions and sampled observables have different shapes")
        failed = predicted != obs
        totals += failed.sum(axis=0)
        union += int(np.any(failed, axis=1).sum())
        joint += int(np.all(failed, axis=1).sum())
        done += n
    method = meta["confidence_interval_method"]
    def result(k):
        return {"errors": int(k), "shots": done, "ler": int(k)/done,
                "ci95": interval(int(k), done, method)}
    output = {"dataset": meta["id"], "scope": meta["scope"], "p_link": args.p_link,
              "shots": done, "discards": 0, "seed": seed, "seed_was_explicit": args.seed is not None, "batch_size": args.batch_size,
              "decoder": "standard_pymatching", "enable_correlations": False,
              "confidence_interval_method": method,
              "noisy_circuit_sha256": point["noisy_circuit"]["sha256"],
              "dem_sha256": point["dem"]["sha256"],
              "observables": {o["label"]: result(totals[o["id"]]) for o in meta["observables"]},
              "either_observable_fails": result(union), "all_observables_fail": result(joint),
              "runtime": {"python": platform.python_version(), "stim": stim.__version__,
                          "pymatching": pymatching.__version__, "numpy": np.__version__,
                          "scipy": scipy.__version__},
              "note": "New run; not pooled with or substituted for published results. Independent statistics require a fresh seed; repeating a seed may duplicate samples and must not be counted as additional independent shots."}
    if meta.get("derived_independent_pair_reference"):
        q = int(totals[0])/done
        lo, hi = interval(int(totals[0]), done, method)
        output["derived_independent_pair"] = {"ler": 2*q-q*q,
                                               "ci95": [2*lo-lo*lo, 2*hi-hi*hi],
                                               "direct_pair_shots": 0}
    run_root = ROOT / "new_runs"
    run_root.mkdir(exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + ".json"
    destination = run_root / name
    with destination.open("x") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    print(destination)


if __name__ == "__main__":
    main()
