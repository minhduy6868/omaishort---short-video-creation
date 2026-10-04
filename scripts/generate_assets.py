import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_svg_favicon(output_path):
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#8b5cf6"/>
      <stop offset="50%" stop-color="#ec4899"/>
      <stop offset="100%" stop-color="#3b82f6"/>
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#a855f7" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#ec4899" stop-opacity="0.6"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="16" flood-color="#8b5cf6" flood-opacity="0.4"/>
    </filter>
  </defs>
  <rect width="512" height="512" rx="128" fill="#090a0f"/>
  <rect x="16" y="16" width="480" height="480" rx="112" fill="none" stroke="url(#glow)" stroke-width="4" opacity="0.5"/>
  <!-- Play emblem with film frame cut -->
  <g filter="url(#shadow)">
    <path d="M 180 140 C 180 125 198 115 210 124 L 370 234 C 382 242 382 270 370 278 L 210 388 C 198 397 180 387 180 372 Z" fill="url(#grad)"/>
    <circle cx="160" cy="256" r="28" fill="#ffffff" opacity="0.9"/>
    <circle cx="352" cy="170" r="16" fill="#ec4899" opacity="0.8"/>
    <circle cx="352" cy="342" r="16" fill="#3b82f6" opacity="0.8"/>
  </g>
</svg>'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    print(f"Created SVG favicon: {output_path}")

def draw_gradient_background(width, height):
    # Base dark image
    base = Image.new("RGBA", (width, height), (9, 10, 15, 255))
    
    # Create radial gradient glow top-left (violet)
    glow1 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(glow1)
    d1.ellipse((-100, -100, 700, 700), fill=(139, 92, 246, 70))
    glow1 = glow1.filter(ImageFilter.GaussianBlur(120))
    
    # Create radial gradient glow bottom-right (magenta)
    glow2 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(glow2)
    d2.ellipse((width - 600, height - 500, width + 200, height + 300), fill=(236, 72, 153, 60))
    glow2 = glow2.filter(ImageFilter.GaussianBlur(130))

    # Create center glow (blue)
    glow3 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(glow3)
    d3.ellipse((300, 100, 900, 600), fill=(59, 130, 246, 40))
    glow3 = glow3.filter(ImageFilter.GaussianBlur(100))

    base = Image.alpha_composite(base, glow1)
    base = Image.alpha_composite(base, glow2)
    base = Image.alpha_composite(base, glow3)
    return base

def draw_icon_on_image(draw, x, y, size):
    # Draw simplified glowing play triangle icon
    p1 = (x, y)
    p2 = (x + size, y + size // 2)
    p3 = (x, y + size)
    draw.polygon([p1, p2, p3], fill=(236, 72, 153, 255))

def create_og_image(output_path):
    width, height = 1200, 630
    img = draw_gradient_background(width, height)
    draw = ImageDraw.Draw(img)

    # Draw sleek card container
    card_margin = 60
    card_box = [card_margin, card_margin, width - card_margin, height - card_margin]
    
    card_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(card_overlay)
    cdraw.rounded_rectangle(card_box, radius=32, fill=(19, 21, 31, 200), outline=(139, 92, 246, 100), width=2)
    img = Image.alpha_composite(img, card_overlay)
    draw = ImageDraw.Draw(img)

    # Try loading default font or fallback
    try:
        title_font = ImageFont.truetype("arial.ttf", 68)
        subtitle_font = ImageFont.truetype("arial.ttf", 28)
        badge_font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        badge_font = ImageFont.load_default()

    # Draw Pill Badge
    badge_box = [110, 110, 360, 152]
    badge_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge_overlay)
    bdraw.rounded_rectangle(badge_box, radius=20, fill=(139, 92, 246, 40), outline=(168, 85, 247, 180), width=1)
    img = Image.alpha_composite(img, badge_overlay)
    draw = ImageDraw.Draw(img)

    draw.text((130, 120), "AI STORY-TO-VIDEO ENGINE", fill=(216, 180, 254), font=badge_font)

    # Brand Title: omaishort
    draw.text((110, 180), "omaishort", fill=(255, 255, 255), font=title_font)

    # Tagline / Subtitle
    draw.text((110, 275), "Turn scripts, news URLs, and topics into", fill=(226, 232, 240), font=subtitle_font)
    draw.text((110, 315), "1080×1920 videos with AI voiceover & captions", fill=(244, 114, 182), font=subtitle_font)

    # Feature Pills
    features = ["Local-First & Free", "Character Bible", "5-Beat Storytelling", "Karaoke Captions"]
    fx = 110
    fy = 420
    for feat in features:
        bw = len(feat) * 13 + 30
        pbox = [fx, fy, fx + bw, fy + 44]
        p_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        pdraw = ImageDraw.Draw(p_overlay)
        pdraw.rounded_rectangle(pbox, radius=12, fill=(30, 41, 59, 180), outline=(71, 85, 105, 150), width=1)
        img = Image.alpha_composite(img, p_overlay)
        draw = ImageDraw.Draw(img)
        draw.text((fx + 15, fy + 10), feat, fill=(203, 213, 225), font=badge_font)
        fx += bw + 16

    # Draw 9:16 Mock Phone Frame on Right Side
    phone_x1, phone_y1 = 820, 100
    phone_x2, phone_y2 = 1040, 530
    phone_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(phone_overlay)
    pdraw.rounded_rectangle([phone_x1, phone_y1, phone_x2, phone_y2], radius=24, fill=(15, 23, 42, 230), outline=(236, 72, 153, 160), width=3)
    
    # Phone screen content (subtitles & play button)
    pdraw.polygon([(905, 290), (965, 325), (905, 360)], fill=(244, 114, 182, 220))
    pdraw.rounded_rectangle([840, 440, 1020, 480], radius=8, fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, phone_overlay)
    draw = ImageDraw.Draw(img)
    draw.text((855, 452), "OMAISHORT ENGINE", fill=(255, 255, 255), font=badge_font)

    # Save
    img.save(output_path, "PNG")
    print(f"Created OG Image: {output_path}")

def create_png_favicon(output_path, size=64):
    img = draw_gradient_background(size, size)
    draw = ImageDraw.Draw(img)
    # Draw simple play icon
    margin = size // 4
    draw.polygon([(margin + 4, margin), (size - margin + 4, size // 2), (margin + 4, size - margin)], fill=(255, 255, 255, 230))
    img.save(output_path, "PNG")
    print(f"Created PNG favicon ({size}x{size}): {output_path}")

if __name__ == '__main__':
    public_dir = os.path.join(os.path.dirname(__file__), '..', 'apps', 'web', 'public')
    os.makedirs(public_dir, exist_ok=True)
    
    create_svg_favicon(os.path.join(public_dir, 'favicon.svg'))
    create_png_favicon(os.path.join(public_dir, 'favicon.png'), 64)
    create_png_favicon(os.path.join(public_dir, 'apple-touch-icon.png'), 180)
    create_og_image(os.path.join(public_dir, 'og-image.png'))
