# SPDX-License-Identifier: GPL-3.0-or-later
"""Time stock Poppler and the proposed preview path on public synthetic PDFs.

Run in a PDF Arranger development environment (GTK/Poppler/Pillow/pikepdf).
No private files or image data are included in the JSON result.
"""
import argparse
import gc
import json
from pathlib import Path
import platform
import sys
import time

import gi
gi.require_version("Poppler", "0.18")
gi.require_version("Gtk", "3.0")
from gi.repository import Poppler, Gtk
import cairo
import pikepdf
import PIL
try:
    from pdfarranger.scanpreview import ScanPreview
except ImportError:
    ScanPreview = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--images", type=Path)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--stock-only", action="store_true",
                        help="Compare just the two native Poppler paths without applying the draft patch")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    folder = args.directory.resolve()
    files = [folder / "synthetic-display-p3.pdf", folder / "synthetic-device-rgb-control.pdf"]
    documents = [Poppler.Document.new_from_file(p.as_uri(), None) for p in files]
    preview = None if args.stock_only or ScanPreview is None else ScanPreview(str(files[0]))
    report = {"environment": {"python": sys.version, "platform": platform.platform(),
                              "poppler": Poppler.get_version(), "pikepdf": pikepdf.__version__,
                              "pillow": PIL.__version__, "cairo": cairo.cairo_version_string(),
                              "gtk": f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"},
              "zoom": .25, "prototype_available": preview is not None, "trials": []}
    if args.images:
        args.images.mkdir(parents=True, exist_ok=True)
    for trial in range(args.repeats):
        for number in range(documents[0].get_n_pages()):
            row = {"trial": trial + 1, "page": number + 1}
            backends = ["poppler_icc", "poppler_rgb_control"]
            if preview is not None:
                backends.append("jpeg_preview")
            for backend in backends:
                doc = documents[1] if backend == "poppler_rgb_control" else documents[0]
                page = doc.get_page(number)
                w, h = page.get_size()
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, round(w / 4)), max(1, round(h / 4)))
                cr = cairo.Context(surface)
                cr.scale(.25, .25)
                start = time.perf_counter()
                if backend == "jpeg_preview":
                    assert preview.paint(cr, number), f"Page {number + 1} did not use the proposed fast path"
                else:
                    page.render(cr)
                row[backend + "_seconds"] = time.perf_counter() - start
                if trial == 0 and args.images and backend != "poppler_rgb_control":
                    surface.write_to_png(str(args.images / f"{backend}-{number+1}.png"))
            report["trials"].append(row)
            print(json.dumps(row), flush=True)
            if args.output:
                args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if preview is not None:
        preview.pdf.close()
        preview.pdf = None
    documents.clear()
    page = None
    gc.collect()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
