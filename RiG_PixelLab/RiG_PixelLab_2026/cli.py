"""Command line version of the same converter. Ideal for automation and tests."""
from __future__ import annotations
import argparse
from pathlib import Path
from pixel_engine import Settings,create_all,export_all,open_local_image


def main()->None:
    parser=argparse.ArgumentParser(description="RiG++ PixelLab batch PNG exporter")
    parser.add_argument("input",type=Path,help="Input image (PNG/JPEG/WebP/BMP)")
    parser.add_argument("--out",type=Path,default=Path("outputs"),help="Folder in which to create an output folder")
    parser.add_argument("--pixel-width",type=int,default=105)
    parser.add_argument("--colors",type=int,default=32)
    parser.add_argument("--bg-brightness",type=int,default=100)
    parser.add_argument("--bg-tolerance",type=int,default=46)
    parser.add_argument("--dither",action="store_true")
    parser.add_argument("--no-background-removal",action="store_true")
    args=parser.parse_args()
    cfg=Settings(pixel_width=args.pixel_width,colors=args.colors,dither=args.dither,
                 bg_brightness=args.bg_brightness,bg_tolerance=args.bg_tolerance,
                 remove_bg=not args.no_background_removal)
    im=open_local_image(args.input)
    result=create_all(im,cfg)
    dest=export_all(im,result,cfg,args.out,args.input.stem)
    print(f"[OK] Saved: {dest}")
    print(f"[INFO] Sprite: {result['sprite_note']}")

if __name__=="__main__":
    main()
