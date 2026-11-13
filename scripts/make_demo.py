#!/usr/bin/env python3
"""Record a real CLI run in a PTY, then render that captured terminal session."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "demo.mp4"
CAST = ROOT / "demo.typescript"
WIDTH, HEIGHT = 1440, 900
FRAME_DIR = ROOT / "scripts"


class FixtureHandler(BaseHTTPRequestHandler):
    payload = b"TETRIX8-demo-data-" * 14_000

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *_args):
        pass


def record_terminal(url: str) -> str:
    command = (
        "stty cols 110 rows 30; "
        "printf '\\033[1;36m╭─ TETRIX 8  /  TERMINAL NETWORK DIAGNOSTICS\\033[0m\\n'; "
        "printf '\\033[90m│  Sequential download benchmark · 10 requests\\033[0m\\n'; "
        "printf '\\033[90m╰────────────────────────────────────────────────────────────\\033[0m\\n\\n'; "
        f"printf '\\033[1;32m$\\033[0m python3 speed_test.py {url}\\n\\n'; "
        f"python3 {ROOT / 'speed_test.py'} {url}; "
        "printf '\\n\\033[1;36mTETRIX 8  •  SESSION COMPLETE\\033[0m\\n'"
    )
    result = subprocess.run(
        ["script", "--quiet", "--return", "--flush", "--command", command, str(CAST)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or f"Recorded CLI exited with code {result.returncode}")
    raw = CAST.read_bytes()
    # Keep the terminal's actual printable output, removing ANSI control sequences
    # from the captured PTY transcript before drawing the playback frames.
    raw = re.sub(rb"\x1b\][^\x07]*(?:\x07|\x1b\\)", b"", raw)
    raw = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", raw)
    raw = raw.replace(b"\r", b"").replace(b"\x08", b"")
    transcript = raw.decode("utf-8", errors="replace")
    # util-linux `script` adds recording metadata around the PTY payload;
    # keep the program's actual terminal output, not that wrapper metadata.
    return "\n".join(
        line for line in transcript.splitlines()
        if not line.startswith("Script started on ")
        and not line.startswith("Script done on ")
    )


def render_video(transcript: str) -> None:
    lines = [line.rstrip() for line in transcript.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    lines = lines[:25]
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    font = ImageFont.truetype(font_path, 22)
    title_font = ImageFont.truetype(font_path, 25)
    label_font = ImageFont.truetype(font_path, 17)
    pattern = FRAME_DIR / "pty-frame-%04d.png"

    def draw_frame(visible: int, frame_number: int) -> None:
        image = Image.new("RGB", (WIDTH, HEIGHT), "#090e1b")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((42, 34, WIDTH - 42, HEIGHT - 34), radius=24,
                               fill="#111827", outline="#1e3a5f", width=2)
        draw.rounded_rectangle((42, 34, WIDTH - 42, 105), radius=24, fill="#0f172a")
        draw.rectangle((42, 78, WIDTH - 42, 105), fill="#0f172a")
        draw.ellipse((68, 60, 84, 76), fill="#fb7185")
        draw.ellipse((96, 60, 112, 76), fill="#fbbf24")
        draw.ellipse((124, 60, 140, 76), fill="#34d399")
        draw.text((177, 52), "TETRIX 8  /  NETWORK LAB", font=title_font, fill="#67e8f9")
        draw.text((WIDTH - 347, 57), "LIVE PTY CAPTURE  ·  10 REQUESTS", font=label_font, fill="#94a3b8")
        draw.line((72, 116, WIDTH - 72, 116), fill="#26354c", width=2)
        draw.text((78, 132), "REAL CONSOLE SESSION", font=label_font, fill="#38bdf8")
        draw.text((WIDTH - 345, 132), "127.0.0.1  /  LOCAL TEST FIXTURE", font=label_font, fill="#64748b")
        draw.rounded_rectangle((68, 165, WIDTH - 68, HEIGHT - 66), radius=12,
                               fill="#070b13", outline="#233044", width=2)
        y = 190
        for index, line in enumerate(lines[:visible]):
            tint = "#a7f3d0" if "Результат" in line else "#d7e2f0"
            if "TETRIX 8" in line or "TETRIX 8  /" in line:
                tint = "#67e8f9"
            if line.lstrip().startswith("$"):
                tint = "#86efac"
            draw.text((94, y + index * 29), line, font=font, fill=tint)
        draw.text((86, HEIGHT - 98), "PTY RECORDING  •  python3 speed_test.py  •  full response reads", font=label_font, fill="#64748b")
        image.save(str(pattern) % frame_number)

    count = max(1, len(lines))
    try:
        for frame in range(count):
            draw_frame(frame + 1, frame)
        # Hold the completed terminal result for an extra three seconds.
        for frame in range(count, count + 6):
            draw_frame(count, frame)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "2",
             "-i", str(pattern), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(OUTPUT)],
            check=True, timeout=90,
        )
    finally:
        for path in FRAME_DIR.glob("pty-frame-*.png"):
            path.unlink(missing_ok=True)


def main() -> int:
    server = HTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/fixture.bin"
        transcript = record_terminal(url)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    render_video(transcript)
    print(f"Recorded PTY session: {CAST} ({CAST.stat().st_size:,} bytes)")
    print(f"TETRIX 8 terminal video: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Demo recording failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
