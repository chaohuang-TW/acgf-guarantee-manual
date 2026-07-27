import json
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

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
            
    resize_w = 400
    resize_h = int(resize_w * 1.414)
    
    canvas_w = max((resize_w + 10) * len(pdf_pages) + 10, 800)
    canvas_h = resize_h + 100
    
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(canvas)
    
    draw.text((20, 20), title, fill="black")
    
    for i, img in enumerate(imgs):
        x = 10 + i * (resize_w + 10)
        y = 80
        if img:
            img = img.resize((resize_w, resize_h))
            canvas.paste(img, (x, y))
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
