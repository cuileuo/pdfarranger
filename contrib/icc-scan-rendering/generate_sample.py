"""Create original synthetic JPEG pages with a generated Display P3 ICC profile.

Requires Pillow and pikepdf. The profile is constructed from public chromaticity
coordinates using LittleCMS, rather than copied from a user's document.
Generated images, ICC profile, and PDFs are dedicated to the public domain (CC0).
The generator's code is GPL-3.0-or-later.
"""
import argparse
import ctypes as C
import ctypes.util
import io
from pathlib import Path
import random

import pikepdf
from PIL import Image, ImageDraw, ImageFont


def make_profile(library):
    cms = C.CDLL(library)
    class xyY(C.Structure):
        _fields_ = [("x", C.c_double), ("y", C.c_double), ("Y", C.c_double)]
    class Triple(C.Structure):
        _fields_ = [("red", xyY), ("green", xyY), ("blue", xyY)]
    def bind(name, result, *args):
        f = getattr(cms, name)
        f.restype, f.argtypes = result, args
        return f
    curve_new = bind("cmsBuildParametricToneCurve", C.c_void_p, C.c_void_p, C.c_int,
                     C.POINTER(C.c_double))
    curve_free = bind("cmsFreeToneCurve", None, C.c_void_p)
    profile_new = bind("cmsCreateRGBProfile", C.c_void_p, C.POINTER(xyY),
                       C.POINTER(Triple), C.POINTER(C.c_void_p))
    profile_save = bind("cmsSaveProfileToMem", C.c_int, C.c_void_p, C.c_void_p,
                        C.POINTER(C.c_uint32))
    profile_free = bind("cmsCloseProfile", C.c_int, C.c_void_p)
    mlu_new = bind("cmsMLUalloc", C.c_void_p, C.c_void_p, C.c_uint32)
    mlu_set = bind("cmsMLUsetASCII", C.c_int, C.c_void_p, C.c_char_p, C.c_char_p, C.c_char_p)
    mlu_free = bind("cmsMLUfree", None, C.c_void_p)
    write_tag = bind("cmsWriteTag", C.c_int, C.c_void_p, C.c_uint32, C.c_void_p)
    params = (C.c_double * 5)(2.4, 1 / 1.055, .055 / 1.055, 1 / 12.92, .04045)
    curve = curve_new(None, 4, params)
    assert curve
    white = xyY(.3127, .3290, 1)
    primaries = Triple(xyY(.680, .320, 1), xyY(.265, .690, 1), xyY(.150, .060, 1))
    profile = profile_new(C.byref(white), C.byref(primaries), (C.c_void_p * 3)(curve, curve, curve))
    try:
        assert profile
        for tag, text in ((b"desc", b"Synthetic Display P3 (sRGB transfer curve)"),
                          (b"cprt", b"CC0 - generated synthetic test profile")):
            mlu = mlu_new(None, 1)
            try:
                assert mlu_set(mlu, b"en", b"US", text)
                assert write_tag(profile, int.from_bytes(tag, "big"), mlu)
            finally:
                mlu_free(mlu)
        size = C.c_uint32()
        assert profile_save(profile, None, C.byref(size))
        data = C.create_string_buffer(size.value)
        assert profile_save(profile, data, C.byref(size))
        return bytes(data.raw[:size.value])
    finally:
        profile_free(profile)
        curve_free(curve)


def make_jpeg(number):
    size = (960, 1280)
    noise = Image.frombytes("RGB", size, random.Random(number).randbytes(size[0] * size[1] * 3))
    image = Image.blend(noise, Image.new("RGB", size, (190, 205, 175)), .65)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    draw.rectangle((30, 25, 930, 140), fill=(235, 235, 220))
    draw.text((50, 50), f"Synthetic scan - page {number + 1}", fill=(15, 15, 15), font=font)
    draw.text((50, 95), "Display P3 / ICC rendering benchmark", fill=(15, 15, 15), font=font)
    for i, color in enumerate(((230, 40, 40), (40, 230, 40), (40, 40, 230),
                                (220, 210, 30), (30, 220, 210), (210, 30, 220))):
        draw.rectangle((40 + i * 145, 170, 170 + i * 145, 280), fill=color)
    for row in range(12):
        draw.text((50, 350 + row * 65), f"Line {row + 1}: 0123456789  ABCDEFGHIJKLMNOP", font=font,
                  fill=(20, 30, 25))
    draw.text((50, 1190), "Original generated pattern; no private document content", font=font,
              fill=(15, 15, 15))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def write_pdf(destination, jpegs, profile):
    pdf = pikepdf.Pdf.new()
    colorspace = pikepdf.Name.DeviceRGB
    if profile is not None:
        icc = pdf.make_stream(profile)
        icc.N = 3
        icc.Alternate = pikepdf.Name.DeviceRGB
        colorspace = pikepdf.Array([pikepdf.Name.ICCBased, icc])
    for number, jpeg in enumerate(jpegs):
        page = pdf.add_blank_page(page_size=(720, 960))
        image = pdf.make_stream(jpeg)
        image.Type = pikepdf.Name.XObject
        image.Subtype = pikepdf.Name.Image
        image.Filter = pikepdf.Name.DCTDecode
        image.Width, image.Height, image.BitsPerComponent = 960, 1280, 8
        image.ColorSpace = colorspace
        page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
        page.Contents = pdf.make_stream(b"q\n720 0 0 960 0 0 cm\n/Im0 Do\nQ\n")
        page.Rotate = 270 if number == 2 else 0
    pdf.docinfo["/Title"] = "Synthetic scan rendering benchmark (CC0)"
    pdf.docinfo["/Creator"] = "generate_sample.py"
    pdf.save(destination, deterministic_id=True)
    pdf.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lcms-library", default=ctypes.util.find_library("lcms2"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if not args.lcms_library:
        parser.error("Pass --lcms-library pointing to the installed LittleCMS shared library")
    args.output.mkdir(parents=True, exist_ok=True)
    profile = make_profile(args.lcms_library)
    jpegs = [make_jpeg(i) for i in range(3)]
    write_pdf(args.output / "synthetic-display-p3.pdf", jpegs, profile)
    write_pdf(args.output / "synthetic-device-rgb-control.pdf", jpegs, None)
    (args.output / "synthetic-display-p3.icc").write_bytes(profile)


if __name__ == "__main__":
    main()
