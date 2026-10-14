"""Render a 10-second motion graphic to motion.mp4 (requires numpy, Pillow, ffmpeg)."""
import math
import subprocess

from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SECONDS = 1280, 720, 30, 10
N = FPS * SECONDS
SS = 2  # supersampling for smooth edges

BG = (14, 14, 28)
PALETTE = [(255, 94, 98), (255, 195, 0), (0, 210, 190), (120, 110, 255)]
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t):
    t = clamp(t)
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


TITLE_FONT = load_font(150 * SS)
SUB_FONT = load_font(34 * SS)


def frame(i):
    t = i / FPS
    w, h = W * SS, H * SS
    cx, cy = w / 2, h / 2
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # Background: drifting dot grid
    step = 80 * SS
    off = (t * 30 * SS) % step
    for gx in range(-1, w // step + 2):
        for gy in range(-1, h // step + 2):
            x, y = gx * step + off, gy * step + off * 0.5
            r = (2 + 1.5 * math.sin(t * 2 + gx * 0.5 + gy * 0.7)) * SS
            d.ellipse([x - r, y - r, x + r, y + r], fill=(40, 40, 70))

    # Scene 1 (0-3.5s): expanding colored rings bursting from center
    if t < 3.5:
        for k, col in enumerate(PALETTE):
            local = t - k * 0.25
            if local <= 0:
                continue
            p = ease_out_cubic(local / 1.6)
            fade = 1 - clamp((t - 2.6) / 0.9)
            r = p * (120 + k * 70) * SS
            width = int(max(1, (18 - k * 3) * SS * fade))
            c = mix(BG, col, fade)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=width)
        # orbiting dots
        for k in range(12):
            a = k / 12 * 2 * math.pi + t * 2.2
            rad = ease_out_back(t / 1.2) * 260 * SS * (1 - clamp((t - 2.8) / 0.7))
            x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad
            r = 10 * SS
            d.ellipse([x - r, y - r, x + r, y + r], fill=PALETTE[k % 4])

    # Scene 2 (3-7s): rotating square wave
    if 3.0 <= t < 7.0:
        local = t - 3.0
        cols, rows = 9, 5
        size = 70 * SS
        gap = 110 * SS
        x0 = cx - (cols - 1) * gap / 2
        y0 = cy - (rows - 1) * gap / 2
        for gx in range(cols):
            for gy in range(rows):
                delay = (gx + gy) * 0.06
                appear = ease_out_back((local - delay) / 0.6)
                vanish = ease_in_out((local - 3.0 - delay * 0.5) / 0.6)
                s = size * appear * (1 - vanish) / 2
                if s <= 0.5:
                    continue
                ang = local * 2.5 + (gx - gy) * 0.4
                pulse = 0.5 + 0.5 * math.sin(local * 4 - (gx + gy) * 0.6)
                col = mix(PALETTE[(gx + gy) % 4], (255, 255, 255), pulse * 0.25)
                x, y = x0 + gx * gap, y0 + gy * gap
                pts = [
                    (x + s * math.cos(ang + q * math.pi / 2) * math.sqrt(2),
                     y + s * math.sin(ang + q * math.pi / 2) * math.sqrt(2))
                    for q in range(4)
                ]
                d.polygon(pts, fill=col)

    # Scene 3 (6.6-10s): kinetic title
    if t >= 6.6:
        local = t - 6.6
        word = "MOTION"
        widths = [d.textlength(ch, font=TITLE_FONT) for ch in word]
        total = sum(widths) + 10 * SS * (len(word) - 1)
        x = cx - total / 2
        for k, ch in enumerate(word):
            p = ease_out_back((local - k * 0.08) / 0.7)
            y = cy - 40 * SS + (1 - p) * 300 * SS
            if p > 0:
                col = mix(BG, PALETTE[k % 4], clamp(p))
                d.text((x, y), ch, font=TITLE_FONT, fill=col, anchor="ls")
            x += widths[k] + 10 * SS

        # underline wipe
        lp = ease_in_out((local - 0.8) / 0.8)
        lw = total * lp
        d.rectangle([cx - lw / 2, cy + 10 * SS, cx + lw / 2, cy + 22 * SS],
                    fill=(255, 255, 255))

        # subtitle fade
        sp = ease_out_cubic((local - 1.4) / 0.8)
        if sp > 0:
            d.text((cx, cy + 90 * SS + (1 - sp) * 30 * SS), "GRAPHICS  •  10 SECONDS",
                   font=SUB_FONT, fill=mix(BG, (200, 200, 230), sp), anchor="mm")

    img = img.resize((W, H), Image.LANCZOS)

    # Fade in / fade out
    fade = min(clamp(t / 0.4), clamp((SECONDS - t) / 0.5))
    if fade < 1:
        img = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), img, fade)
    return img


def main():
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", "motion.mp4"],
        stdin=subprocess.PIPE,
    )
    for i in range(N):
        proc.stdin.write(frame(i).tobytes())
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    main()
