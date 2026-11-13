#!/usr/bin/env python3
"""Run the CLI against a local fixture and render its real output as a short MP4."""

from __future__ import annotations

import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "demo.mp4"
WIDTH, HEIGHT = 1280, 720


class FixtureHandler(BaseHTTPRequestHandler):
    payload = b"demo-data-" * 25_000  # 250 kB per response

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *_args):
        pass


def main() -> int:
    server = HTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/fixture.bin"
        result = subprocess.run(
            [sys.executable, str(ROOT / "speed_test.py"), url],
            check=False, capture_output=True, text=True,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    if result.returncode:
        sys.stderr.write(result.stderr)
        return result.returncode

    lines = ["$ python3 speed_test.py http://127.0.0.1:<fixture>/fixture.bin", ""]
    lines.extend(result.stdout.strip().splitlines())
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    font = ImageFont.truetype(font_path, 21)
    title_font = ImageFont.truetype(font_path, 24)
    maximum_lines = max(1, (HEIGHT - 155) // 31)
    lines = lines[:maximum_lines]
    temp_pattern = ROOT / "scripts" / "frame-%04d.png"

    try:
        for frame_no in range(12):
            visible = min(len(lines), 3 + frame_no * 2)
            image = Image.new("RGB", (WIDTH, HEIGHT), "#0b1020")
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((48, 38, WIDTH - 48, HEIGHT - 38), radius=20, fill="#111827", outline="#334155", width=2)
            draw.text((80, 68), "INTERNET SPEED TEST", font=title_font, fill="#7dd3fc")
            draw.text((80, 112), "Terminal demo · 10 sequential downloads · local fixture", font=font, fill="#94a3b8")
            draw.line((80, 151, WIDTH - 80, 151), fill="#334155", width=2)
            for i, line in enumerate(lines[:visible]):
                color = "#86efac" if line.startswith("Результат") else "#e2e8f0"
                draw.text((80, 175 + i * 31), line, font=font, fill=color)
            image.save(str(temp_pattern) % frame_no)
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2", "-framerate", "2",
             "-i", str(temp_pattern), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(OUTPUT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        _, error = ffmpeg.communicate(timeout=60)
        if ffmpeg.returncode:
            sys.stderr.write(error.decode(errors="replace"))
            return ffmpeg.returncode
    finally:
        for path in (ROOT / "scripts").glob("frame-*.png"):
            path.unlink(missing_ok=True)

    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
