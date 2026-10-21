# Launcher artwork. No game art is shipped or downloaded: each game gets a background drawn in its own
# colours and its name in plain type. A user may put their own images in art\<game>\ (hero.png, logo.png,
# cover.png, icon.png), for example through their own files.
import os, random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import core


def path(game, kind):
    for ext in ('.png', '.jpg'):
        p = os.path.join(core.ART, game, kind + ext)
        if os.path.isfile(p):
            return p
    return None


def background(game, w, h):
    """Dark storm in the game's colours (electric blue, fire orange, blood red)."""
    c1, c2 = core.GAMES[game]['colors']
    rnd = random.Random(game)
    img = Image.new('RGB', (w, h), (11, 13, 18))
    glow = Image.new('RGB', (w, h), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    for _i in range(26):
        x, y = rnd.uniform(0.35, 1.05) * w, rnd.uniform(-0.1, 0.9) * h
        r = rnd.uniform(0.06, 0.22) * w
        c = rnd.choice([c1, c2, (60, 66, 82), (30, 34, 46)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(v * rnd.uniform(0.2, 0.55)) for v in c))
    glow = glow.filter(ImageFilter.GaussianBlur(w / 14))
    img = Image.blend(img, glow, 0.9)
    # a few thin bolts for the electric look
    bolts = ImageDraw.Draw(img)
    for _i in range(3):
        x, y = rnd.uniform(0.55, 0.95) * w, 0
        pts = [(x, y)]
        while y < h * rnd.uniform(0.4, 0.8):
            x += rnd.uniform(-30, 30)
            y += rnd.uniform(15, 45)
            pts.append((x, y))
        bolts.line(pts, fill=tuple(min(255, int(v * 0.5) + 30) for v in c2), width=1)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def _font(size, bold):
    try:
        f = ImageFont.truetype('bahnschrift.ttf', size)
        f.set_variation_by_name('Bold' if bold else 'SemiBold')
        return f
    except (OSError, ValueError, AttributeError):
        return ImageFont.load_default()


def title_image(game, width=420):
    """The game's name in plain type (no logo artwork), with the launcher's name under it."""
    name = core.GAMES[game]['name']
    big, small = _font(64, True), _font(30, False)
    img = Image.new('RGBA', (1400, 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((4, 0), name, font=big, fill=(236, 238, 243, 255))
    d.text((8, 84), 'Conduit Legacy Launcher', font=small, fill=(141, 148, 165, 255))
    img = img.crop(img.getbbox())
    s = min(width / img.width, 1.0)
    return img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
