#!/usr/bin/env python3
"""Render one all-ticks detector-slice SVG per archived, hash-verified Stim circuit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import stim

from run_simulation import DATA_ROOT, contained_path, resolve_dataset


ROOT = Path(__file__).resolve().parents[1]
STIM_VERSION = "1.15.0"
DIAGRAM_TYPE = "detslice-with-ops-svg"



def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path.name}")
    return value


def declared_datasets() -> dict[str, dict]:
    manifest = read_json(DATA_ROOT / "release_manifest.json")
    entries = manifest.get("datasets")
    if not isinstance(entries, list) or not entries:
        raise ValueError("release_manifest.json must contain a nonempty datasets list")
    result = {}
    for item in entries:
        dataset_id = item["id"]
        basis = item["basis"]
        if basis not in ("control_x", "target_z"):
            raise ValueError(f"Unsupported readout basis: {basis}")
        if dataset_id in result or dataset_id != f"{item['path']}:{basis}":
            raise ValueError("Duplicate dataset ID or ID/path/basis mismatch in release manifest")
        path = Path(item["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Dataset paths must be relative and remain within the repository")
        if item["metadata"] != f"{basis}_metadata.json":
            raise ValueError(f"Unexpected metadata filename for {dataset_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("clean_sha256", "")):
            raise ValueError(f"Invalid clean-circuit SHA-256 for {dataset_id}")
        result[dataset_id] = item
    return result


def load_circuit(entry: dict) -> tuple[stim.Circuit, dict, bytes]:
    directory = contained_path(ROOT, entry["path"])
    support_directory = contained_path(DATA_ROOT, entry["path"])
    metadata = read_json(contained_path(support_directory, entry["metadata"]))
    if metadata.get("id") != entry["id"]:
        raise ValueError(f"Metadata ID mismatch: {entry['id']}")
    source = metadata["clean_circuit"]
    if source.get("path") != f"{entry['basis']}.stim":
        raise ValueError("Expected the archived readout-specific Stim circuit input")
    raw = contained_path(directory, source["path"]).read_bytes()
    if not (sha256(raw) == source["sha256"] == entry["clean_sha256"]):
        raise ValueError(f"Circuit SHA-256 mismatch: {entry['id']}")
    circuit = stim.Circuit(raw.decode("utf-8"))
    actual = {
        "detectors": circuit.num_detectors,
        "indexed_qubits": circuit.num_qubits,
        "measurements": circuit.num_measurements,
        "observables": circuit.num_observables,
        "ticks": circuit.num_ticks,
    }
    if metadata["circuit_dimensions"] != actual:
        raise ValueError(f"Circuit dimensions disagree with metadata: {entry['id']}")
    return circuit, metadata, raw


def render_diagram(entry: dict) -> dict[str, bytes]:
    circuit, metadata, source_bytes = load_circuit(entry)
    basis = entry["basis"]
    source_path = Path(entry["path"]) / metadata["clean_circuit"]["path"]
    ticks = list(range(circuit.num_ticks + 1))
    name = f"{basis}_all_ticks.svg"
    raw = str(circuit.diagram(
        DIAGRAM_TYPE, tick=range(circuit.num_ticks + 1), filter_coords=[()]
    )).encode("utf-8")
    svg = ET.fromstring(raw)
    if svg.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Stim returned invalid SVG")
    if any(marker in raw for marker in (b"<script", b"foreignObject", b"<!ENTITY")):
        raise ValueError("Unexpected nonstatic content in native Stim SVG")
    frame_ticks = [int(t) for t in re.findall(rb'id="tick_border:(\d+):', raw)]
    if frame_ticks != ticks:
        raise ValueError("SVG does not contain every tick interval exactly once in order")
    if (ROOT / source_path).read_bytes() != source_bytes:
        raise ValueError("Source circuit changed during rendering")
    note = ("One SVG contains every operation interval, labeled Tick 0 through "
            f"Tick {circuit.num_ticks}, including operations before the first TICK and "
            "after the last TICK. Detector support is overlaid at the boundary after "
            "each interval. Stim arranges the frames in an automatic grid.")
    provenance = {
        "schema": "8dam-detector-slices-v2",
        "dataset": entry["id"],
        "source_circuit": {"repository_path": source_path.as_posix(), "sha256": sha256(source_bytes)},
        "circuit_dimensions": metadata["circuit_dimensions"],
        "stim_version": STIM_VERSION,
        "diagram_type": DIAGRAM_TYPE,
        "rows": None,
        "filter_coords": [[]],
        "included_slices": "all detector coordinates; no logical observable slices",
        "ticks": ticks,
        "tick_range": {"start": 0, "stop_exclusive": circuit.num_ticks + 1},
        "tick_convention": "Frame labels are operation intervals: Tick 0 before the first TICK, Tick N after the final TICK.",
        "coverage_note": note,
        "native_stim_output_unmodified": True,
        "sampling_performed": False,
        "figures": [{"path": name, "ticks": ticks, "bytes": len(raw), "sha256": sha256(raw)}],
    }
    artifacts = {name: raw}
    artifacts[f"{basis}_manifest.json"] = (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


def render_readme(diagrams: list[tuple[dict, dict]]) -> bytes:
    """Document all readout diagrams available in one configuration folder."""
    if not diagrams or len({entry["path"] for entry, _ in diagrams}) != 1:
        raise ValueError("A shared README requires diagrams from one configuration")
    diagrams = sorted(diagrams, key=lambda item: item[0]["basis"])
    configuration = Path(diagrams[0][0]["path"]).name
    lines = [f"# All-ticks detector slices: {configuration}", "",
             "Stim 1.15.0 diagrams show all detector coordinates and circuit operations from "
             "Tick 0 (before the first TICK) through Tick N (after the last). Logical observable "
             "slices are excluded. Pauli support is red for X, green for Y, and blue for Z.", "",
             "Open or download an SVG in a browser and zoom to inspect each frame.", "",
             "| Readout | Complete diagram | Tick intervals |",
             "| --- | --- | --- |"]
    for entry, diagram in diagrams:
        basis = entry["basis"]
        if diagram["dataset"] != entry["id"]:
            raise ValueError("README diagram metadata does not match the dataset")
        label = "Control X" if basis == "control_x" else "Target Z"
        last_tick = diagram["circuit_dimensions"]["ticks"]
        lines += [f"| {label} | [All ticks SVG]({basis}_all_ticks.svg) | 0–{last_tick} "
                  f"({last_tick + 1} frames) |"]
    return ("\n".join(lines).rstrip() + "\n").encode()


def check_destination(destination: Path, artifacts: dict[str, bytes], basis: str) -> None:
    if destination.is_symlink():
        raise ValueError("Output directories must not be symbolic links")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"Output is not a directory: {destination}")
        # Readout diagrams share one directory. Only this basis's artifacts
        # participate in the collision check; the other diagram is preserved.
        present = {p.name for p in destination.iterdir() if p.name.startswith(f"{basis}_")}
        if present - set(artifacts) or any(
            (destination / name).is_symlink() or not (destination / name).is_file()
            or (destination / name).read_bytes() != artifacts[name] for name in present
        ):
            raise ValueError(f"Output already contains different files; use a fresh --output directory: {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", help=(
        "Circuit file, e.g. single_lcnot/3-7-3/control_x.stim; "
        "dataset ID, e.g. single_lcnot/3-7-3:control_x; or central metadata file"))
    parser.add_argument("--all", action="store_true", help="Render all ticks for every packaged dataset")
    parser.add_argument("--output", type=Path, help=(
        "Output directory for SVG and readme.md; --all mirrors configuration paths. "
        "Render manifests are stored under OUTPUT/scripts/data/configuration/detector_slices"))
    args = parser.parse_args()
    if bool(args.dataset) == args.all:
        parser.error("Choose one circuit file, dataset ID, or central metadata file, or --all")
    if stim.__version__ != STIM_VERSION:
        parser.error(f"Stim {STIM_VERSION} is required; installed version is {stim.__version__}")
    try:
        declared = declared_datasets()
        dataset = resolve_dataset(args.dataset)[2]["id"] if args.dataset else None
        if dataset and dataset not in declared:
            raise ValueError("Dataset must be listed in scripts/data/release_manifest.json")
        selected = list(declared) if args.all else [dataset]
        rendered = []
        groups = {}
        for dataset_id in selected:
            entry = declared[dataset_id]
            artifacts = render_diagram(entry)
            metadata = json.loads(artifacts[f"{entry['basis']}_manifest.json"])
            frame_count = len(metadata["ticks"])
            destination = ROOT / entry["path"] / "detector_slices"
            support_destination = DATA_ROOT / entry["path"] / "detector_slices"
            if args.output is not None:
                destination = args.output / entry["path"] / "detector_slices" if args.all else args.output
                support_destination = args.output / "scripts/data" / entry["path"] / "detector_slices"
            public_artifacts = {name: raw for name, raw in artifacts.items() if name.endswith(".svg")}
            support_artifacts = {name: raw for name, raw in artifacts.items() if name.endswith(".json")}
            check_destination(destination, public_artifacts, entry["basis"])
            check_destination(support_destination, support_artifacts, entry["basis"])
            group = groups.setdefault(destination, {"path": entry["path"],
                                                    "support": support_destination, "diagrams": {}})
            group["diagrams"][entry["basis"]] = (entry, metadata)
            rendered.append((dataset_id, destination, support_destination,
                             public_artifacts, support_artifacts, frame_count))
        readmes = {}
        for destination, group in groups.items():
            # A single-readout rerun retains documentation for the peer diagram
            # when that diagram is already present in this shared folder.
            for peer in declared.values():
                if peer["path"] != group["path"] or peer["basis"] in group["diagrams"]:
                    continue
                peer_manifest = group["support"] / f"{peer['basis']}_manifest.json"
                peer_svg = destination / f"{peer['basis']}_all_ticks.svg"
                if peer_manifest.is_file() and peer_svg.is_file():
                    group["diagrams"][peer["basis"]] = (peer, read_json(peer_manifest))
            readme = render_readme(list(group["diagrams"].values()))
            readme_path = destination / "readme.md"
            if readme_path.is_symlink() or (readme_path.exists() and (
                not readme_path.is_file() or readme_path.read_bytes() != readme
            )):
                raise ValueError(f"README already differs; use a fresh --output directory: {destination}")
            readmes[destination] = readme
        for dataset_id, destination, support_destination, public_artifacts, support_artifacts, count in rendered:
            for target, artifacts in ((destination, public_artifacts), (support_destination, support_artifacts)):
                target.mkdir(parents=True, exist_ok=True)
                for name, raw in artifacts.items():
                    if not (target / name).exists():
                        (target / name).write_bytes(raw)
            print(f"{dataset_id}: one SVG containing {count} tick intervals")
        for destination, readme in readmes.items():
            readme_path = destination / "readme.md"
            if not readme_path.exists():
                readme_path.write_bytes(readme)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
