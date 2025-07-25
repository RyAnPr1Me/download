from PIL import Image, ImageDraw

# Create a 256x256 PNG with a conductor-like icon (simple, modern, blue/white theme)
def make_conductor_png(path="icon.png"):
    size = 256
    img = Image.new("RGBA", (size, size), (45, 45, 45, 255))
    draw = ImageDraw.Draw(img)
    # Outer white circle
    draw.ellipse((32, 32, 224, 224), fill="white", outline="#4a90e2", width=8)
    # Body
    draw.rounded_rectangle((108, 60, 148, 160), 12, fill="#4a90e2")
    draw.rounded_rectangle((88, 160, 168, 180), 8, fill="#4a90e2")
    draw.rounded_rectangle((120, 180, 136, 210), 6, fill="#4a90e2")
    # Head
    draw.ellipse((118, 80, 138, 100), fill="white", outline="#4a90e2", width=4)
    # Face (smile)
    draw.arc((122, 90, 134, 98), 20, 160, fill="#4a90e2", width=2)
    # Buttons
    draw.rounded_rectangle((116, 100, 140, 130), 6, fill="white", outline="#4a90e2", width=4)
    draw.rounded_rectangle((110, 130, 146, 140), 4, fill="white", outline="#4a90e2", width=2)
    img.save(path)
    print(f"Saved {path}")

if __name__ == "__main__":
    make_conductor_png()
