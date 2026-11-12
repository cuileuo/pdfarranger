# ICC scan rendering reproducer

Original generated patterns and ICC profile; no content from the private scan.
Generated images, profile and PDFs are CC0; scripts are GPL-3.0-or-later.
Measurements in results.json were collected on 2026-10-11. The updated-source
unit test results were collected on 2026-11-12.

Download both PDFs and benchmark.py into one directory. In a PDF Arranger
development environment providing GI/Poppler, Cairo, pikepdf and Pillow, run:

```sh
python benchmark.py --stock-only --directory . --repeats 3 --output fresh-results.json
```

This compares native rendering of the same JPEG streams and page instructions
with an ICCBased Display P3 color space versus DeviceRGB. Ignoring the profile
is diagnostic only, not a correct color conversion. After applying the proposed
patch and making the modified pdfarranger package importable, omit --stock-only
to also measure the color-managed JPEG preview.

To regenerate the synthetic files using LittleCMS:

```sh
python generate_sample.py --lcms-library /path/to/liblcms2.so --output .
```

On Windows, pass liblcms2-2.dll with its dependencies discoverable by the loader.
The sample uses Display P3 chromaticities, D65 white and the sRGB transfer curve.
The third page has Rotate=270. The DeviceRGB control has exactly the same JPEG
streams and drawing instructions. public-sample-check.json records their hashes
and image comparisons. Linux, pikepdf 6 and the full dogtail GUI suite have not
been run locally. See the associated draft PR for those validation limits.
