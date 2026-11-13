"""Pure-Pillow conversion engine for RiG++ PixelLab.

No webcam, web API or machine-learning service required. Images stay local.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import math
import re

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


@dataclass(frozen=True)
class Settings:
    pixel_width: int = 80
    colors: int = 24
    dither: bool = False
    bg_brightness: int = 90  # percent; no darkening by default
    sprite_size: int = 128
    tile_size: int = 64
    remove_bg: bool = True
    bg_tolerance: int = 46
    background_size: tuple[int, int] = (960, 540)
    scene_style: str = "adventure"

    def validate(self) -> None:
        if not 8 <= self.pixel_width <= 256:
            raise ValueError("pixel_width must be between 8 and 256")
        if not 2 <= self.colors <= 256:
            raise ValueError("colors must be between 2 and 256")
        if not 40 <= self.bg_brightness <= 125:
            raise ValueError("bg_brightness must be 40-125")
        if self.scene_style not in ("adventure","sunset","night"):
            raise ValueError("scene_style is invalid")
        if self.sprite_size not in (32, 64, 96, 128, 256):
            raise ValueError("sprite_size must be 32/64/96/128/256")
        if self.tile_size not in (32, 64, 128):
            raise ValueError("tile_size must be 32/64/128")
        if not 5 <= self.bg_tolerance <= 130:
            raise ValueError("bg_tolerance must be 5-130")
        if any(not 128 <= x <= 2048 for x in self.background_size):
            raise ValueError("background_size out of range")


def open_local_image(path: Path | str) -> Image.Image:
    with Image.open(path) as im:
        if im.width * im.height > 60_000_000:
            raise ValueError("画像が大きすぎます（最大6000万画素）。小さくしてから選んでください。")
        im = ImageOps.exif_transpose(im)
        im.load()
        return im.convert("RGBA")


def cap_source(im: Image.Image, limit: int = 1600) -> Image.Image:
    out = im.copy().convert("RGBA")
    out.thumbnail((limit, limit), Image.Resampling.LANCZOS)
    return out


def reduce_colors(im: Image.Image, colors: int, dither: bool) -> Image.Image:
    """Quantize RGB, restore alpha so transparent images remain usable assets."""
    alpha = im.getchannel("A") if im.mode == "RGBA" else None
    rgb = im.convert("RGB")
    pal = rgb.quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE,
    ).convert("RGB")
    if alpha is not None and alpha.getextrema()[0] < 255:
        pal.putalpha(alpha)
    return pal


def pixelate(im: Image.Image, width: int, colors: int, dither: bool, target: tuple[int,int] | None = None) -> Image.Image:
    if target is not None:
        im = im.resize(target, Image.Resampling.LANCZOS)
    w, h = im.size
    low_w = min(max(1, width), w)
    low_h = max(1, round(h * low_w / w))
    small = im.resize((low_w, low_h), Image.Resampling.BOX)
    reduced = reduce_colors(small, colors, dither)
    return reduced.resize((w, h), Image.Resampling.NEAREST)


def ordinary(im: Image.Image, cfg: Settings) -> Image.Image:
    return pixelate(cap_source(im), cfg.pixel_width, cfg.colors, cfg.dither)


def _tone_grade(low: Image.Image, style: str, brightness: float) -> Image.Image:
    """Colour direction on pixel grid (no external AI/model dependency)."""
    import colorsys

    rgb = low.convert("RGB")
    colors = []
    # Grade on LOW resolution so the effect also respects pixel boundaries.
    pixels = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
    for r, g, b in pixels:
        h, sat, value = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        if style == "adventure":
            sat = min(1, sat*1.32 + .045)
            value = min(1, max(0, (value-.5)*1.16+.56)*brightness)
        elif style == "sunset":
            # Golden hour: navy shadows, warm highlights, retained image detail.
            value = min(1, max(0, (value-.5)*1.12+.53)*brightness)
            r = min(255, int((r*.95 + value*43 + 12)*brightness))
            g = min(255, int((g*.79 + value*22)*brightness))
            b = min(255, int((b*.75 + (1-value)*33)*brightness))
            colors.append((r,g,b))
            continue
        else:  # night: cool blue hour, not simply a black filter
            value = min(1, max(0,value*.64+.10)*brightness)
            r = min(255, int(r*.48*brightness+8))
            g = min(255, int(g*.75*brightness+18))
            b = min(255, int((b*.94+35)*brightness))
            colors.append((r,g,b))
            continue
        colors.append(tuple(int(c*255) for c in colorsys.hsv_to_rgb(h,sat,value)))
    graded = Image.new("RGB", low.size)
    graded.putdata(colors)
    return graded


def game_background(im: Image.Image, cfg: Settings, style: str | None = None) -> Image.Image:
    """Transform a real photo into a coherent 16:9 pixel-game BACKGROUND.

    No HUD/characters; the photo content remains recognizable. All grading
    happens at low resolution and is then nearest-neighbour enlarged.
    """
    style = style or cfg.scene_style
    if style not in ("adventure","sunset","night"):
        raise ValueError("Unknown scene style")
    w,h=cfg.background_size
    source=ImageOps.fit(im.convert("RGB"),(w,h),method=Image.Resampling.LANCZOS)
    source=ImageEnhance.Contrast(source).enhance(1.22)
    source=ImageEnhance.Color(source).enhance(1.18)
    source=source.filter(ImageFilter.UnsharpMask(radius=1.6,percent=110,threshold=4))
    # Fine pixels make photographs recognisable; coarse settings are still user-selectable.
    low_w=max(48, min(w, cfg.pixel_width*2))
    low_h=max(1,round(h*low_w/w))
    low=source.resize((low_w,low_h),Image.Resampling.BOX)
    low=_tone_grade(low,style,cfg.bg_brightness/100)
    low=reduce_colors(low, min(cfg.colors*2,96),cfg.dither).convert("RGB")
    return low.resize((w,h),Image.Resampling.NEAREST)

def _corner_color(rgb: Image.Image, tolerance: int) -> tuple[int, int, int] | None:
    """Only use automatic removal when all corners appear to be one flat color."""
    w, h = rgb.size
    cx = max(0, min(w - 1, w // 40))
    cy = max(0, min(h - 1, h // 40))
    pts = [(cx,cy),(w-1-cx,cy),(cx,h-1-cy),(w-1-cx,h-1-cy)]
    samples = [rgb.getpixel(p) for p in pts]
    mean = tuple(round(sum(p[k] for p in samples) / 4) for k in range(3))
    if any(sum((p[k]-mean[k])**2 for k in range(3)) > (min(34,tolerance))**2 for p in samples):
        return None
    # Real photographs often share dark corners while having a highly varied
    # edge. Do not mistake such a photo for an object on a plain background.
    border = []
    for i in range(20):
        x = round(i * (w - 1) / 19)
        y = round(i * (h - 1) / 19)
        border.extend((rgb.getpixel((x,0)),rgb.getpixel((x,h-1)),
                       rgb.getpixel((0,y)),rgb.getpixel((w-1,y))))
    limit = max(18, min(42, tolerance)) ** 2
    close = sum(sum((p[k]-mean[k])**2 for k in range(3)) <= limit for p in border)
    if close < len(border)*0.88:
        return None
    return mean


def _flood_background(rgb: Image.Image, color: tuple[int,int,int], tol: int) -> Image.Image:
    """Remove only edge-connected pixels near corner color; preserves foreground islands."""
    w, h = rgb.size
    pixels = rgb.load()
    alpha = Image.new("L", (w, h), 255)
    aa = alpha.load()
    visits = bytearray(w*h)
    queue: deque[tuple[int,int]] = deque()
    threshold = tol * tol
    def near(x: int, y: int) -> bool:
        p = pixels[x,y]
        return sum((int(p[k])-color[k])**2 for k in range(3)) <= threshold
    def attempt(x:int,y:int) -> None:
        pos = y*w+x
        if not visits[pos]:
            visits[pos]=1
            if near(x,y):
                aa[x,y]=0
                queue.append((x,y))
    for x in range(w):
        attempt(x,0)
        attempt(x,h-1)
    for y in range(h):
        attempt(0,y)
        attempt(w-1,y)
    while queue:
        x,y=queue.popleft()
        if x>0: attempt(x-1,y)
        if x<w-1: attempt(x+1,y)
        if y>0: attempt(x,y-1)
        if y<h-1: attempt(x,y+1)
    return alpha


def game_sprite(im: Image.Image, cfg: Settings) -> tuple[Image.Image,str]:
    """Game sprite PNG with transparent padding; conservative background removal."""
    im = cap_source(im, 520)
    alpha = im.getchannel("A")
    note = "元の透過情報を使用"
    if alpha.getextrema()[0] == 255:
        note = "背景透過なし（複雑な写真では通常の四角い画像になります）"
        if cfg.remove_bg:
            corner = _corner_color(im.convert("RGB"), cfg.bg_tolerance)
            if corner is not None:
                alpha = _flood_background(im.convert("RGB"),corner,cfg.bg_tolerance)
                if alpha.getbbox():
                    note = "単色背景を自動透過（端からつながる近似色のみ）"
    working=im.copy()
    working.putalpha(alpha)
    bbox=alpha.getbbox()
    if bbox:
        working=working.crop(bbox)
    size=cfg.sprite_size
    pad=max(2, round(size*0.08))
    max_inner=size-2*pad
    ratio=min(max_inner/working.width, max_inner/working.height)
    target=(max(1,round(working.width*ratio)),max(1,round(working.height*ratio)))
    # Pixelize before placing, preserving transparent pixels.
    low_w=max(1, min(target[0], max(6, round(target[0]/8))))
    low_h=max(1,round(target[1]*low_w/target[0]))
    tiny=working.resize((low_w,low_h), Image.Resampling.BOX)
    q=reduce_colors(tiny, min(cfg.colors,32),cfg.dither)
    pixel=q.resize(target, Image.Resampling.NEAREST).convert("RGBA")
    out=Image.new("RGBA",(size,size),(0,0,0,0))
    out.alpha_composite(pixel,((size-target[0])//2,(size-target[1])//2))
    return out,note


def seamless_tile(im: Image.Image, cfg: Settings) -> Image.Image:
    """A deliberately mirrored tile whose opposite edges match without seams."""
    n=cfg.tile_size
    sq=ImageOps.fit(im.convert("RGB"),(n,n), method=Image.Resampling.LANCZOS)
    half=math.ceil(n/2)
    base=sq.resize((half,half),Image.Resampling.BOX)
    base=reduce_colors(base,min(cfg.colors,64),cfg.dither).convert("RGB")
    tile=Image.new("RGB",(n,n))
    src=base.load(); dest=tile.load()
    for y in range(n):
        ysrc=min(y,n-1-y)
        for x in range(n):
            dest[x,y]=src[min(x,n-1-x),ysrc]
    # The mirrored color-limited base keeps opposing borders identical even with dithering.
    return tile


def tile_preview(tile: Image.Image, columns:int=4, rows:int=3, cell:int=96) -> Image.Image:
    base=tile.resize((cell,cell),Image.Resampling.NEAREST).convert("RGB")
    output=Image.new("RGB",(cell*columns,cell*rows))
    for y in range(rows):
        for x in range(columns):
            output.paste(base,(x*cell,y*cell))
    return output


def checkerboard(size:tuple[int,int], grid:int=14) -> Image.Image:
    out=Image.new("RGB",size,(238,241,246))
    d=ImageDraw.Draw(out)
    w,h=size
    for y in range(0,h,grid):
        for x in range(0,w,grid):
            if ((x//grid)+(y//grid))%2:
                d.rectangle((x,y,x+grid-1,y+grid-1),fill=(193,202,215))
    return out


def sprite_preview(sprite:Image.Image, display:int=300) -> Image.Image:
    bg=checkerboard((display,display))
    fg=sprite.resize((display,display), Image.Resampling.NEAREST)
    bg.paste(fg,(0,0),fg)
    return bg


def _pixel_hero(size: int = 96) -> Image.Image:
    """Original built-in sample character; never claims to extract subjects from a landscape."""
    unit = 4
    im=Image.new("RGBA",(24,24),(0,0,0,0))
    d=ImageDraw.Draw(im)
    # cape/shadow, shoes, tunic, head, hair, face, eyes
    d.polygon([(6,7),(18,7),(22,21),(3,21)],fill=(28,52,87,255))
    d.rectangle((7,18,11,22),fill=(32,40,65,255))
    d.rectangle((13,18,17,22),fill=(32,40,65,255))
    d.rectangle((6,20,11,22),fill=(16,28,43,255))
    d.rectangle((13,20,18,22),fill=(16,28,43,255))
    d.rectangle((6,10,18,19),fill=(16,34,50,255))
    d.rectangle((7,11,17,18),fill=(41,201,185,255))
    d.rectangle((9,13,15,17),fill=(83,237,210,255))
    d.rectangle((6,10,8,15),fill=(253,205,149,255))
    d.rectangle((17,10,19,15),fill=(253,205,149,255))
    d.rectangle((8,4,16,11),fill=(24,39,60,255))
    d.rectangle((9,5,15,10),fill=(255,207,144,255))
    d.rectangle((8,3,16,6),fill=(39,48,65,255))
    d.rectangle((7,5,10,8),fill=(39,48,65,255))
    d.rectangle((10,8,10,8),fill=(35,34,43,255))
    d.rectangle((14,8,14,8),fill=(35,34,43,255))
    d.rectangle((16,4,17,6),fill=(24,39,60,255))
    return im.resize((size,size),Image.Resampling.NEAREST)


def game_screen_demo(background: Image.Image, sprite:Image.Image|None=None) -> Image.Image:
    """A designed side-scrolling game mock-up, not a playable game.

    Independent foreground/platforms and interactive motifs make the difference
    between just pixelating a photo and presenting it as a playable level.
    """
    im=background.convert("RGB").copy()
    w,h=im.size
    # Render UI/foreground at pixel-grid resolution then scale with NEAREST.
    scale=4
    sw,sh=w//scale,h//scale
    stage=im.resize((sw,sh),Image.Resampling.NEAREST).convert("RGBA")
    d=ImageDraw.Draw(stage,"RGBA")
    # Atmospheric fade behind ground, retain the original photograph above it.
    d.rectangle((0,sh-29,sw,sh),fill=(11,31,44,130))
    # Rugged, patterned ground with a clear playable baseline.
    d.rectangle((0,sh-16,sw,sh),fill=(19,43,60,255))
    d.rectangle((0,sh-18,sw,sh-16),fill=(87,198,131,255))
    for x in range(0,sw,7):
        d.rectangle((x,sh-15,x+3,sh-14),fill=(37,81,91,255))
        if x%3: d.rectangle((x+2,sh-7,x+5,sh-6),fill=(30,65,80,255))
    # Floating platforms, shadows, and small collectibles.
    for x,y,pw in ((16,80,42),(114,68,43),(190,90,40)):
        d.rectangle((x+2,y+3,x+pw+2,y+8),fill=(10,21,41,145))
        d.rectangle((x,y,x+pw,y+3),fill=(40,77,104,255))
        d.rectangle((x,y,x+pw,y+1),fill=(141,230,160,255))
        for px in range(x+7,x+pw-1,12): d.rectangle((px,y+2,px+2,y+4),fill=(61,110,112,255))
    for x,y in ((46,70),(148,58),(215,79)):
        d.ellipse((x-4,y-4,x+4,y+4),fill=(248,198,80,255),outline=(254,236,166,255),width=1)
        d.rectangle((x,y-2,x+1,y+2),fill=(255,255,215,255))
    # small sprite and soft ground shadow
    d.ellipse((115,sh-22,131,sh-18),fill=(2,14,24,150))
    hero = _pixel_hero(28) if sprite is None else sprite.resize((28,28),Image.Resampling.NEAREST)
    stage.alpha_composite(hero,(111,sh-45))
    # Transparent HUD with pixel borders and shadows.
    d.rounded_rectangle((5,5,80,25),radius=3,fill=(8,24,40,228),outline=(109,228,220,220),width=1)
    d.text((9,9),"SCORE  01280",font=_font(10,True),fill=(243,252,247,255))
    d.text((9,18),"HP  03/03",font=_font(8,True),fill=(157,240,183,255))
    d.rounded_rectangle((sw-63,5,sw-5,19),radius=3,fill=(8,24,40,225),outline=(109,228,220,220))
    d.text((sw-58,9),"STAGE 01",font=_font(8,True),fill=(244,249,252,255))
    return stage.resize((w,h),Image.Resampling.NEAREST).convert("RGB")


def create_all(im:Image.Image,cfg:Settings) -> dict[str,Any]:
    cfg.validate()
    regular=ordinary(im,cfg)
    bg=game_background(im,cfg)
    sunset=game_background(im,cfg,"sunset")
    night=game_background(im,cfg,"night")
    sprite,note=game_sprite(im,cfg)
    tile=seamless_tile(im,cfg)
    return {
        "normal":regular,
        "game_background":bg,
        "sunset_background":sunset,
        "night_background":night,
        "sprite":sprite,
        "built_in_hero":_pixel_hero(128),
        "tile":tile,
        "tile_repeat":tile_preview(tile),
        "game_demo":game_screen_demo(bg),
        "sprite_note":note,
    }


def _font(size:int, bold:bool=False) -> ImageFont.FreeTypeFont|ImageFont.ImageFont:
    fonts=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/meiryo.ttc",
    ]
    for f in fonts:
        try: return ImageFont.truetype(f,size)
        except OSError: pass
    return ImageFont.load_default()


def _fit_preview(img:Image.Image, w:int,h:int, mode:str="contain") -> Image.Image:
    if mode=="cover":
        return ImageOps.fit(img.convert("RGB"),(w,h),method=Image.Resampling.NEAREST)
    out=Image.new("RGB",(w,h),(229,234,241))
    image=img.convert("RGBA").copy()
    image.thumbnail((w-12,h-12), Image.Resampling.NEAREST)
    if image.getchannel('A').getextrema()[0] <255:
        checker=checkerboard(image.size)
        checker.paste(image,(0,0),image)
        image=checker.convert("RGBA")
    out.paste(image.convert('RGB'),((w-image.width)//2,(h-image.height)//2))
    return out


def comparison_sheet(source:Image.Image, result:dict[str,Any]) -> Image.Image:
    cell_w,cell_h=490,340
    margin,gap,head=48,22,110
    width=margin*2+3*cell_w+2*gap
    height=head+margin+3*cell_h+2*gap+margin
    sheet=Image.new("RGB",(width,height),(18,27,44))
    d=ImageDraw.Draw(sheet)
    d.text((margin,24),"RiG++ PIXEL LAB",font=_font(34,True),fill=(255,255,255))
    d.text((margin,68),"One image  /  Different game-ready results",font=_font(16),fill=(159,179,205))
    cards=[
       ("01  REAL PHOTO",source,"contain"),
       ("02  BASIC PIXELATE",result["normal"],"contain"),
       ("03  GAME BACKGROUND",result["game_background"],"cover"),
       ("04  SUNSET VARIANT",result["sunset_background"],"cover"),
       ("05  NIGHT VARIANT",result["night_background"],"cover"),
       ("06  GAME STAGE MOCKUP",result["game_demo"],"cover"),
       ("07  CHARACTER SAMPLE",result["built_in_hero"],"contain"),
       ("08  TILE REPEAT",result["tile_repeat"],"cover"),
    ]
    for i,(label,img,mode) in enumerate(cards):
        x=margin+(i%3)*(cell_w+gap)
        y=head+(i//3)*(cell_h+gap)
        d.rounded_rectangle((x,y,x+cell_w,y+cell_h),radius=16,fill=(34,48,69))
        d.text((x+18,y+11),label,font=_font(17,True),fill=(233,241,254))
        thumb=_fit_preview(img,cell_w-24,cell_h-56,mode)
        sheet.paste(thumb,(x+12,y+44))
    return sheet


def export_all(source:Image.Image,result:dict[str,Any],cfg:Settings,base_dir:Path|str,filename_stem:str) -> Path:
    base=Path(base_dir)
    base.mkdir(parents=True,exist_ok=True)
    safe=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",filename_stem).strip(" .")[:40] or "photo"
    parent=base/(safe+"_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
    out=parent
    attempt=1
    while out.exists():
        out=Path(str(parent)+f"_{attempt}")
        attempt+=1
    out.mkdir()
    mapped={
       "normal":"01_normal_pixel_art.png",
       "game_background":"02_game_background_960x540.png",
       "sunset_background":"03_game_background_sunset.png",
       "night_background":"04_game_background_night.png",
       "built_in_hero":"08_builtin_pixel_hero.png",
       "sprite":"07_photo_sprite_only_for_plain_background.png",
       "tile":"09_seamless_tile.png",
       "tile_repeat":"10_repeating_tile_preview.png",
       "game_demo":"05_game_stage_mockup.png",
    }
    for k,name in mapped.items():
        result[k].save(out/name)
    comparison_sheet(source,result).save(out/"00_before_after_comparison.png")
    meta=asdict(cfg)
    meta["sprite_auto_detection"]=result["sprite_note"]
    meta["note"]="Game stage is an illustrative mockup, not a playable game. Photo-derived sprite only works for simple backgrounds. No semantic/AI segmentation."
    (out/"settings.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    return out
