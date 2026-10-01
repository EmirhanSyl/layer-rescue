"""Draws the Layer Rescue icon: printed layers (amber), the layer being printed (green) and the nozzle."""

from PIL import Image, ImageDraw

S = 1024  # drawn large and scaled down for smooth edges

def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # background: rounded square
    d.rounded_rectangle([24, 24, S - 24, S - 24], radius=210, fill=(31, 41, 51, 255))
    # layers already printed (amber), bottom to top
    left, right, h, gap = 200, S - 200, 92, 30
    y = 800
    amber = [(217, 119, 6), (234, 140, 18), (245, 158, 11)]
    for color in amber:
        d.rounded_rectangle([left, y - h, right, y], radius=46, fill=color + (255,))
        y -= h + gap
    # layer being printed (green): solid part + faint rest
    top = y
    d.rounded_rectangle([left, top - h, right, top], radius=46, fill=(58, 96, 86, 255))
    done = left + int((right - left) * 0.62)
    d.rounded_rectangle([left, top - h, done, top], radius=46, fill=(52, 211, 153, 255))
    # nozzle above the end of the green part
    cx = done - 30
    body_top, body_bottom = top - h - 230, top - h - 95
    d.rounded_rectangle([cx - 95, body_top, cx + 95, body_bottom], radius=26, fill=(236, 240, 243, 255))
    d.polygon([(cx - 60, body_bottom - 5), (cx + 60, body_bottom - 5), (cx + 16, top - h - 28), (cx - 16, top - h - 28)],
              fill=(236, 240, 243, 255))
    return img

if __name__ == "__main__":
    # Writes the icons used by the app and the installers. Run from the repository root:
    #   python packaging/icon/make_icon.py
    big = draw()
    big.resize((256, 256), Image.LANCZOS).save("src/layer_rescue/assets/icon.png", optimize=True)
    big.resize((256, 256), Image.LANCZOS).save(
        "src/layer_rescue/assets/icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    )
    big.save("packaging/macos/LayerRescue.icns")
