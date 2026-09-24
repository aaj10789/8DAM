#!/usr/bin/env python3
"""Verify archived data, all-tick diagrams, and optional decoder models; no sampling."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import stim

from run_simulation import DATA_ROOT, contained_path, interval, load_dataset, validate_observables
from export_crumble import make_html, validated_crumble_url

ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rate_key(value):
    value = float(value)
    require(math.isfinite(value), "Nonfinite link-noise rate")
    key = round(value * 1000)
    require(1 <= key <= 10 and math.isclose(value, key/1000, rel_tol=0, abs_tol=1e-12), "Unexpected link-noise rate")
    return key


def validate_counts(meta, point):
    counts = point["counts"]
    n = counts["shots"]
    require(type(n) is int and n == 45_000_000 and counts["discards"] == 0, "Unexpected archived shot count")
    observed = counts["observables"]
    validate_observables(observed)
    require({(o["id"], o["label"]) for o in observed} == {(o["id"], o["label"]) for o in meta["observables"]}, "Count observable IDs/labels differ from metadata")
    for result in observed:
        k = result["errors"]
        require(type(k) is int and 0 <= k <= n, "Invalid observable count")
    if len(observed) == 2:
        a, b = (r["errors"] for r in observed)
        both, either = counts["both_errors"], counts["either_errors"]
        require(type(both) is int and type(either) is int, "Dual counts must be integers")
        require(max(0, a+b-n) <= both <= min(a, b), "Invalid dual intersection count")
        require(max(a, b) <= either <= n, "Invalid dual union count")
        require(either == a+b-both, "Dual union inconsistent")
    return n


def verify_results_csv(meta, rows):
    """Match every CSV row to archived counts before checking estimates/intervals."""
    points = {rate_key(point["p_link"]): point for point in meta["points"]}
    require(len(points) == len(meta["points"]), "Duplicate metadata rate")
    require(bool(rows), "Empty results CSV")
    single_format = "logical_errors" in rows[0]
    derived = bool(meta.get("derived_independent_pair_reference"))
    dual = len(meta["observables"]) == 2
    expected_series = {"single"} if single_format else ({"single_d3", "two_independent_d3"} if derived else {"dual_bottom", "dual_top", "dual_either"})
    if not single_format and any(row.get("series") == "dual_both" for row in rows):
        require(dual, "Intersection series requires two observables")
        expected_series.add("dual_both")
    seen = set()
    for row in rows:
        key = rate_key(row["p_link"])
        require(key in points, "CSV rate absent from metadata")
        point = points[key]
        counts = point["counts"]
        errors = {o["label"]: o["errors"] for o in counts["observables"]}
        if single_format:
            require(not dual and not derived and len(errors) == 1, "Single-format CSV does not match dataset type")
            series = "single"
            expected_k = next(iter(errors.values()))
            k, n = int(row["logical_errors"]), int(row["shots"])
            require(meta["confidence_interval_method"] == "clopper_pearson", "Single-CNOT CI method mismatch")
            for field in ("enable_correlations_at_compile", "enable_correlations_at_decode"):
                if field in row:
                    require(row[field].strip().lower() == "false", "CSV is not standard PyMatching")
            if "decoder" in row:
                require(row["decoder"] == "standard_pymatching", "Unexpected single-CNOT decoder")
            if "logical_basis" in row:
                basis = {"control_x": "X", "target_z": "Z"}.get(next(iter(errors)))
                require(basis is not None and row["logical_basis"] == basis, "CSV observable basis differs from metadata")
            if "discards" in row:
                require(int(row["discards"]) == counts["discards"], "CSV discard count differs from metadata")
            if "retained_shots" in row:
                require(int(row["retained_shots"]) == counts["shots"]-counts["discards"], "CSV retained shots differ from metadata")
            method, low_field, high_field = "clopper_pearson", "clopper_pearson_95_low", "clopper_pearson_95_high"
        else:
            series = row["series"]
            require(series in expected_series, f"Unexpected CSV series: {series}")
            require(meta["confidence_interval_method"] == "wilson", "Dual/reference CI method mismatch")
            require(row.get("decoder") == "standard", "Unexpected dual/reference decoder")
            k, n = int(row["source_errors"]), int(row["source_shots"])
            if derived:
                require(not dual and len(errors) == 1, "Independent-pair reference must have one source observable")
                expected_k = next(iter(errors.values()))
            else:
                require(dual, "Dual CSV requires two source observables")
                expected_k = {"dual_bottom": errors["bottom_target_z"], "dual_top": errors["top_target_z"],
                              "dual_either": counts["either_errors"], "dual_both": counts["both_errors"]}[series]
            method, low_field, high_field = "wilson", "ci95_low", "ci95_high"
        require((key, series) not in seen, "Duplicate CSV rate/series")
        seen.add((key, series))
        require(k == expected_k and n == counts["shots"], "CSV source counts differ from metadata")
        lo, hi = interval(k, n, method)
        rate = k/n
        if series == "two_independent_d3":
            rate, lo, hi = (2*v-v*v for v in (rate, lo, hi))
        require(math.isclose(float(row["ler"]), rate, rel_tol=1e-10, abs_tol=1e-16), "CSV LER mismatch")
        require(math.isclose(float(row[low_field]), lo, rel_tol=1e-9, abs_tol=1e-15), "CSV CI low mismatch")
        require(math.isclose(float(row[high_field]), hi, rel_tol=1e-9, abs_tol=1e-15), "CSV CI high mismatch")
    require(seen == {(key, series) for key in points for series in expected_series}, "Missing or extra CSV rate/series rows")


def verify_detector_slices(manifest, required_hashes):
    """Check one complete, valid SVG per circuit against its render manifest."""
    declared = {entry["id"]: entry for entry in manifest["datasets"]}
    release = manifest["detector_slices"]
    require(release["stim_version"] == "1.15.0", "Unexpected detector-slice Stim version")
    require(release["diagram_type"] == "detslice-with-ops-svg", "Unexpected detector-slice diagram type")
    galleries = release["galleries"]
    require(len(galleries) == len(declared) == 14, "Expected 14 detector-slice galleries")
    require(release["total_svgs"] == 14, "Expected 14 all-tick SVGs")
    seen_datasets = set()
    seen_svgs = set()
    gallery_files = {}
    for gallery in galleries:
        dataset_id = gallery["dataset"]
        require(dataset_id in declared and dataset_id not in seen_datasets,
                "Unknown or duplicate detector-slice dataset")
        seen_datasets.add(dataset_id)
        entry = declared[dataset_id]
        basis = entry["basis"]
        gallery_relative = f"{entry['path']}/detector_slices"
        manifest_relative = f"scripts/data/{entry['path']}/detector_slices/{basis}_manifest.json"
        svg_relative = f"{gallery_relative}/{basis}_all_ticks.svg"
        require(gallery["manifest"] == manifest_relative, "Unexpected detector-slice manifest path")
        require(gallery["svg"] == svg_relative and gallery["svg_count"] == 1,
                "Each detector-slice gallery must contain one all-tick SVG")
        gallery_path = contained_path(ROOT, gallery_relative)
        require(not any(gallery_path.glob("*_tick_*.svg")), "Obsolete selected-tick SVG found")
        manifest_path = contained_path(ROOT, manifest_relative)
        svg_path = contained_path(ROOT, svg_relative)
        readme_relative = f"{gallery_relative}/readme.md"
        require(contained_path(ROOT, readme_relative).is_file(), "Missing detector-slice README")
        require({path.name for path in gallery_path.glob("*.md")} == {"readme.md"},
                "Expected one shared readme.md per detector-slice folder")
        require(not any(gallery_path.glob("*.json")), "Render manifests must be in scripts/data")
        required_hashes.update((manifest_relative, svg_relative, readme_relative))
        require(svg_path not in seen_svgs, "Detector-slice datasets share an SVG file")
        seen_svgs.add(svg_path)
        gallery_files.setdefault(gallery_path, set()).add(svg_path)
        diagram = json.loads(manifest_path.read_text())
        require(diagram["schema"] == "8dam-detector-slices-v2", "Unexpected detector-slice manifest schema")
        require(diagram["dataset"] == dataset_id, "Detector-slice dataset ID mismatch")
        require(diagram["stim_version"] == release["stim_version"], "Detector-slice Stim version mismatch")
        require(diagram["diagram_type"] == release["diagram_type"], "Detector-slice diagram type mismatch")
        require(diagram["rows"] is None, "All-tick SVGs must use Stim's automatic row layout")
        require(diagram["filter_coords"] == [[]], "Detector-coordinate filter changed")
        require(diagram["native_stim_output_unmodified"] is True, "Detector-slice output must be native Stim SVG")
        require(diagram["sampling_performed"] is False, "Detector-slice rendering must not sample")
        source_relative = f"{entry['path']}/{basis}.stim"
        source_raw = contained_path(ROOT, source_relative).read_bytes()
        source_hash = hashlib.sha256(source_raw).hexdigest()
        require(diagram["source_circuit"] == {"repository_path": source_relative, "sha256": source_hash},
                "Detector-slice source circuit or hash mismatch")
        require(source_hash == entry["clean_sha256"], "Detector-slice source differs from release circuit")
        circuit = stim.Circuit(source_raw.decode("utf-8"))
        dimensions = {"detectors": circuit.num_detectors, "indexed_qubits": circuit.num_qubits,
                      "measurements": circuit.num_measurements, "observables": circuit.num_observables,
                      "ticks": circuit.num_ticks}
        require(diagram["circuit_dimensions"] == dimensions, "Detector-slice circuit dimensions differ")
        all_ticks = list(range(circuit.num_ticks + 1))
        require(all(type(tick) is int for tick in diagram["ticks"]) and diagram["ticks"] == all_ticks,
                "Detector-slice manifest must include every tick, starting at 0")
        require(gallery["ticks"] == all_ticks, "Release detector-slice tick range differs")
        require(diagram["tick_range"] == {"start": 0, "stop_exclusive": circuit.num_ticks + 1},
                "Detector-slice tick-range bounds differ")
        figures = diagram["figures"]
        require(len(figures) == 1, "Expected one all-tick figure per dataset")
        figure = figures[0]
        require(figure["path"] == svg_path.name and figure["ticks"] == all_ticks,
                "All-tick SVG filename or tick list differs")
        svg_raw = svg_path.read_bytes()
        require(len(svg_raw) == figure["bytes"], "All-tick SVG byte count differs")
        require(hashlib.sha256(svg_raw).hexdigest() == figure["sha256"], "All-tick SVG hash differs")
        panel_ticks = [int(tick) for tick in re.findall(rb'id="tick_border:(\d+):', svg_raw)]
        require(panel_ticks == all_ticks, "SVG panels do not cover every tick interval in order")
        del svg_raw
        # Clear completed elements to validate even large SVGs with bounded memory.
        first_element = True
        for event, element in ET.iterparse(svg_path, events=("start", "end")):
            if first_element:
                require(element.tag == "{http://www.w3.org/2000/svg}svg", "Diagram is not an SVG document")
                first_element = False
            if event == "end":
                element.clear()
        require(not first_element, "Empty all-tick SVG")
    require(seen_datasets == set(declared), "Missing detector-slice dataset")
    for gallery_path, expected_paths in gallery_files.items():
        require({path.resolve() for path in gallery_path.glob("*.svg")} == expected_paths,
                f"Unexpected SVG files in {gallery_path.relative_to(ROOT)}")
    return len(seen_svgs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", action="store_true", help="Also rebuild/check every decoding model")
    args = parser.parse_args()
    manifest_path = contained_path(DATA_ROOT, "release_manifest.json")
    manifest = json.loads(manifest_path.read_text())
    checked = 0
    listed = set()
    for line in contained_path(ROOT, "SHA256SUMS").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        path = contained_path(ROOT, relative)
        require(relative not in listed, f"Duplicate checksum entry: {relative}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"Changed file: {relative}")
        listed.add(relative)
        checked += 1
    models = 0
    point_count = 0
    required_hashes = {manifest_path.relative_to(ROOT).as_posix()}
    datasets_seen = set()
    metadata_seen = set()
    for entry in manifest["datasets"]:
        directory = contained_path(ROOT, entry["path"])
        support_directory = contained_path(DATA_ROOT, entry["path"])
        basis = entry["basis"]
        require(basis in {"control_x", "target_z"}, "Unexpected dataset basis")
        require(entry["id"] == f"{entry['path']}:{basis}", "Dataset ID differs from its path and basis")
        require(entry["id"] not in datasets_seen, "Duplicate dataset ID")
        datasets_seen.add(entry["id"])
        require(entry["metadata"] == f"{basis}_metadata.json", "Unexpected metadata filename")
        require(entry["results"] == f"{basis}_results.csv", "Unexpected results filename")
        meta_path = contained_path(support_directory, entry["metadata"])
        results_path = contained_path(directory, entry["results"])
        require(meta_path not in metadata_seen, "Duplicate dataset metadata file")
        metadata_seen.add(meta_path)
        meta = json.loads(meta_path.read_text())
        require(meta["id"] == entry["id"], "Metadata ID differs from release manifest")
        require(meta["results_file"] == entry["results"], "Metadata results file differs from release manifest")
        require(meta["clean_circuit"]["path"] == f"{basis}.stim", "Unexpected clean circuit filename")
        require(meta["crumble_file"] == f"{basis}_crumble.html", "Unexpected Crumble filename")
        validate_observables(meta["observables"])
        clean_path = contained_path(directory, meta["clean_circuit"]["path"])
        for path in (meta_path, results_path, clean_path):
            required_hashes.add(path.relative_to(ROOT).as_posix())
        raw = clean_path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == meta["clean_circuit"]["sha256"], "Clean circuit changed")
        visual_path = contained_path(directory, f"{basis}_crumble.stim")
        html_path = contained_path(directory, f"{basis}_crumble.html")
        url_path = contained_path(directory, f"{basis}_crumble_url.txt")
        export_path = contained_path(support_directory, f"provenance/{basis}_crumble_export.json")
        for path in (visual_path, html_path, url_path, export_path):
            required_hashes.add(path.relative_to(ROOT).as_posix())
        visual = visual_path.read_bytes()
        expected_html, export_meta = make_html(visual, filename=visual_path.name,
                                               title=entry["title"], reference_bytes=raw)
        require(html_path.read_text() == expected_html, "Crumble redirect differs from validated export")
        require(url_path.read_text().strip() == validated_crumble_url(visual.decode()), "Direct Crumble URL differs")
        saved_export = json.loads(export_path.read_text())
        require(all(saved_export.get(k) == v for k, v in export_meta.items() if k != "stim_version"), "Crumble export metadata differs")
        require(export_meta["polygon_annotations"] > 0, "Missing Crumble polygons")
        require(len(meta["points"]) == 10, "Rate grid length changed")
        require([rate_key(p["p_link"]) for p in meta["points"]] == list(range(1, 11)), "Rate grid changed")
        point_count += len(meta["points"])
        for point in meta["points"]:
            validate_counts(meta, point)
            for spec, source_directory in ((point["noisy_circuit"], directory),
                                           (point["dem"], support_directory)):
                if "path" in spec:
                    path = contained_path(source_directory, spec["path"])
                    required_hashes.add(path.relative_to(ROOT).as_posix())
                    require(hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"], "Point circuit/model hash mismatch")
            if args.models:
                load_dataset(meta_path, point["p_link"])
                models += 1
        with results_path.open(newline="") as f:
            verify_results_csv(meta, list(csv.DictReader(f)))
    all_tick_svgs = verify_detector_slices(manifest, required_hashes)
    require(required_hashes <= listed, f"Referenced files missing from SHA256SUMS: {sorted(required_hashes-listed)}")
    print(json.dumps({"status": "PASS", "files_hashed": checked, "datasets": len(manifest["datasets"]),
                      "circuit_rate_points": point_count,
                      "decoder_models_checked": models, "shots_drawn": 0,
                      "exact_polygon_crumble_exports_checked": len(datasets_seen),
                      "all_tick_svgs_checked": all_tick_svgs}, indent=2))


if __name__ == "__main__":
    main()
