"""Render the ChArUco board defined by ``CharucoBoardSpec`` into a printable file.

The board must be printed at *exactly* the physical size the spec declares, or
every recovered length is biased. Two things make that dependable:

* The board is emitted as an **SVG sized in millimetres** (``width="210mm"``),
  so a browser/print dialog at 100% (no "fit to page") reproduces true size on
  A4 with no raster-DPI guesswork.
* A vector **100 mm reference bar** is drawn beside the board. After printing,
  the operator measures it with a ruler and feeds the value to
  ``calibrate_device`` (``--measured-bar-mm``); ``print_verify`` turns any
  residual printer scaling into a correction factor.

A companion PNG (raster only, no bar) can be written for on-screen preview,
and a print-ready **A4 PDF** carrying the same true-size board and reference
bar. The PDF is the most dependable print target -- viewers print it at true
physical size when "Actual size" / 100% (not "Fit") is selected.

Pure ``cv2`` + ``numpy`` + stdlib ``zlib`` -- no PDF/image dependencies added.
The PDF is emitted by hand: a single A4 page with the board raster embedded as
a ``FlateDecode`` image XObject sized in points, plus the vector bar and caption.
"""

import argparse
import base64
import zlib
from pathlib import Path

import cv2
import numpy as np

from app.models.calibration import CharucoBoardSpec
from app.services.calibration.board import build_charuco_board

# A4 portrait, millimetres. The board (175 x 250 mm at the default spec) fits
# with room below for the reference bar and caption.
A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
REFERENCE_BAR_MM = 100.0
_PX_PER_MM = 10  # raster density for the embedded board image (~254 DPI)
_MM_TO_PT = 72.0 / 25.4  # PDF user space is points (1/72 inch)


def board_size_mm(spec: CharucoBoardSpec) -> tuple[float, float]:
    """Physical (width, height) of the board at nominal (100%) print scale."""
    return spec.squares_x * spec.square_length_mm, spec.squares_y * spec.square_length_mm


def render_board_image(spec: CharucoBoardSpec, px_per_mm: int = _PX_PER_MM, margin_mm: float = 5.0) -> np.ndarray:
    """Raster of the board at a metric-proportional pixel size.

    ``margin_mm`` adds a white quiet zone around the markers, which the ArUco
    detector needs to segment the outer markers reliably.
    """
    width_mm, height_mm = board_size_mm(spec)
    width_px = round(width_mm * px_per_mm)
    height_px = round(height_mm * px_per_mm)
    board = build_charuco_board(spec, print_scale_factor=1.0)
    return board.generateImage((width_px, height_px), marginSize=round(margin_mm * px_per_mm), borderBits=1)


def _png_data_uri(image: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("failed to PNG-encode the board raster")
    return "data:image/png;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def build_board_svg(spec: CharucoBoardSpec, image: np.ndarray) -> str:
    """A4 SVG (mm units) placing the board raster at true size plus the bar."""
    board_w, board_h = board_size_mm(spec)
    # Quiet-zone margin is baked into the raster; grow the on-page footprint so
    # the printed squares keep their nominal mm size.
    raster_h, raster_w = image.shape[:2]
    page_w_of_raster = board_w * (raster_w / (board_w * _PX_PER_MM))
    page_h_of_raster = board_h * (raster_h / (board_h * _PX_PER_MM))

    x = (A4_WIDTH_MM - page_w_of_raster) / 2
    y = 12.0
    bar_y = y + page_h_of_raster + 18.0
    bar_x = (A4_WIDTH_MM - REFERENCE_BAR_MM) / 2
    data_uri = _png_data_uri(image)
    caption = (
        f"{spec.version} | {spec.dictionary} | {spec.squares_x}x{spec.squares_y} "
        f"| square {spec.square_length_mm:g}mm marker {spec.marker_length_mm:g}mm"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{A4_WIDTH_MM}mm" height="{A4_HEIGHT_MM}mm"
     viewBox="0 0 {A4_WIDTH_MM} {A4_HEIGHT_MM}">
  <rect x="0" y="0" width="{A4_WIDTH_MM}" height="{A4_HEIGHT_MM}" fill="white"/>
  <image x="{x:.3f}" y="{y:.3f}" width="{page_w_of_raster:.3f}" height="{page_h_of_raster:.3f}"
         href="{data_uri}" style="image-rendering:pixelated"/>
  <g stroke="black" stroke-width="0.4" fill="black">
    <line x1="{bar_x:.3f}" y1="{bar_y:.3f}" x2="{bar_x + REFERENCE_BAR_MM:.3f}" y2="{bar_y:.3f}"/>
    <line x1="{bar_x:.3f}" y1="{bar_y - 2:.3f}" x2="{bar_x:.3f}" y2="{bar_y + 2:.3f}"/>
    <line x1="{bar_x + REFERENCE_BAR_MM:.3f}" y1="{bar_y - 2:.3f}" x2="{bar_x + REFERENCE_BAR_MM:.3f}" y2="{bar_y + 2:.3f}"/>
  </g>
  <text x="{A4_WIDTH_MM / 2:.3f}" y="{bar_y + 8:.3f}" font-family="sans-serif" font-size="4"
        text-anchor="middle" fill="black">100 mm reference -- print at 100% (no fit-to-page), then measure this line</text>
  <text x="{A4_WIDTH_MM / 2:.3f}" y="{bar_y + 15:.3f}" font-family="sans-serif" font-size="3"
        text-anchor="middle" fill="black">{caption}</text>
</svg>
"""


def _mm(value: float) -> float:
    """mm -> PDF points."""
    return value * _MM_TO_PT


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_board_pdf(spec: CharucoBoardSpec, image: np.ndarray) -> bytes:
    """A single-page A4 PDF placing the board raster at true size plus the bar.

    Hand-built so no PDF dependency is pulled in. The board raster is embedded as
    a grayscale ``FlateDecode`` image XObject and scaled to its nominal mm size,
    so "Actual size" / 100% printing reproduces true physical dimensions. The
    reference bar, ticks and caption are vector so they stay crisp.
    """
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = np.ascontiguousarray(gray, dtype=np.uint8)
    raster_h, raster_w = gray.shape[:2]
    board_w, board_h = board_size_mm(spec)
    # The raster carries a quiet-zone margin; grow the on-page footprint so the
    # printed squares keep their nominal mm size (mirrors build_board_svg).
    page_w = board_w * (raster_w / (board_w * _PX_PER_MM))
    page_h = board_h * (raster_h / (board_h * _PX_PER_MM))

    # Layout in mm from the top edge (matches the SVG), converted to PDF's
    # bottom-left origin below.
    x_mm = (A4_WIDTH_MM - page_w) / 2
    y_mm = 12.0
    bar_y_mm = y_mm + page_h + 18.0
    bar_x_mm = (A4_WIDTH_MM - REFERENCE_BAR_MM) / 2
    caption = (
        f"{spec.version} | {spec.dictionary} | {spec.squares_x}x{spec.squares_y} "
        f"| square {spec.square_length_mm:g}mm marker {spec.marker_length_mm:g}mm"
    )
    note = "100 mm reference -- print at 100% / Actual size (not Fit), then measure this line"

    def top_to_pdf_y(mm_from_top: float) -> float:
        return _mm(A4_HEIGHT_MM - mm_from_top)

    img_x, img_y = _mm(x_mm), top_to_pdf_y(y_mm + page_h)  # PDF y is the bottom edge
    img_w, img_h = _mm(page_w), _mm(page_h)
    bar_y = top_to_pdf_y(bar_y_mm)
    bar_x0, bar_x1 = _mm(bar_x_mm), _mm(bar_x_mm + REFERENCE_BAR_MM)
    cx = _mm(A4_WIDTH_MM / 2)

    def centered(text: str, size: float, mm_from_top: float) -> str:
        # Helvetica averages ~0.5 em per glyph; good enough to center a caption.
        width = len(text) * size * 0.5
        return f"BT /F1 {size:.2f} Tf {cx - width / 2:.2f} {top_to_pdf_y(mm_from_top):.2f} Td ({_pdf_escape(text)}) Tj ET"

    content = "\n".join(
        [
            f"q {img_w:.3f} 0 0 {img_h:.3f} {img_x:.3f} {img_y:.3f} cm /Im0 Do Q",
            "0 G 1.13 w 1 J",  # ~0.4mm stroke, round caps
            f"{bar_x0:.2f} {bar_y:.2f} m {bar_x1:.2f} {bar_y:.2f} l S",
            f"{bar_x0:.2f} {bar_y - _mm(2):.2f} m {bar_x0:.2f} {bar_y + _mm(2):.2f} l S",
            f"{bar_x1:.2f} {bar_y - _mm(2):.2f} m {bar_x1:.2f} {bar_y + _mm(2):.2f} l S",
            "0 g",
            centered(note, 9.0, bar_y_mm + 8),
            centered(caption, 7.5, bar_y_mm + 15),
        ]
    )
    content_bytes = content.encode("ascii")
    image_stream = zlib.compress(gray.tobytes(), 9)

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_mm(A4_WIDTH_MM):.3f} {_mm(A4_HEIGHT_MM):.3f}] "
            f"/Resources << /XObject << /Im0 5 0 R >> /Font << /F1 6 0 R >> >> /Contents 4 0 R >>"
        ).encode("ascii"),
        (
            f"<< /Length {len(content_bytes)} >>\nstream\n".encode("ascii")
            + content_bytes
            + b"\nendstream"
        ),
        (
            f"<< /Type /XObject /Subtype /Image /Width {raster_w} /Height {raster_h} "
            f"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode "
            f"/Length {len(image_stream)} >>\nstream\n".encode("ascii")
            + image_stream
            + b"\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the printable ChArUco calibration board.")
    parser.add_argument("--out", type=Path, default=Path("board_a4.svg"), help="output SVG path (mm-sized, for printing)")
    parser.add_argument("--pdf", type=Path, default=None, help="optional print-ready A4 PDF path (true-size, with bar)")
    parser.add_argument("--png", type=Path, default=None, help="optional PNG preview path (raster only)")
    parser.add_argument("--px-per-mm", type=int, default=_PX_PER_MM, help="raster density of the embedded board image")
    args = parser.parse_args(argv)

    spec = CharucoBoardSpec()
    image = render_board_image(spec, px_per_mm=args.px_per_mm)
    args.out.write_text(build_board_svg(spec, image), encoding="utf-8")
    width_mm, height_mm = board_size_mm(spec)
    print(f"wrote {args.out} -- board {width_mm:g}x{height_mm:g} mm on A4; print at 100%")
    if args.pdf is not None:
        args.pdf.write_bytes(build_board_pdf(spec, image))
        print(f"wrote {args.pdf} -- A4 PDF; print at 100% / Actual size (not Fit)")
    if args.png is not None:
        cv2.imwrite(str(args.png), image)
        print(f"wrote {args.png} -- raster preview {image.shape[1]}x{image.shape[0]} px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
