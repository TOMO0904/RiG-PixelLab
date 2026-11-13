import unittest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image,ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pixel_engine import Settings, ordinary, game_background, game_sprite, seamless_tile, tile_preview, create_all, export_all, open_local_image

class TestPixelLab(unittest.TestCase):
    def setUp(self):
        self.cfg=Settings()
        self.image=Image.new("RGB",(300,200),(100,160,200))
        d=ImageDraw.Draw(self.image)
        d.rectangle((90,45,210,155),fill=(250,80,70))

    def test_normal_keeps_canvas_size(self):
        self.assertEqual(ordinary(self.image,self.cfg).size,(300,200))

    def test_normal_uses_limited_palette(self):
        a=ordinary(self.image,Settings(pixel_width=50,colors=4))
        self.assertLessEqual(len(a.convert('RGB').getcolors(300*200)),4)

    def test_background_is_game_size(self):
        self.assertEqual(game_background(self.image,self.cfg).size,(960,540))

    def test_dark_background_is_darker(self):
        a=game_background(self.image,Settings(bg_brightness=40))
        b=game_background(self.image,Settings(bg_brightness=90))
        self.assertLess(sum(a.getpixel((300,250))),sum(b.getpixel((300,250))))

    def test_sprite_is_png_transparency_compatible(self):
        out,note=game_sprite(self.image,self.cfg)
        self.assertEqual(out.mode,'RGBA')
        self.assertEqual(out.size,(128,128))
        self.assertEqual(out.getpixel((0,0))[3],0)
        self.assertIn('透過',note)

    def test_plain_background_removed_not_subject(self):
        out,note=game_sprite(self.image,self.cfg)
        alphas=list(out.getchannel('A').get_flattened_data())
        self.assertGreater(sum(a>50 for a in alphas),100)
        self.assertGreater(sum(a==0 for a in alphas),100)
        self.assertIn('自動透過',note)

    def test_colorful_corners_not_auto_removed(self):
        im=Image.new('RGB',(160,160),'white')
        dr=ImageDraw.Draw(im)
        for box,color in [((0,0,20,20),'red'),((139,0,159,20),'green'),((0,139,20,159),'blue'),((139,139,159,159),'yellow')]:
            dr.rectangle(box,fill=color)
        _,note=game_sprite(im,self.cfg)
        self.assertIn('背景透過なし',note)

    def test_existing_alpha_preserved_as_alpha_sprite(self):
        im=Image.new('RGBA',(110,130),(0,0,0,0))
        ImageDraw.Draw(im).ellipse((25,30,90,100),fill=(250,30,80,255))
        out,note=game_sprite(im,self.cfg)
        self.assertIn('元の透過',note)
        self.assertEqual(out.getpixel((0,0))[3],0)
        self.assertGreater(out.getchannel('A').getbbox()[2],0)

    def test_seamless_tile_all_edges_match(self):
        for dither in (False,True):
            tile=seamless_tile(self.image,Settings(dither=dither))
            for n in range(tile.height):
                self.assertEqual(tile.getpixel((0,n)),tile.getpixel((tile.width-1,n)))
            for n in range(tile.width):
                self.assertEqual(tile.getpixel((n,0)),tile.getpixel((n,tile.height-1)))

    def test_tile_repeat_size(self):
        tile=seamless_tile(self.image,self.cfg)
        self.assertEqual(tile.size,(64,64))
        self.assertEqual(tile_preview(tile).size,(384,288))

    def test_all_outputs(self):
        result=create_all(self.image,self.cfg)
        self.assertEqual(set(result),{'normal','game_background','sunset_background','night_background','sprite','built_in_hero','tile','tile_repeat','game_demo','sprite_note'})

    def test_exported_files_exist(self):
        with TemporaryDirectory() as tmp:
            images=create_all(self.image,self.cfg)
            out=export_all(self.image,images,self.cfg,tmp,'test source')
            self.assertEqual(len(list(out.glob('*.png'))),10)
            self.assertTrue((out/'settings.json').exists())
            with Image.open(out/'07_photo_sprite_only_for_plain_background.png') as saved:
                self.assertEqual(saved.mode,'RGBA')

    def test_photo_background_variants_are_distinct(self):
        result=create_all(self.image,self.cfg)
        for key in ('game_background','sunset_background','night_background'):
            self.assertEqual(result[key].size,(960,540))
        self.assertNotEqual(result['game_background'].tobytes(),result['sunset_background'].tobytes())
        self.assertNotEqual(result['sunset_background'].tobytes(),result['night_background'].tobytes())

    def test_game_mockup_is_not_same_as_background(self):
        result=create_all(self.image,self.cfg)
        self.assertNotEqual(result['game_demo'].tobytes(), result['game_background'].tobytes())
        self.assertEqual(result['game_demo'].size,(960,540))

    def test_builtin_hero_is_transparent_sprite(self):
        hero=create_all(self.image,self.cfg)['built_in_hero']
        self.assertEqual(hero.mode,'RGBA')
        self.assertEqual(hero.size,(128,128))
        self.assertEqual(hero.getpixel((0,0))[3],0)
        self.assertGreater(hero.getchannel('A').getbbox()[2],0)

    def test_real_photo_not_false_cutout(self):
        sample = Path(__file__).resolve().parents[1]/'samples'/'sample_real_rocket.jpg'
        source = open_local_image(sample)
        _, note = game_sprite(source, self.cfg)
        self.assertIn('背景透過なし',note)

    def test_japanese_unicode_file_name(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'秋の画像_１.png'
            self.image.save(path)
            loaded=open_local_image(path)
            self.assertEqual(loaded.size,self.image.size)

    def test_settings_validation(self):
        with self.assertRaises(ValueError):
            Settings(colors=257).validate()

    def test_large_image_aspect_ratio_preserved(self):
        img=Image.new('RGB',(1800,600),(100,200,100))
        out=ordinary(img,self.cfg)
        self.assertEqual(out.size,(1600,533))

if __name__=='__main__':
    unittest.main()
