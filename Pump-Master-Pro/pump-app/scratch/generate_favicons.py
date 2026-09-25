import os
from PIL import Image, ImageDraw

out_dir = r"c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app\static\img"
os.makedirs(out_dir, exist_ok=True)

# 1. High-quality SVG Favicon
# Clean, crisp industrial pump volute + droplet motif with vibrant cyan/blue gradients
svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <!-- Background Radial Gradient -->
    <radialGradient id="bgGrad" cx="50%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#090d16"/>
    </radialGradient>
    
    <!-- Outer Ring Gradient -->
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="50%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#2563eb"/>
    </linearGradient>

    <!-- Droplet / Flow Gradient -->
    <linearGradient id="dropGrad" x1="20%" y1="0%" x2="80%" y2="100%">
      <stop offset="0%" stop-color="#67e8f9"/>
      <stop offset="50%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>

    <!-- Impeller Swirl Gradient -->
    <linearGradient id="impellerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.1"/>
    </linearGradient>
    
    <!-- Glow Filter -->
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="1.5" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- Base Squircle / Rounded Container -->
  <rect x="2" y="2" width="60" height="60" rx="14" fill="url(#bgGrad)" stroke="url(#ringGrad)" stroke-width="2.5"/>

  <!-- Centrifugal Volute Discharge Nozzle (Top-Right) -->
  <path d="M 38 12 L 52 12 C 53.5 12 54.5 13 54.5 14.5 L 54.5 24 C 54.5 25 53.5 25.5 52.5 25 L 45 20" 
        fill="url(#ringGrad)" opacity="0.85"/>
  <rect x="52" y="10" width="3.5" height="16" rx="1.5" fill="#38bdf8"/>

  <!-- Circular Volute Casing Ring -->
  <circle cx="31" cy="34" r="21" fill="none" stroke="url(#ringGrad)" stroke-width="3" stroke-linecap="round" stroke-dasharray="105 25"/>

  <!-- Impeller Curved Blades (Rotating Energy) -->
  <!-- Blade 1 -->
  <path d="M 31 23 C 37 23 42 27 43 33" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
  <!-- Blade 2 -->
  <path d="M 42 34 C 42 40 37 45 31 45" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
  <!-- Blade 3 -->
  <path d="M 31 45 C 25 45 20 40 20 34" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
  <!-- Blade 4 -->
  <path d="M 20 34 C 20 28 25 23 31 23" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" opacity="0.6"/>

  <!-- Central Water Droplet (Fluid Energy) -->
  <!-- Droplet outline with glow -->
  <path d="M 31 20 C 31 20 39.5 30.5 39.5 35.5 C 39.5 40.2 35.7 44 31 44 C 26.3 44 22.5 40.2 22.5 35.5 C 22.5 30.5 31 20 31 20 Z" 
        fill="url(#dropGrad)" filter="url(#glow)"/>

  <!-- Droplet Gloss / Highlight Reflection -->
  <path d="M 28 27 C 28 27 25 33 25 36 C 25 38 26.5 40 28.5 40.5 C 27 39.5 26.2 37.5 26.2 35.5 C 26.2 32.5 28 27 28 27 Z" 
        fill="#ffffff" opacity="0.65"/>
  <circle cx="34" cy="33" r="1.5" fill="#ffffff" opacity="0.8"/>
</svg>
'''

svg_path = os.path.join(out_dir, "favicon.svg")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg_content.strip())
print(f"Wrote {svg_path}")

# 2. Render Raster Favicons (180x180, 64x64, 32x32, 16x16) using PIL Drawing for crisp display
def create_raster_favicon(size):
    s = size / 64.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background rounded rectangle
    r = int(14 * s)
    draw.rounded_rectangle([int(2*s), int(2*s), int(60*s), int(60*s)], radius=r, fill=(15, 23, 42, 255), outline=(56, 189, 248, 255), width=max(1, int(2.5*s)))

    # Discharge nozzle
    draw.rectangle([int(40*s), int(12*s), int(53*s), int(22*s)], fill=(2, 132, 199, 255))
    draw.rounded_rectangle([int(51*s), int(10*s), int(55*s), int(24*s)], radius=max(1, int(1.5*s)), fill=(56, 189, 248, 255))

    # Casing arc / circle
    draw.arc([int(10*s), int(13*s), int(52*s), int(55*s)], start=30, end=330, fill=(2, 132, 199, 255), width=max(1, int(3*s)))

    # Droplet geometry: drawn with polygon + circles
    cx, cy = int(31 * s), int(35 * s)
    drop_r = int(8.5 * s)
    # Bottom circle
    draw.ellipse([cx - drop_r, cy - drop_r, cx + drop_r, cy + drop_r], fill=(56, 189, 248, 255))
    # Top triangle pointing up
    top_y = int(20 * s)
    draw.polygon([(cx - int(7.5*s), cy - int(2*s)), (cx, top_y), (cx + int(7.5*s), cy - int(2*s))], fill=(56, 189, 248, 255))

    # Inner droplet shine / highlight
    if size >= 32:
        draw.ellipse([cx - int(4*s), cy - int(4*s), cx - int(1*s), cy + int(2*s)], fill=(255, 255, 255, 180))
        draw.ellipse([cx + int(2*s), cy - int(3*s), cx + int(4*s), cy - int(1*s)], fill=(255, 255, 255, 220))

    return img

img_180 = create_raster_favicon(180)
img_180.save(os.path.join(out_dir, "apple-touch-icon.png"), format="PNG")

img_64 = create_raster_favicon(64)
img_64.save(os.path.join(out_dir, "favicon-64x64.png"), format="PNG")

img_32 = create_raster_favicon(32)
img_32.save(os.path.join(out_dir, "favicon-32x32.png"), format="PNG")

img_16 = create_raster_favicon(16)
img_16.save(os.path.join(out_dir, "favicon-16x16.png"), format="PNG")

# Multi-resolution .ico file (contains 16, 32, 48, 64)
ico_path = os.path.join(out_dir, "favicon.ico")
img_64.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print(f"Wrote raster favicons and {ico_path}")
