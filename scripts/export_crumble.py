#!/usr/bin/env python3
"""Export direct official Crumble links, retaining all detectors and polygons.

HTML automatically redirects; there is no custom viewer. Ordinary comments
are omitted from the URL; keep the input .stim file as the offline source.

  python scripts/export_crumble.py circuit_crumble.stim crumble.html \
      --reference circuit.stim --url-output crumble_url.txt
  python scripts/export_crumble.py --self-test
"""
from __future__ import annotations
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote
import stim

CRUMBLE_PREFIX = "https://algassert.com/crumble#circuit="
ALIASES = {"Q": "QUBIT_COORDS", "DT": "DETECTOR", "OI": "OBSERVABLE_INCLUDE"}
VISUAL_NAMES = {"POLYGON", "MARKX", "MARKY", "MARKZ"}
NAMES = sorted(set(stim.gate_data()) | set(ALIASES) | VISUAL_NAMES | {"REPEAT"}, key=len, reverse=True)


def compact_lines(source: str) -> list[str]:
    """Crumble's native compact grammar, with view-only pragmas retained."""
    out = []
    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("#!pragma "):
            line = line[len("#!pragma "):]
            name = re.split(r"[ (]", line, maxsplit=1)[0]
            if name not in VISUAL_NAMES:
                raise ValueError(f"Unsupported Crumble pragma: {name}")
        else:
            line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if re.match(r"[A-Z_]+\[", line):
            raise ValueError("Tagged instructions require a tag-aware codec")
        line = re.sub(r"\s+", " ", line)
        for short, full in ALIASES.items():
            if re.match(re.escape(full) + r"(?=[ (]|$)", line):
                line = short + line[len(full):]
                break
        out.append(line.replace(", ", ",").replace(") ", ")").replace(" ", "_"))
    return out


def restore_url_text(url: str) -> str:
    """Independently reverse compact URL syntax, restoring view-only comments."""
    if not url.startswith(CRUMBLE_PREFIX):
        raise ValueError("Not an official Crumble circuit URL")
    out = []
    for token in unquote(url[len(CRUMBLE_PREFIX):]).split(";"):
        if not token.strip("_"):
            continue
        if token.rstrip("_") == "}":
            out.append("}")
            continue
        for name in NAMES:
            if token == name or token.startswith(name + "(") or token.startswith(name + "_"):
                tail = token[len(name):].replace("_", " ")
                prefix = "#!pragma " if name in VISUAL_NAMES else ""
                out.append(prefix + re.sub(r"\)(?=\S)", ") ", ALIASES.get(name, name) + tail))
                break
        else:
            raise ValueError(f"Unsupported compact token: {token[:80]!r}")
    return "\n".join(out) + "\n"


def restore_native_crumble_url(url: str) -> stim.Circuit:
    return stim.Circuit(restore_url_text(url))


def annotation_signature(source: str) -> list[tuple[int, str]]:
    tick = 0
    signature = []
    for token in compact_lines(source):
        if token == "TICK":
            tick += 1
        if token.split("(", 1)[0] in VISUAL_NAMES:
            signature.append((tick, token))
    return signature


def validated_crumble_url(source: str | stim.Circuit) -> str:
    text = str(source)
    # Native Crumble URLs use POLYGON without the '#!pragma' prefix.
    url = CRUMBLE_PREFIX + quote(";".join(compact_lines(text)), safe=";(),_*{}[]^!:-.")
    restored = restore_url_text(url)
    if stim.Circuit(restored) != stim.Circuit(text):
        raise ValueError("URL changed the parsed Stim circuit")
    if annotation_signature(restored) != annotation_signature(text):
        raise ValueError("URL changed visualization annotations or their ticks")
    return url


class _RedirectAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.scripts = [], []
        self.in_script, self.current, self.iframe = False, "", False
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href"))
        if tag == "iframe":
            self.iframe = True
        if tag == "script":
            self.in_script, self.current = True, ""
    def handle_data(self, data):
        if self.in_script:
            self.current += data
    def handle_endtag(self, tag):
        if tag == "script":
            self.scripts.append(self.current)
            self.in_script = False


def make_html(source_bytes: bytes, *, filename: str, title: str,
              reference_bytes: bytes | None = None) -> tuple[str, dict]:
    source = source_bytes.decode("utf-8")
    circuit = stim.Circuit(source)
    if reference_bytes is not None and circuit != stim.Circuit(reference_bytes.decode("utf-8")):
        raise ValueError("Visualization circuit differs from the simulation reference")
    url = validated_crumble_url(source)
    meta = {
        "source_filename": filename,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes), "stim_version": stim.__version__,
        "qubits": circuit.num_qubits, "measurements": circuit.num_measurements,
        "detectors": circuit.num_detectors, "observables": circuit.num_observables,
        "ticks": circuit.num_ticks,
        "polygon_annotations": sum(t.startswith("POLYGON(") for _, t in annotation_signature(source)),
        "crumble_url_characters": len(url),
        "crumble_url_sha256": hashlib.sha256(url.encode()).hexdigest(),
        "all_detectors_included": True, "exact_circuit_url_roundtrip": True,
        "annotation_tick_roundtrip": True, "viewer_requires_internet": True,
        "html_behavior": "automatic redirect to official Crumble; no custom viewer",
    }
    if reference_bytes is not None:
        meta["reference_sha256"] = hashlib.sha256(reference_bytes).hexdigest()
        meta["exact_simulation_circuit_equality"] = True
    url_json = json.dumps(url, ensure_ascii=True).replace("<", "\\u003c")
    document = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="referrer" content="no-referrer">
  <title>{html.escape(title)} — Crumble</title>
  <script>window.location.replace({url_json});</script>
</head>
<body>
  <p><a href="{html.escape(url, quote=True)}">Open this circuit directly in Crumble</a></p>
</body>
</html>
'''
    audit = _RedirectAudit()
    audit.feed(document)
    if audit.links != [url] or audit.scripts != [f"window.location.replace({url_json});"] or audit.iframe:
        raise ValueError("Redirect HTML failed validation")
    return document, meta


def self_test():
    source = (
        "# <&> </script>\r\nQUBIT_COORDS(1, 2) 0\r\nQUBIT_COORDS(2, 2) 1\r\n"
        "#!pragma POLYGON(1, 0, 0, 0.25) 0 1\r\nR 0 1\r\n"
        "REPEAT 2 {\r\nX_ERROR(0.01) 0\r\nM 0\r\n"
        "DETECTOR(1, 2, 0) rec[-1]\r\nSHIFT_COORDS(0, 0, 1)\r\nTICK\r\n}\r\n"
        "#!pragma MARKZ(0) 0\r\nOBSERVABLE_INCLUDE(0) rec[-1]\r\n"
    ).encode()
    document, meta = make_html(source, filename="test.stim", title='Test <&>',
                               reference_bytes=str(stim.Circuit(source.decode())).encode())
    assert meta["polygon_annotations"] == 1 and meta["detectors"] == 2
    assert meta["exact_simulation_circuit_equality"] and "<iframe" not in document
    for text in ("", "RX 0 1\nMPP X0*X1\nDETECTOR rec[-1]", "R 0\nM 0\nCX rec[-1] 0"):
        assert restore_native_crumble_url(validated_crumble_url(text)) == stim.Circuit(text)
    try:
        make_html(b"R 0", filename="bad.stim", title="bad", reference_bytes=b"RX 0")
    except ValueError:
        pass
    else:
        raise AssertionError("Changed circuit accepted")
    print("PASS: exact Stim roundtrips, polygon/marker ticks, REPEAT, underscored names, direct redirect, reference guard")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", nargs="?", type=Path)
    p.add_argument("output", nargs="?", type=Path)
    p.add_argument("--title")
    p.add_argument("--reference", type=Path, help="Require exact equality to simulation circuit")
    p.add_argument("--url-output", type=Path, help="Also save the direct official URL")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    if a.input is None or a.output is None:
        p.error("input and output required")
    protected = {a.input.resolve()} | ({a.reference.resolve()} if a.reference else set())
    outputs = [a.output] + ([a.url_output] if a.url_output else [])
    if any(path.resolve() in protected for path in outputs) or len({path.resolve() for path in outputs}) != len(outputs):
        p.error("Outputs must be distinct from each other and all input circuits")
    source = a.input.read_bytes()
    document, meta = make_html(source, filename=a.input.name, title=a.title or a.input.stem,
                              reference_bytes=a.reference.read_bytes() if a.reference else None)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(document, encoding="utf-8")
    if a.url_output:
        a.url_output.parent.mkdir(parents=True, exist_ok=True)
        a.url_output.write_text(validated_crumble_url(source.decode()) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
