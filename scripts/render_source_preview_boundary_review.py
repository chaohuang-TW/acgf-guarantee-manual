import json
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

def calculate_scaled_size(original_width, original_height, max_w, max_h):
    scale = min(max_w / original_width, max_h / original_height, 1.0)
    return round(original_width * scale), round(original_height * scale)

def render_review(output_path, title, pdf_pages):
    imgs = []
    labels = []
    
    for n in pdf_pages:
        p = ROOT / f"assets/page-previews/115-04/pdf-page-{n:03d}.webp"
        if p.exists():
            imgs.append(Image.open(p).convert("RGB"))
            labels.append(f"PDF {n}")
        else:
            imgs.append(None)
            labels.append(f"PDF {n} (MISSING)")
            
    MAX_W = 400
    MAX_H = 600
    
    cell_w = MAX_W + 10
    cell_h = MAX_H + 100
    
    canvas_w = max(cell_w * len(pdf_pages) + 10, 800)
    canvas_h = cell_h
    
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(canvas)
    
    draw.text((20, 20), title, fill="black")
    
    for i, img in enumerate(imgs):
        x = 10 + i * cell_w
        y = 80
        if img:
            new_w, new_h = calculate_scaled_size(img.width, img.height, MAX_W, MAX_H)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            offset_x = x + (MAX_W - new_w) // 2
            offset_y = y + (MAX_H - new_h) // 2
            canvas.paste(img, (offset_x, offset_y))
            draw.text((x, 60), labels[i], fill="blue")
        else:
            draw.text((x, 60), labels[i], fill="red")
            
    canvas.save(output_path, "PDF", resolution=100.0)
    print(f"Generated {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--pages", type=int, nargs='+', required=True)
    parser.add_argument("--title", type=str, default="Visual Review")
    args = parser.parse_args()
    
    render_review(Path(args.out), args.title, args.pages)

if __name__ == "__main__":
    main()
