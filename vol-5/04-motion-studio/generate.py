"""Motion Studio, generate: brand + three lines in, a branded animation out.

    python generate.py sample-data/brand.json sample-data/brief.txt

Writes:
  out/animation.html  a self-contained HTML/canvas animation. No network, no
                      build step, no API key. Open it in a browser.

The local path is a real template-based generator: it composes the timeline from
the brand's pace and the brief's three lines, and the motion craft (easing
helpers, anticipation, per-word stagger, a logo lockup, a held final frame) is
baked into the template. Add --ai (and an ANTHROPIC_API_KEY) to have Claude write
a fresher animation instead, using the same deterministic contract so critique.py
and render.py still work on it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path

# Pace presets, in seconds. These are the whole personality of the piece:
# lead  = the breath before the first move
# gap   = distance between beat entrances (the stagger)
# beat  = how long one beat takes to settle
# hold  = dead air at the end, nothing moving, logo on screen
PACES = {
    "calm":   {"lead": 0.70, "gap": 0.95, "beat": 1.10, "hold": 1.30},
    "brisk":  {"lead": 0.40, "gap": 0.62, "beat": 0.80, "hold": 1.00},
    "snappy": {"lead": 0.22, "gap": 0.40, "beat": 0.55, "hold": 0.80},
}

# Which easing each cue gets. Named here so critique.py can see the intent.
CUE_EASE = {
    "headline": "anticipate",
    "rule": "easeInOutCubic",
    "support": "easeOutQuint",
    "kicker": "easeOutQuint",
    "lockup": "easeOutElastic",
    "wordmark": "easeOutCubic",
}


# ---------------------------------------------------------------- inputs

def load_brand(path: str) -> dict:
    brand = json.loads(Path(path).read_text(encoding="utf-8"))
    colors = brand.get("colors", {})
    fonts = brand.get("fonts", {})
    canvas = brand.get("canvas", {})
    pace = str(brand.get("pace", "brisk")).lower()
    if pace not in PACES:
        raise SystemExit(f"pace must be one of {sorted(PACES)}, got {pace!r}")
    return {
        "name": brand.get("name", "Your Brand"),
        "tagline": brand.get("tagline", ""),
        "pace": pace,
        "bg": colors.get("bg", "#101216"),
        "ink": colors.get("ink", "#f5f3ee"),
        "muted": colors.get("muted", "#98a1ae"),
        "accent": colors.get("accent", "#e4654a"),
        "accent2": colors.get("accent2", colors.get("accent", "#6fd3c7")),
        "display": fonts.get("display", "Helvetica, Arial, sans-serif"),
        "body": fonts.get("body", "Georgia, serif"),
        "width": int(canvas.get("width", 1280)),
        "height": int(canvas.get("height", 720)),
        "fps": int(canvas.get("fps", 24)),
    }


def parse_duration(value: str) -> float:
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(s|sec|secs|seconds)?\s*", value)
    if not m:
        raise SystemExit(f"could not read duration {value!r}, try '6s'")
    return float(m.group(1))


def load_brief(path: str) -> dict:
    """Three content lines, plus optional `key: value` directives."""
    beats: list[str] = []
    directives: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(duration|logo|style)\s*:\s*(.+)$", line, re.I)
        if m:
            directives[m.group(1).lower()] = m.group(2).strip()
            continue
        beats.append(line)
    if len(beats) != 3:
        raise SystemExit(
            f"brief.txt needs exactly three content lines, found {len(beats)}. "
            "Directives (duration:, logo:) and # comments do not count."
        )
    return {
        "beats": beats,
        "logo": directives.get("logo", ""),
        "duration": parse_duration(directives["duration"]) if "duration" in directives else None,
    }


# ---------------------------------------------------------------- timeline

def build_timeline(pace: str, target: float | None) -> tuple[list[dict], float]:
    """Lay out the cues, then stretch or squeeze them to hit the brief's duration.

    The hold is never scaled. A six second clip and a twelve second clip both
    end on the same length of stillness, because that stillness is what makes
    the last frame readable, not a fraction of the runtime.
    """
    p = PACES[pace]
    cues = [
        {"id": "headline", "label": "headline enters, per word", "start": p["lead"], "dur": p["beat"]},
        {"id": "rule", "label": "accent rule wipes under headline", "start": p["lead"] + p["gap"] * 0.55, "dur": p["beat"] * 0.9},
        {"id": "support", "label": "supporting line enters", "start": p["lead"] + p["gap"], "dur": p["beat"]},
        {"id": "kicker", "label": "kicker line enters", "start": p["lead"] + p["gap"] * 2, "dur": p["beat"]},
    ]
    last = max(c["start"] + c["dur"] for c in cues)
    cues.append({"id": "lockup", "label": "logo mark springs in", "start": last + p["gap"] * 0.45, "dur": p["beat"] * 1.25})
    lock = cues[-1]
    cues.append({"id": "wordmark", "label": "wordmark tracking contracts", "start": lock["start"] + p["beat"] * 0.35, "dur": p["beat"]})

    moving = max(c["start"] + c["dur"] for c in cues)
    total = moving + p["hold"]

    if target is not None:
        if target <= p["hold"] + 0.4:
            raise SystemExit(
                f"duration {target}s is shorter than this pace can hold "
                f"({p['hold']}s of final stillness plus the moves). Try "
                f"{p['hold'] + 1.5:.1f}s or slow the pace down."
            )
        scale = (target - p["hold"]) / moving
        for c in cues:
            c["start"] = round(c["start"] * scale, 4)
            c["dur"] = round(c["dur"] * scale, 4)
        total = target

    for c in cues:
        c["ease"] = CUE_EASE[c["id"]]
    return cues, round(total, 4)


def initial_of(name: str) -> str:
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    for ch in stripped:
        if ch.isalnum():
            return ch.upper()
    return "*"


def build_config(brand: dict, brief: dict) -> dict:
    cues, total = build_timeline(brand["pace"], brief["duration"])
    logo = brief["logo"] or brand["name"]
    return {
        "brand": brand["name"],
        "tagline": brand["tagline"],
        "pace": brand["pace"],
        "width": brand["width"],
        "height": brand["height"],
        "fps": brand["fps"],
        "duration": total,
        "hold": round(total - max(c["start"] + c["dur"] for c in cues), 4),
        "beats": brief["beats"],
        "logo": logo,
        "mark": initial_of(logo),
        "colors": {
            "bg": brand["bg"], "ink": brand["ink"], "muted": brand["muted"],
            "accent": brand["accent"], "accent2": brand["accent2"],
        },
        "fonts": {"display": brand["display"], "body": brand["body"]},
        "timeline": cues,
    }


# ---------------------------------------------------------------- template

SCENE_JS = r"""
// ---- easing helpers -------------------------------------------------------
// Every one of these is non-linear on purpose. `linear` is here only so you can
// A/B it against the others and feel why nothing in the scene uses it.
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
function linear(p)          { return p; }
function easeOutCubic(p)    { return 1 - Math.pow(1 - p, 3); }
function easeInOutCubic(p)  { return p < 0.5 ? 4*p*p*p : 1 - Math.pow(-2*p + 2, 3) / 2; }
function easeOutQuint(p)    { return 1 - Math.pow(1 - p, 5); }
function easeOutBack(p)     { const c1 = 1.70158, c3 = c1 + 1;
                              return 1 + c3*Math.pow(p - 1, 3) + c1*Math.pow(p - 1, 2); }
function easeOutElastic(p)  { const c4 = (2*Math.PI) / 3;
                              return p === 0 ? 0 : p === 1 ? 1
                                   : Math.pow(2, -10*p) * Math.sin((p*10 - 0.75)*c4) + 1; }
// Anticipation: pull back before you move. The first 18% of the cue drifts the
// wrong way, then easeOutBack overshoots past the target and settles.
function anticipate(p) {
  if (p <= 0) return 0;
  if (p >= 1) return 1;
  const k = 0.18;
  return p < k ? -0.10 * easeOutCubic(p / k) : easeOutBack((p - k) / (1 - k));
}
const EASE = { linear, easeOutCubic, easeInOutCubic, easeOutQuint,
               easeOutBack, easeOutElastic, anticipate };

const CUE = {};
CFG.timeline.forEach(c => { CUE[c.id] = c; });

// progress of a cue at time t, eased
function at(t, id, offset) {
  const c = CUE[id];
  const start = c.start + (offset || 0);
  return EASE[c.ease](clamp((t - start) / c.dur, 0, 1));
}
// raw, un-eased progress. Used for crossfades only, never for position.
function raw(t, start, dur) { return clamp((t - start) / dur, 0, 1); }
const mix = (a, b, p) => a + (b - a) * p;

// ---- layout ---------------------------------------------------------------
const C   = document.getElementById('stage');
const ctx = C.getContext('2d');
const W = CFG.width, H = CFG.height, D = CFG.duration;
const K = CFG.colors, F = CFG.fonts;

function withAlpha(hex, a) {
  const h = hex.replace('#', '');
  const n = h.length === 3 ? h.split('').map(c => c + c).join('') : h;
  const r = parseInt(n.slice(0, 2), 16), g = parseInt(n.slice(2, 4), 16), b = parseInt(n.slice(4, 6), 16);
  return 'rgba(' + r + ',' + g + ',' + b + ',' + a + ')';
}

// Wrap into lines of words, each word carrying its own x so it can be
// animated independently. This is what makes the stagger possible.
function layout(text, font, maxWidth) {
  ctx.font = font;
  const lines = [];
  let cur = [], curW = 0;
  const space = ctx.measureText(' ').width;
  for (const word of text.split(/\s+/)) {
    const w = ctx.measureText(word).width;
    if (cur.length && curW + space + w > maxWidth) { lines.push(cur); cur = []; curW = 0; }
    cur.push({ text: word, w: w });
    curW += (cur.length > 1 ? space : 0) + w;
  }
  if (cur.length) lines.push(cur);
  let index = 0;
  for (const line of lines) {
    let x = 0;
    for (const word of line) { word.x = x; word.i = index++; x += word.w + space; }
  }
  lines.totalWords = index;
  return lines;
}

// ---- the scene ------------------------------------------------------------
function background(t) {
  ctx.fillStyle = K.bg;
  ctx.fillRect(0, 0, W, H);

  // A dot grid that drifts across the whole runtime on easeInOutCubic, so the
  // frame is never dead even while the type is holding.
  const drift = easeInOutCubic(clamp(t / D, 0, 1));
  const step = 46, off = mix(-step, 0, drift);
  ctx.fillStyle = withAlpha(K.muted, 0.10);
  for (let y = off; y < H + step; y += step) {
    for (let x = off; x < W + step; x += step) {
      ctx.beginPath(); ctx.arc(x, y, 1.1, 0, Math.PI * 2); ctx.fill();
    }
  }
  // A soft accent glow that eases up with the headline, then stays.
  const glow = easeOutCubic(clamp((t - CUE.headline.start) / (CUE.headline.dur * 2), 0, 1));
  const g = ctx.createRadialGradient(W * 0.18, H * 0.18, 0, W * 0.18, H * 0.18, W * 0.75);
  g.addColorStop(0, withAlpha(K.accent, 0.20 * glow));
  g.addColorStop(1, withAlpha(K.accent, 0));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
}

function typeBlock(t, text, opts) {
  const lines = layout(text, opts.font, opts.maxWidth);
  // Per-word stagger inside the cue, capped so a long headline never drags.
  const perWord = Math.min(opts.cue.dur * 0.30, opts.cue.dur / Math.max(lines.totalWords, 1));
  ctx.font = opts.font;
  ctx.textBaseline = 'alphabetic';
  lines.forEach((line, li) => {
    const y = opts.y + li * opts.lineHeight;
    for (const word of line) {
      const p = at(t, opts.cue.id, word.i * perWord);
      if (p <= 0 && t < opts.cue.start) continue;
      const dy = mix(opts.rise, 0, p);
      const alpha = clamp(p * 1.6, 0, 1) * opts.alpha;
      if (alpha <= 0.001) continue;
      ctx.fillStyle = withAlpha(opts.color, alpha);
      ctx.fillText(word.text, opts.x + word.x, y + dy);
    }
  });
  return opts.y + (lines.length - 1) * opts.lineHeight;
}

function accentRule(t, y, alpha) {
  const p = at(t, 'rule');
  if (p <= 0) return;
  const w = mix(0, W * 0.26, p);
  ctx.fillStyle = withAlpha(K.accent, alpha);
  ctx.fillRect(W * 0.08, y, w, 5);
}

function lockup(t, alpha) {
  const pop = at(t, 'lockup');
  if (pop <= 0 && t < CUE.lockup.start) return;
  if (alpha <= 0.001) return;
  const cx = W / 2, cy = H / 2 - 10;
  const size = mix(0, 112, pop);

  // the mark: a rounded square that springs in and rotates home
  const rot = mix(-0.22, 0, easeOutCubic(clamp((t - CUE.lockup.start) / CUE.lockup.dur, 0, 1)));
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rot);
  ctx.fillStyle = withAlpha(K.accent, alpha);
  const r = 22, s = size / 2;
  ctx.beginPath();
  ctx.moveTo(-s + r, -s);
  ctx.arcTo(s, -s, s, s, r);
  ctx.arcTo(s, s, -s, s, r);
  ctx.arcTo(-s, s, -s, -s, r);
  ctx.arcTo(-s, -s, s, -s, r);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = withAlpha(K.bg, alpha);
  ctx.font = '700 ' + Math.round(size * 0.52) + 'px ' + F.display;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(CFG.mark, 0, size * 0.03);
  ctx.restore();

  // the wordmark: letters start wide apart and contract into place
  const wm = at(t, 'wordmark');
  if (wm <= 0) return;
  const track = mix(26, 2, wm);
  ctx.font = '600 34px ' + F.display;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  const chars = CFG.logo.split('');
  const widths = chars.map(ch => ctx.measureText(ch).width);
  const total = widths.reduce((a, b) => a + b, 0) + track * (chars.length - 1);
  let x = cx - total / 2;
  ctx.fillStyle = withAlpha(K.ink, alpha * clamp(wm * 1.4, 0, 1));
  chars.forEach((ch, i) => { ctx.fillText(ch, x, cy + 108); x += widths[i] + track; });

  if (CFG.tagline) {
    const tp = easeOutCubic(clamp((t - CUE.wordmark.start - CUE.wordmark.dur * 0.4) / (CUE.wordmark.dur * 0.8), 0, 1));
    ctx.font = 'italic 19px ' + F.body;
    ctx.textAlign = 'center';
    ctx.fillStyle = withAlpha(K.muted, alpha * tp);
    ctx.fillText(CFG.tagline, cx, cy + 142 + mix(8, 0, tp));
  }
}

// Pure function of time. render.py depends on this: same t, same pixels.
function drawFrame(t) {
  t = clamp(t, 0, D);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.textAlign = 'left';
  background(t);

  // Crossfade the copy out just before the lockup lands, so the two never fight.
  const fade = raw(t, CUE.lockup.start - CUE.lockup.dur * 0.25, CUE.lockup.dur * 0.55);
  const copy = 1 - easeInOutCubic(fade);

  if (copy > 0.001) {
    const bottom = typeBlock(t, CFG.beats[0], {
      cue: CUE.headline, font: '700 72px ' + F.display, color: K.ink,
      x: W * 0.08, y: H * 0.30, lineHeight: 84, maxWidth: W * 0.84,
      rise: 46, alpha: copy,
    });
    accentRule(t, bottom + 34, copy);
    typeBlock(t, CFG.beats[1], {
      cue: CUE.support, font: '400 34px ' + F.body, color: K.muted,
      x: W * 0.08, y: bottom + 104, lineHeight: 44, maxWidth: W * 0.72,
      rise: 26, alpha: copy,
    });
    typeBlock(t, CFG.beats[2], {
      cue: CUE.kicker, font: '600 28px ' + F.display, color: K.accent2,
      x: W * 0.08, y: bottom + 164, lineHeight: 38, maxWidth: W * 0.72,
      rise: 20, alpha: copy,
    });
  }
  lockup(t, easeOutCubic(clamp(fade * 1.3, 0, 1)));
}

// ---- playback / capture ---------------------------------------------------
const q = new URLSearchParams(location.search);

if (q.get('strip')) {
  // Deterministic filmstrip for render.py: frames stacked top to bottom in one
  // page, one headless screenshot per strip. No animation clock involved.
  const from = parseInt(q.get('from') || '0', 10);
  const count = parseInt(q.get('count') || '1', 10);
  const fps = parseFloat(q.get('fps') || CFG.fps);
  C.width = W; C.height = H * count;
  C.style.width = W + 'px'; C.style.height = (H * count) + 'px'; C.style.maxWidth = 'none';
  document.body.classList.add('strip');
  for (let k = 0; k < count; k++) {
    ctx.save();
    ctx.beginPath(); ctx.rect(0, k * H, W, H); ctx.clip();
    ctx.translate(0, k * H);
    drawFrame((from + k) / fps);
    ctx.restore();
  }
  document.title = 'strip-ready';
} else {
  let t0 = null;
  function tick(now) {
    if (t0 === null) t0 = now;
    drawFrame((now - t0) / 1000);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  function replay() { t0 = null; }
  document.body.addEventListener('click', replay);
  window.addEventListener('keydown', e => { if (e.code === 'Space') { e.preventDefault(); replay(); } });
}
"""

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; height: 100%; background: __BG__; }
  body { display: grid; place-items: center; font: 14px/1.5 system-ui, sans-serif; color: __MUTED__; }
  body.strip { display: block; }
  body.strip .hint { display: none; }
  canvas { display: block; width: min(96vw, __W__px); height: auto; aspect-ratio: __W__ / __H__; }
  .hint { position: fixed; bottom: 14px; left: 0; right: 0; text-align: center; opacity: .55; }
</style>
</head>
<body>
<canvas id="stage" width="__W__" height="__H__"></canvas>
<p class="hint">__HINT__</p>
<script>
const CFG = __CFG__;
</script>
<script>
__SCENE__
</script>
</body>
</html>
"""


def render_html(cfg: dict) -> str:
    hint = f"{cfg['duration']:.2f}s at {cfg['fps']}fps, pace {cfg['pace']}. Click or press space to replay."
    return (HTML
            .replace("__TITLE__", f"{cfg['brand']} motion")
            .replace("__BG__", cfg["colors"]["bg"])
            .replace("__MUTED__", cfg["colors"]["muted"])
            .replace("__W__", str(cfg["width"]))
            .replace("__H__", str(cfg["height"]))
            .replace("__HINT__", hint)
            .replace("__CFG__", json.dumps(cfg, indent=2))
            .replace("__SCENE__", SCENE_JS))


# ---------------------------------------------------------------- the AI path

GEN_PROMPT = """You are a motion designer writing a single self-contained HTML file.

Brand and brief, as JSON:
{cfg}

Write one HTML file, no external requests, no libraries, that animates these
three lines in the brand's colours and fonts and ends on a logo lockup.

Hard contract, because a renderer and a critic read this file:
- Keep `const CFG = {{...}}` at the top, exactly the JSON above, unchanged.
- Define `function drawFrame(t)` that paints the full frame for time t in
  seconds on a canvas with id "stage". It must be pure: same t, same pixels.
  No reads of Date, performance.now, or Math.random inside it.
- Define named easing helpers (easeOutCubic, easeInOutCubic, easeOutQuint,
  easeOutBack, easeOutElastic, anticipate). Position and scale must go through
  one of them. Linear is only allowed for opacity crossfades.
- Stagger entrances per word, honour every start/dur in CFG.timeline, and leave
  CFG.hold seconds of total stillness at the end.
- Keep the `?strip=&from=&count=&fps=` filmstrip branch exactly as described:
  it resizes the canvas to height*count and calls drawFrame((from+k)/fps) for
  each k, translated down by k*height.

Return only the HTML. No markdown fence, no commentary.
"""


def generate_ai(cfg: dict) -> str:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=8000,
        messages=[{"role": "user", "content": GEN_PROMPT.format(cfg=json.dumps(cfg, indent=2))}],
    )
    text = msg.content[0].text.strip()
    text = re.sub(r"^```(?:html)?\s*|\s*```$", "", text)
    if "drawFrame" not in text or "<canvas" not in text:
        raise ValueError("model did not return a usable animation (no drawFrame or no canvas)")
    return text


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description="Compose a branded canvas animation.")
    ap.add_argument("brand", help="path to brand.json")
    ap.add_argument("brief", help="path to brief.txt")
    ap.add_argument("-o", "--out", default="out/animation.html", help="output HTML path")
    ap.add_argument("--ai", action="store_true", help="let Claude write the animation instead")
    args = ap.parse_args()

    cfg = build_config(load_brand(args.brand), load_brief(args.brief))

    source = "template"
    if args.ai and os.getenv("ANTHROPIC_API_KEY"):
        try:
            html_text = generate_ai(cfg)
            source = "claude"
        except Exception as exc:
            print(f"(--ai failed: {exc}; falling back to the template)")
            html_text = render_html(cfg)
    else:
        if args.ai:
            print("(--ai given but ANTHROPIC_API_KEY is not set; using the template)")
        html_text = render_html(cfg)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")

    print(f"Wrote {out} ({out.stat().st_size:,} bytes, source: {source})")
    print(f"{cfg['duration']:.2f}s at {cfg['fps']}fps, pace {cfg['pace']}, "
          f"{cfg['hold']:.2f}s hold on the last frame")
    for c in cfg["timeline"]:
        print(f"  {c['start']:5.2f}s +{c['dur']:.2f}s  {c['ease']:<14} {c['label']}")
    print(f"Next: python critique.py {out}   then   python render.py {out}")


if __name__ == "__main__":
    main()
