"""Motion Studio, render: the HTML animation out as a real video file.

    python render.py out/animation.html                 # mp4 at the brand's fps
    python render.py out/animation.html --format webm
    python render.py out/animation.html --dry-run       # print the pipeline, run nothing

How it works, and why it is shaped this way: screen-recording an animation frame
by frame normally means one headless browser screenshot per frame, and Chrome's
startup cost (about six seconds) makes that unbearable. So the generated page has
a filmstrip mode. `?strip=1&from=0&count=24&fps=24` stacks twenty-four frames
vertically in a single page, which is one screenshot, and ffmpeg's `untile`
filter unstacks them straight into a video. A six second clip is a handful of
browser launches instead of a hundred and forty four.

Needs: ffmpeg, and a Chromium-family browser (Google Chrome, Chromium, Brave, or
Edge). Both are detected, not assumed. If one is missing, this prints the exact
commands it would have run and exits non-zero. There is an optional Playwright
path (--engine playwright) for people who have it; nothing here requires it.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import pathname2url

# Chromium's own surface limit is 16384px. Stay under it with room to spare.
MAX_STRIP_PX = 15600

BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def find_browser() -> str | None:
    for candidate in BROWSERS:
        if "/" in candidate:
            if Path(candidate).exists():
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None


def read_cfg(html_path: Path) -> dict:
    """Pull the CFG block back out of the generated page."""
    text = html_path.read_text(encoding="utf-8")
    m = re.search(r"const\s+CFG\s*=\s*(\{.*?\n\})\s*;", text, re.S)
    if not m:
        raise SystemExit(f"{html_path} has no `const CFG = {{...}};` block; "
                         "was it made by generate.py?")
    return json.loads(m.group(1))


def strip_url(html_path: Path, frm: int, count: int, fps: float) -> str:
    base = "file://" + quote(pathname2url(str(html_path.resolve())))
    return f"{base}?strip=1&from={frm}&count={count}&fps={fps}"


def chrome_cmd(browser: str, url: str, out_png: Path, width: int, height: int) -> list[str]:
    return [
        browser, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--no-sandbox", "--no-first-run", "--force-device-scale-factor=1",
        "--allow-file-access-from-files",
        f"--window-size={width},{height}",
        f"--screenshot={out_png}", url,
    ]


def ffmpeg_cmd(pattern: str, fps: float, rows: int, frames: int,
               out_path: Path, fmt: str) -> list[str]:
    codec = ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32"] if fmt == "webm" \
        else ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]
    # Each input image holds `rows` frames, so the input rate is fps/rows and
    # untile multiplies it back up. Get this wrong and you ship a video with the
    # right pixels and a duration off by a factor of twenty-one.
    return [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", f"{fps / rows:.9f}", "-i", pattern,
        "-vf", f"untile=1x{rows},format=yuv420p",
        "-frames:v", str(frames), "-r", str(fps), *codec,
        "-movflags", "+faststart", str(out_path),
    ]


def plan(html_path: Path, cfg: dict, fps: float, fmt: str, out_path: Path,
         work: Path) -> dict:
    width, height = cfg["width"], cfg["height"]
    frames = max(1, round(cfg["duration"] * fps))
    rows = max(1, min(frames, MAX_STRIP_PX // height))
    strips = -(-frames // rows)          # ceil
    padded = strips * rows               # last strip repeats the held frame
    return {
        "width": width, "height": height, "frames": frames, "rows": rows,
        "strips": strips, "padded": padded, "fps": fps,
        "pattern": str(work / "strip_%04d.png"),
        "shots": [
            (work / f"strip_{i + 1:04d}.png", strip_url(html_path, i * rows, rows, fps))
            for i in range(strips)
        ],
        "video": ffmpeg_cmd(str(work / "strip_%04d.png"), fps, rows, frames, out_path, fmt),
    }


def render_playwright(html_path: Path, cfg: dict, fps: float, work: Path, p: dict) -> None:
    """Optional. Same filmstrip trick, one browser launch for every strip."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": p["width"], "height": p["height"] * p["rows"]})
        for png, url in p["shots"]:
            page.goto(url)
            page.wait_for_function("document.title === 'strip-ready'")
            page.screenshot(path=str(png))
            print(f"  captured {png.name}")
        browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Capture the animation to a video file.")
    ap.add_argument("html", help="the animation HTML from generate.py")
    ap.add_argument("-o", "--out", default=None, help="output video path")
    ap.add_argument("--format", choices=["mp4", "webm"], default="mp4")
    ap.add_argument("--fps", type=float, default=None, help="override the brand fps")
    ap.add_argument("--engine", choices=["chrome", "playwright"], default="chrome")
    ap.add_argument("--dry-run", action="store_true", help="print the pipeline, capture nothing")
    ap.add_argument("--keep-frames", action="store_true", help="leave the strip PNGs on disk")
    args = ap.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        raise SystemExit(f"no such file: {html_path}")
    cfg = read_cfg(html_path)
    fps = args.fps or float(cfg.get("fps", 24))
    out_path = Path(args.out) if args.out else html_path.with_suffix("." + args.format)
    work = html_path.parent / "frames"
    p = plan(html_path, cfg, fps, args.format, out_path, work)

    ffmpeg = shutil.which("ffmpeg")
    browser = find_browser()

    print(f"{cfg['duration']:.2f}s x {fps}fps = {p['frames']} frames at "
          f"{p['width']}x{p['height']}")
    print(f"{p['strips']} filmstrip screenshot(s) of {p['rows']} frames each "
          f"({p['height'] * p['rows']}px tall), then one ffmpeg untile pass")
    print(f"ffmpeg:  {ffmpeg or 'NOT FOUND'}")
    print(f"browser: {browser or 'NOT FOUND'}")

    if args.dry_run or not ffmpeg or not browser:
        print("\nThe exact pipeline:")
        for png, url in p["shots"]:
            print("  " + " ".join(chrome_cmd(browser or "<chrome>", url, png,
                                             p["width"], p["height"] * p["rows"])))
        print("  " + " ".join(p["video"]))
        if args.dry_run:
            print("\nDry run, nothing captured.")
            return
        missing = []
        if not ffmpeg:
            missing.append("ffmpeg       brew install ffmpeg")
        if not browser:
            missing.append("a Chromium   brew install --cask google-chrome")
        print("\nCannot capture. Install:")
        for line in missing:
            print("  " + line)
        print("Or, if you already run Playwright:  python render.py "
              f"{html_path} --engine playwright")
        sys.exit(2)

    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("strip_*.png"):
        old.unlink()

    if args.engine == "playwright":
        try:
            render_playwright(html_path, cfg, fps, work, p)
        except ImportError:
            raise SystemExit("playwright is not installed. Either `pip install playwright && "
                             "playwright install chromium`, or drop --engine playwright and "
                             "use the Chrome path, which needs nothing extra.")
    else:
        for i, (png, url) in enumerate(p["shots"], 1):
            cmd = chrome_cmd(browser, url, png, p["width"], p["height"] * p["rows"])
            res = subprocess.run(cmd, capture_output=True, text=True)
            if not png.exists():
                print(res.stderr[-800:], file=sys.stderr)
                raise SystemExit(f"browser produced no screenshot for strip {i}")
            print(f"  strip {i}/{p['strips']}  frames "
                  f"{(i - 1) * p['rows']}-{i * p['rows'] - 1}  {png.stat().st_size:,} bytes")

    res = subprocess.run(p["video"], capture_output=True, text=True)
    if res.returncode != 0 or not out_path.exists():
        print(res.stderr[-1500:], file=sys.stderr)
        raise SystemExit("ffmpeg failed; the strip PNGs are still in " + str(work))

    if not args.keep_frames:
        for png in work.glob("strip_*.png"):
            png.unlink()
        work.rmdir()

    print(f"\nWrote {out_path} ({out_path.stat().st_size:,} bytes, "
          f"{p['frames']} frames at {fps}fps)")


if __name__ == "__main__":
    main()
