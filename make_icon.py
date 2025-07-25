import cairosvg
from PIL import Image
import os

def svg_to_ico(svg_path, ico_path, size=256):
    # Convert SVG to PNG in memory
    png_bytes = cairosvg.svg2png(url=svg_path, output_width=size, output_height=size)
    # Save PNG to a temporary file
    tmp_png = svg_path + ".tmp.png"
    with open(tmp_png, "wb") as f:
        f.write(png_bytes)
    # Open PNG and save as ICO
    img = Image.open(tmp_png).convert("RGBA")
    img.save(ico_path, format="ICO", sizes=[(size, size)])
    os.remove(tmp_png)

if __name__ == "__main__":
    svg_to_ico("icon.svg", "icon.ico")
    print("icon.ico created.")
