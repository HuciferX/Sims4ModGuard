"""
step_indicator.py
Animated, Pillow-rendered step indicator circles for the wizard UI.

Each indicator is a tk.Canvas widget that:
  - Pre-renders glow images via Pillow + GaussianBlur
  - Animates the active state with a sine-wave pulsing glow ring
  - Displays ✓ / ✗ / ⚠ / number glyphs inside the circle
  - Handles state transitions cleanly

States:
  PENDING  — dim hollow ring, step number, greyed
  ACTIVE   — bright filled circle, pulsing outer glow, step number
  RUNNING  — spinning arc, amber
  DONE     — green filled circle, soft static glow, checkmark ✓
  WARNING  — amber filled circle, warning glyph ⚠
  CRITICAL — red filled circle, red glow, ✗
"""

import math
import tkinter as tk
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Color helpers ─────────────────────────────────────────────────────────────

BG = "#050510"   # match app background

def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _mix(c1: str, c2: str, t: float) -> str:
    """Linearly blend c1 (t=1) → c2 (t=0)."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 * t + r2 * (1 - t))
    g = int(g1 * t + g2 * (1 - t))
    b = int(b1 * t + b2 * (1 - t))
    return f"#{r:02x}{g:02x}{b:02x}"

# ── Pillow-based glow icon renderer ───────────────────────────────────────────

def _make_glow_image(size: int, color: str, glyph: str,
                     glow_intensity: float, fill_alpha: float = 0.18
                     ) -> "tk.PhotoImage":
    """
    Render a glowing circle icon using Pillow at 2× and downsample.
    Returns a tk.PhotoImage.
    """
    import tkinter as tk
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    S   = size * 2          # render at 2× for antialiasing
    cx  = cy = S // 2
    r   = S // 2 - 4

    rgb = _hex_to_rgb(color)
    bg_rgb = _hex_to_rgb(BG)

    # ── Layer 1: outer glow (multiple blurred circles) ──
    glow_img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd       = ImageDraw.Draw(glow_img)
    # Draw glow rings with increasing blur
    for radius_extra, alpha_factor in [(20, 0.25), (12, 0.40), (6, 0.55)]:
        gr = r + radius_extra
        gd.ellipse([cx-gr, cy-gr, cx+gr, cy+gr],
                   fill=(rgb[0], rgb[1], rgb[2],
                         int(glow_intensity * alpha_factor * 200)))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(16))

    # ── Layer 2: circle fill ──
    fill_img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fd       = ImageDraw.Draw(fill_img)
    fill_a   = int(fill_alpha * 255)
    fd.ellipse([cx-r, cy-r, cx+r, cy+r],
               fill=(rgb[0], rgb[1], rgb[2], fill_a),
               outline=(rgb[0], rgb[1], rgb[2], 255),
               width=3)

    # ── Layer 3: glyph text ──
    text_img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    td       = ImageDraw.Draw(text_img)
    fsize    = max(16, S // 3)
    try:
        font = ImageFont.truetype("cour.ttf", fsize)
    except Exception:
        font = ImageFont.load_default()
    bbox  = td.textbbox((0, 0), glyph, font=font)
    tw    = bbox[2] - bbox[0]
    th    = bbox[3] - bbox[1]
    tx    = cx - tw // 2
    ty    = cy - th // 2
    td.text((tx, ty), glyph, fill=(rgb[0], rgb[1], rgb[2], 255), font=font)

    # ── Composite ──
    base = Image.new("RGBA", (S, S), (bg_rgb[0], bg_rgb[1], bg_rgb[2], 255))
    base.paste(glow_img, mask=glow_img)
    base.paste(fill_img, mask=fill_img)
    base.paste(text_img, mask=text_img)

    # Downsample to final size
    base = base.resize((size, size), Image.LANCZOS)

    from PIL import ImageTk
    return ImageTk.PhotoImage(base)


# ── State configurations ──────────────────────────────────────────────────────

STATE_CONFIGS = {
    "PENDING":  {"color": "#2a2a4a", "glyph": None,  "glow": 0.0,  "fill": 0.0,  "border": "#1a1a3a"},
    "ACTIVE":   {"color": None,       "glyph": None,  "glow": 0.8,  "fill": 0.18, "border": None,     "pulse": True},
    "RUNNING":  {"color": "#ffaa00",  "glyph": None,  "glow": 0.4,  "fill": 0.10, "border": "#ffaa00", "spin": True},
    "DONE":     {"color": "#00ff9f",  "glyph": "✓",   "glow": 0.4,  "fill": 0.18, "border": "#00ff9f"},
    "WARNING":  {"color": "#ffaa00",  "glyph": "⚠",   "glow": 0.3,  "fill": 0.12, "border": "#ffaa00"},
    "CRITICAL": {"color": "#ff003c",  "glyph": "✗",   "glow": 0.6,  "fill": 0.18, "border": "#ff003c"},
    "COMPLETE": {"color": "#00ff9f",  "glyph": "✓",   "glow": 0.4,  "fill": 0.18, "border": "#00ff9f"},
}

SPIN_CHARS = ["◜ ", " ◝", " ◞", "◟ ", "◠ ", " ◡", " ◢", "◣ "]


# ── StepIndicator widget ──────────────────────────────────────────────────────

class StepIndicator(tk.Canvas):
    """
    Animated circular step indicator. Works with or without Pillow.
    With Pillow: renders proper Gaussian glow images.
    Without Pillow: falls back to pure Canvas drawing.
    """

    def __init__(self, parent, step_num: str = "1",
                 step_color: str = "#00ff9f",
                 state: str = "PENDING",
                 size: int = 52, **kw):
        super().__init__(parent,
                         width=size, height=size,
                         bg=BG, highlightthickness=0, **kw)
        self._num     = step_num
        self._color   = step_color
        self._state   = state
        self._size    = size
        self._phase   = 0.0       # pulse phase (0–2π)
        self._spin    = 0         # spin frame index
        self._running = True
        self._img_ref = None      # hold Pillow PhotoImage reference
        self._animate()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_state(self, state: str):
        self._state = state
        self._phase = 0.0
        if state not in ("ACTIVE", "RUNNING"):
            self._draw()  # static redraw immediately

    def set_color(self, color: str):
        self._color = color

    def destroy(self):
        self._running = False
        super().destroy()

    # ── Animation loop ────────────────────────────────────────────────────────

    def _animate(self):
        if not self._running:
            return
        if self._state == "ACTIVE":
            self._phase = (self._phase + 0.10) % (2 * math.pi)
        elif self._state == "RUNNING":
            self._spin = (self._spin + 1) % len(SPIN_CHARS)
        self._draw()
        try:
            self.after(40, self._animate)
        except Exception:
            pass

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        if PIL_AVAILABLE:
            self._draw_pillow()
        else:
            self._draw_canvas()

    def _draw_pillow(self):
        """High-quality Pillow rendering."""
        cfg   = STATE_CONFIGS.get(self._state, STATE_CONFIGS["PENDING"])
        color = cfg["color"] or self._color

        # Compute current glow intensity
        base_glow = cfg["glow"]
        if cfg.get("pulse"):
            glow = base_glow * ((math.sin(self._phase) + 1) / 2 * 0.6 + 0.4)
        else:
            glow = base_glow

        # Glyph text
        if cfg.get("spin"):
            glyph = SPIN_CHARS[self._spin]
        elif cfg.get("glyph"):
            glyph = cfg["glyph"]
        else:
            glyph = self._num

        try:
            img = _make_glow_image(self._size, color, glyph, glow, cfg["fill"])
            self._img_ref = img
            self.delete("all")
            self.create_image(0, 0, anchor="nw", image=img)
        except Exception:
            self._draw_canvas()

    def _draw_canvas(self):
        """Fallback: pure tkinter Canvas drawing with simulated glow."""
        self.delete("all")
        s  = self._size
        cx = cy = s // 2
        r  = s // 2 - 3

        cfg   = STATE_CONFIGS.get(self._state, STATE_CONFIGS["PENDING"])
        color = cfg["color"] or self._color

        if self._state == "PENDING":
            self.create_oval(cx-r, cy-r, cx+r, cy+r,
                             fill="", outline="#1a1a3a", width=1)
            self.create_text(cx, cy, text=self._num,
                             fill="#2a2a4a",
                             font=("Courier New", 15))
            return

        # Glow rings (simulated via concentric ovals blended toward BG)
        glow = cfg["glow"]
        if cfg.get("pulse"):
            glow *= (math.sin(self._phase) + 1) / 2 * 0.7 + 0.3
        for i in range(5, 0, -1):
            mix_t = glow * (1 - (i - 1) / 5) * 0.4
            c = _mix(color, BG, mix_t)
            rg = r + i * 3
            self.create_oval(cx-rg, cy-rg, cx+rg, cy+rg, outline=c, width=1)

        # Circle fill
        fill_c = _mix(color, BG, 0.15)
        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         fill=fill_c, outline=color, width=2)

        # Glyph
        if cfg.get("spin"):
            text = SPIN_CHARS[self._spin]
        elif cfg.get("glyph"):
            text = cfg["glyph"]
        else:
            text = self._num
        self.create_text(cx, cy, text=text, fill=color,
                         font=("Courier New", 17, "bold"))


# ── Connector line ────────────────────────────────────────────────────────────

class ConnectorLine(tk.Canvas):
    """
    Thin vertical line connecting two step indicators.
    Green when the step above is done, dim otherwise.
    """
    WIDTH = 2

    def __init__(self, parent, done: bool = False, height: int = 24, **kw):
        super().__init__(parent,
                         width=52, height=height,
                         bg=BG, highlightthickness=0, **kw)
        self._done   = done
        self._height = height
        self._draw()

    def set_done(self, done: bool):
        self._done = done
        self._draw()

    def _draw(self):
        self.delete("all")
        cx     = 26  # center horizontally (indicator is 52px wide)
        color  = "#00ff9f" if self._done else "#1a1a3a"
        self.create_line(cx, 0, cx, self._height,
                         fill=color, width=self.WIDTH)
