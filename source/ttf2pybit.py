# Convert Doto-Black.ttf into a 5x8 dot-matrix style MicroPython font dict
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import textwrap, json, os, math

ttf_path = "source/Doto-Black.ttf"

# Load font large so we can sample cleanly
try:
    font = ImageFont.truetype(ttf_path, size=80)
except Exception as e:
    raise RuntimeError(f"Failed to load TTF at {ttf_path}: {e}")

# Target micropy format: 5 columns x 8 rows (row 8 left empty), ASCII 32..126
W_COLS, H_ROWS = 5, 8
SAMPLE_ROWS = 8  # usable rows
START, END = 32, 126

def glyph_to_5x8_bits(ch, font):
    """Render a glyph from TTF into a 5x8 boolean grid (True=dot on)."""
    # Make a large canvas and draw character
    ascent, descent = font.getmetrics()
    canvas_w = 100
    canvas_h = ascent + descent + 20
    img = Image.new("L", (canvas_w, canvas_h), 0)
    draw = ImageDraw.Draw(img)
    # Draw with baseline at y=ascent (so baseline aligned)
    draw.text((0, 0), ch, font=font, fill=255)  # Pillow draws with baseline offset internally

    _bbox_ = img.getbbox()
    if _bbox_:
        bbox = (0, min(_bbox_[1],max(76,_bbox_[3])-56), 40, max(76,_bbox_[3]))
        if baseline := (bbox[3] - ascent)//8:
            print(f'char {ch} ascent:', baseline)
    else:
        # space or empty -> all False
        return np.zeros((SAMPLE_ROWS, W_COLS), dtype=bool)

    # Extract the tight bbox of ink
    glyph = img.crop(bbox)

    # We want to fit glyph into a 5x8 grid with small margins, preserving aspect.
    # Compute scale to fit inside (W_COLS, SAMPLE_ROWS) "units". We'll sample in continuous space.
    gw, gh = glyph.size
    if gw == 0 or gh == 0:
        return np.zeros((SAMPLE_ROWS, W_COLS), dtype=bool)

    # Scale factors to fit inside 5x8 with tiny margin
    target_w = W_COLS * 10  # arbitrary grid scaling for anti-aliased sampling
    target_h = SAMPLE_ROWS * 10
    # Compute uniform scale to fit
    scale = min(target_w / gw, target_h / gh)
    new_w = max(1, int(round(gw * scale)))
    new_h = max(1, int(round(gh * scale)))
    glyph_scaled = glyph.resize((new_w, new_h), Image.LANCZOS)

    # Place scaled glyph into a target grid canvas with centering
    canvas = Image.new("L", (target_w, target_h), 0)
    ox = (target_w - new_w)
    oy = (target_h - new_h)
    canvas.paste(glyph_scaled, (ox, oy))

    if ch == 'j':
        canvas.save("source/ch.png")

    # Now sample 5x8 points. For a "square dot" look, sample the center of each cell.
    grid = np.zeros((SAMPLE_ROWS, W_COLS), dtype=bool)
    cell_w = target_w / W_COLS
    cell_h = target_h / SAMPLE_ROWS

    # Threshold based on average intensity in a central patch of each cell
    for r in range(SAMPLE_ROWS):
        for c in range(W_COLS):
            # Sample a small box (central 60% of the cell)
            cx0 = int(c * cell_w + 0.2 * cell_w)
            cy0 = int(r * cell_h + 0.2 * cell_h)
            cx1 = int((c + 1) * cell_w - 0.2 * cell_w)
            cy1 = int((r + 1) * cell_h - 0.2 * cell_h)
            # cx1 = max(cx1, cx0 + 1)
            # cy1 = max(cy1, cy0 + 1)
            patch = np.asarray(canvas.crop((cx0, cy0, cx1, cy1)), dtype=np.uint8)
            # Consider "on" if average intensity > threshold
            val = patch.mean()
            grid[r, c] = val > 64  # threshold
    return grid

def grid_to_column_bytes(grid5x8):
    """Pack 5x8 grid into 5 bytes (one per column), bit0=top row, rows 0..7 used."""
    cols = []
    for c in range(W_COLS):
        byte = 0
        for r in range(SAMPLE_ROWS):  # rows 0..6
            if grid5x8[r, c]:
                byte |= (1 << r)  # bit0 = top row
        cols.append(byte)
    return cols

data_bytes = []
sample = ''
for code in range(START, END + 1):
    ch = chr(code)
    sample += ch
    grid = glyph_to_5x8_bits(ch, font)
    cols = grid_to_column_bytes(grid)
    data_bytes.extend(cols)

# Build FONT dict text
font_py_content = f"""# Auto-generated from Doto-Black.ttf -> 5x8 dot-matrix font for MicroPython ST7735
# Columns: 5 per glyph, bit0 = top row. Height uses 7 rows; row 8 is empty.
FONT = {{"Width": 5, "Height": 8, "Start": {START}, "End": {END}, "Data": bytearray({data_bytes})}}
"""

out_path = "font_doto5x8.py"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(font_py_content)

# Also render a quick 128x128 preview image using this bitmap font
def render_text_preview(text, cols=16, rows=16, cell_px=8):
    img = Image.new("RGB", (cols*cell_px, rows*cell_px), (0,0,0))
    draw = ImageDraw.Draw(img)
    # draw characters using the packed bytes
    x = 0
    y = 0
    for ch in text:
        if ch == "\n" or x >= cols:
            x = 0
            y += 1
            if ch == "\n":
                continue
        if y >= rows:
            break
        code = ord(ch)
        if code < START or code > END:
            x += 1
            continue
        idx = (code - START) * W_COLS
        cols_bytes = data_bytes[idx:idx+W_COLS]
        # paint pixels
        for cx, b in enumerate(cols_bytes):
            for ry in range(SAMPLE_ROWS):  # 0..6
                if b & (1 << ry):
                    # draw a square dot (2x2 if cell_px allows), else 1x1
                    px = x*cell_px + cx + 1  # +1 left margin
                    py = y*cell_px + ry + 1  # +1 top margin
                    # keep dots square-ish
                    img.putpixel((px, py), (255,255,255))
        x += 1
    return img

print('#'+sample+'#')

preview = render_text_preview(sample, cols=16, rows=8, cell_px=8)
preview_path = "source/doto5x8_preview.png"
preview.save(preview_path)
