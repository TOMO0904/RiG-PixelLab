"""Japanese beginner-friendly desktop app. Run: python app.py"""
from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from pixel_engine import (
    Settings, checkerboard, comparison_sheet, create_all, export_all,
    open_local_image, sprite_preview,
)

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except (ImportError, OSError):
    TkinterDnD = None
    DND_FILES = None

ROOT = Path(__file__).resolve().parent
BACKGROUND = "#0d1628"
PANEL = "#1d2a40"
PANEL2 = "#263852"
FG = "#f5f8ff"
DIM = "#b0c0d8"
GREEN = "#82e3b9"
BLUE = "#69b7ff"


class PixelLabApp:
    def __init__(self, root:tk.Tk, dnd:bool):
        self.root=root
        self.dnd=dnd
        self.root.title("RiG++ PixelLab | 写真からゲーム素材を作ろう")
        self.root.geometry("1320x940")
        self.root.minsize(1060,760)
        self.root.configure(bg=BACKGROUND)
        self.source:Image.Image|None=None
        self.source_path:Path|None=None
        self.results:dict|None=None
        self.refs:dict[str,ImageTk.PhotoImage]={}
        self.labels:dict[str,tk.Label]={}
        self.original_images:dict[str,Image.Image]={}
        self.after_job:str|None=None
        self.pixel=tk.IntVar(value=105)
        self.colors=tk.IntVar(value=32)
        self.brightness=tk.IntVar(value=100)
        self.tolerance=tk.IntVar(value=46)
        self.dither=tk.BooleanVar(value=False)
        self.remove_bg=tk.BooleanVar(value=True)
        self.status=tk.StringVar(value="写真を選ぶか、サンプルを開いてください")
        self.note=tk.StringVar(value="")

        # Everything (upload area, settings, results and footer) lives in one
        # vertical scrolling document. No fixed top area or nested results scroll.
        self.page_canvas = tk.Canvas(self.root, bg=BACKGROUND, highlightthickness=0, borderwidth=0)
        self.page_scroll = ttk.Scrollbar(self.root, orient="vertical", command=self.page_canvas.yview)
        self.page_canvas.configure(yscrollcommand=self.page_scroll.set)
        self.page_scroll.pack(side="right", fill="y")
        self.page_canvas.pack(side="left", fill="both", expand=True)
        self.page = tk.Frame(self.page_canvas, bg=BACKGROUND)
        self.page_window = self.page_canvas.create_window((0, 0), window=self.page, anchor="nw")
        self.page.bind("<Configure>", self._update_scrollregion)
        self.page_canvas.bind("<Configure>", self._resize_page)
        # Wheel works over every control and every preview, not just the images.
        self.root.bind_all("<MouseWheel>", self._wheel, add="+")
        self.root.bind_all("<Button-4>", self._wheel_linux, add="+")
        self.root.bind_all("<Button-5>", self._wheel_linux, add="+")
        self.root.bind_all("<Prior>", self._page_key, add="+")
        self.root.bind_all("<Next>", self._page_key, add="+")
        self.root.bind_all("<Home>", self._page_key, add="+")
        self.root.bind_all("<End>", self._page_key, add="+")

        self._build()
        for var in (self.pixel,self.colors,self.brightness,self.tolerance,self.dither,self.remove_bg):
            var.trace_add("write",self.schedule_refresh)
        self.root.after(150,lambda:self.load_image(ROOT/"samples"/"sample_real_rocket.jpg"))

    def _button(self,parent,text,command,accent=False):
        return tk.Button(parent,text=text,command=command,cursor="hand2",font=("Yu Gothic UI",10,"bold"),
                         bg=BLUE if accent else PANEL2,fg="#0a1830" if accent else FG,
                         activebackground=GREEN if accent else "#3a516f",
                         activeforeground="#0a1830" if accent else FG,
                         padx=13,pady=9,relief="flat",borderwidth=0)

    def _label(self,parent,text,sz=11,color=FG,bold=False):
        return tk.Label(parent,text=text,bg=parent.cget("bg"),fg=color,
            font=("Yu Gothic UI",sz,"bold" if bold else "normal"),justify="left",anchor="w")

    def _build(self):
        header=tk.Frame(self.page,bg=BACKGROUND)
        header.pack(fill="x",padx=28,pady=(23,11))
        self._label(header,"RiG++ PIXEL LAB",23,FG,True).pack(anchor="w")
        self._label(header,"実写写真を選ぶ → ドット絵化 → ゲーム向け背景へ。昼・夕暮れ・夜と実際の配置例を比較できます。",11,DIM).pack(anchor="w",pady=(4,0))

        top=tk.Frame(self.page,bg=PANEL)
        top.pack(fill="x",padx=28,pady=(0,10))
        drop=tk.Frame(top,bg=PANEL,padx=14,pady=12)
        drop.pack(side="left",fill="both",expand=True)
        self.drop_label=tk.Label(drop,text="📂 ここへ画像をドラッグ＆ドロップ\nまたは［画像を選ぶ］をクリック",bg=PANEL,fg=FG,
            font=("Yu Gothic UI",12,"bold"),pady=5,justify="center")
        self.drop_label.pack(fill="both",expand=True)
        if self.dnd:
            for widget in (drop,self.drop_label):
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind("<<Drop>>",self._on_drop)
                except Exception:
                    self.dnd=False
            self._label(drop,"画像のドラッグ＆ドロップ対応（JPEG / PNG / WebP など）",9,GREEN).pack()
        else:
            self._label(drop,"ファイル選択に対応。ドラッグ＆ドロップは追加機能です。",9,DIM).pack()
        buttons=tk.Frame(top,bg=PANEL)
        buttons.pack(side="right",padx=(6,20),pady=10)
        self._button(buttons,"画像を選ぶ",self.select_file,True).pack(fill="x",pady=3)
        self._button(buttons,"実写サンプル",lambda:self.load_image(ROOT/"samples"/"sample_real_rocket.jpg")).pack(fill="x",pady=3)

        settings=tk.Frame(self.page,bg=PANEL,padx=16,pady=10)
        settings.pack(fill="x",padx=28,pady=(0,8))
        self._label(settings,"変換オプション  ｜  数値を変えると自動でプレビュー更新",10,GREEN,True).pack(anchor="w",pady=(0,3))
        presets=tk.Frame(settings,bg=PANEL)
        presets.pack(anchor="w",pady=(0,6))
        self._label(presets,"おすすめ設定：",9,DIM).pack(side="left",padx=(0,7))
        for text,pw,colors,bg in (("レトロ風",60,16,95),("ゲーム向け",105,32,100),("細かめ",160,48,106)):
            tk.Button(presets,text=text,command=lambda x=pw,y=colors,z=bg:self.apply_preset(x,y,z),
                bg=PANEL2,fg=FG,activebackground="#3a516f",activeforeground=FG,
                font=("Yu Gothic UI",9),relief="flat",padx=12,pady=4,cursor="hand2").pack(side="left",padx=(0,6))
        bar=tk.Frame(settings,bg=PANEL)
        bar.pack(fill="x")
        controls=[("ドットの細かさ (横px)",self.pixel,40,192),
                  ("使う色の数",self.colors,4,64),
                  ("背景の明るさ (%)",self.brightness,65,125),
                  ("背景透過の許容値",self.tolerance,10,100)]
        for j,(name,var,low,high) in enumerate(controls):
            cell=tk.Frame(bar,bg=PANEL)
            cell.grid(row=0,column=j,sticky="ew",padx=(0,18))
            self._label(cell,name,9,DIM).pack(anchor="w")
            tk.Scale(cell,from_=low,to=high,variable=var,orient="horizontal",showvalue=True,
                length=245 if j<2 else 210,sliderlength=14,highlightthickness=0,borderwidth=0,
                resolution=1,bg=PANEL,fg=FG,troughcolor="#38516e",activebackground=BLUE).pack(anchor="w")
        checkbar=tk.Frame(settings,bg=PANEL)
        checkbar.pack(fill="x")
        for title,var in (("色をなじませる（ディザリング）",self.dither),
                          ("単色背景なら自動で透過する",self.remove_bg)):
            tk.Checkbutton(checkbar,text=title,variable=var,bg=PANEL,fg=FG,
                           selectcolor="#27344d",activebackground=PANEL,activeforeground=FG,
                           font=("Yu Gothic UI",10)).pack(side="left",padx=(0,25))

        actions=tk.Frame(self.page,bg=BACKGROUND)
        actions.pack(fill="x",padx=28,pady=(1,9))
        self._button(actions,"生成した画像を全部保存（PNG）",self.save_all,True).pack(side="left")
        self._button(actions,"変換をやり直す",self.convert).pack(side="left",padx=(10,0))
        self._button(actions,"説明を見る",self.show_help).pack(side="left",padx=(10,0))
        self._label(actions,"画像はPC内で処理され、外部に送信されません。",9,DIM).pack(side="right")

        self._label(self.page,"変換結果  ｜  実写 → 通常ドット → ゲーム素材",14,FG,True).pack(fill="x",padx=28,pady=(0,3))
        self._label(self.page,"左右で比較しながら下へスクロール。画像をクリックすると大きく確認できます。",9,DIM).pack(fill="x",padx=28,pady=(0,7))
        # Results are regular document content, not a separately scrolling area.
        # The scrollbar on the right controls the entire app from header to footer.
        self.cards = tk.Frame(self.page, bg=BACKGROUND)
        self.cards.pack(fill="x", padx=28)
        cards=[
          ("source","01  入力した実写写真","元写真の情報・構図を確認"),
          ("normal","02  シンプルなドット絵化","解像度と色数を削減しただけの比較用"),
          ("game_background","03  ゲーム向け背景｜鮮やか","コントラスト・色設計・ピクセル輪郭を調整"),
          ("sunset_background","04  ゲーム向け背景｜夕暮れ","温かい光・色調で雰囲気を変更"),
          ("night_background","05  ゲーム向け背景｜夜","青色系・低照度の別パターン"),
          ("game_demo","06  ゲーム画面での使用例","足場・キャラ・コイン・UIを重ねた見本（プレイ不可）"),
          ("built_in_hero","07  ゲーム用キャラクター見本","写真からの切り抜きではなく付属のオリジナル素材"),
          ("tile_repeat","08  タイル配置の見本","写真から繰り返し用の模様を作成"),
        ]
        for i,(key,title,sub) in enumerate(cards):
            box=tk.Frame(self.cards,bg=PANEL,padx=10,pady=10)
            box.grid(row=i//2,column=i%2,sticky="nsew",padx=6,pady=6)
            self._label(box,title,11,FG,True).pack(anchor="w")
            self._label(box,sub,9,DIM).pack(anchor="w",pady=(3,7))
            img=tk.Label(box,bg="#dfe4ec",width=64,height=16,cursor="hand2")
            img.pack(fill="both",expand=True)
            img.bind("<Button-1>", lambda e, current_key=key: self.open_preview(current_key))
            self.labels[key]=img
        for i in range(2):
            self.cards.columnconfigure(i,weight=1,uniform="preview")
        for i in range(4):
            self.cards.rowconfigure(i,weight=1)

        footer=tk.Frame(self.page,bg=BACKGROUND)
        footer.pack(fill="x",padx=28,pady=(6,12))
        self._label(footer,"※ 実写の背景を変換するアプリです。人物等の自動切り抜きAIはなく、スプライト抽出は単色背景のみ対応。",9,DIM).pack(anchor="w")
        tk.Label(footer,textvariable=self.note,bg=BACKGROUND,fg=GREEN,font=("Yu Gothic UI",9),anchor="w").pack(fill="x")
        tk.Label(footer,textvariable=self.status,bg=BACKGROUND,fg=BLUE,font=("Yu Gothic UI",10,"bold"),anchor="w").pack(fill="x")

    def _update_scrollregion(self, event=None):
        self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))

    def _resize_page(self, event):
        self.page_canvas.itemconfigure(self.page_window, width=event.width)

    def _scroll_allowed(self, event) -> bool:
        # Don't hijack the wheel inside the enlarged-image popup.
        try:
            return event.widget.winfo_toplevel() == self.root
        except (AttributeError, tk.TclError):
            return False

    def _wheel(self, event):
        if self._scroll_allowed(event) and event.delta:
            # Tk's delta is usually 120 per notch on Windows. Keep precision
            # touchpads usable when a smaller delta is delivered.
            notches = max(1, round(abs(event.delta) / 120))
            self.page_canvas.yview_scroll((-1 if event.delta > 0 else 1) * notches * 3, "units")
            return "break"

    def _wheel_linux(self, event):
        if self._scroll_allowed(event):
            self.page_canvas.yview_scroll(-3 if event.num == 4 else 3, "units")
            return "break"

    def _page_key(self, event):
        if not self._scroll_allowed(event):
            return None
        if event.keysym == "Prior":
            self.page_canvas.yview_scroll(-1, "pages")
        elif event.keysym == "Next":
            self.page_canvas.yview_scroll(1, "pages")
        elif event.keysym == "Home":
            self.page_canvas.yview_moveto(0)
        elif event.keysym == "End":
            self.page_canvas.yview_moveto(1)
        return "break"

    def _on_drop(self,event):
        try:
            names=self.root.tk.splitlist(event.data)
            if names: self.load_image(Path(names[0]))
        except Exception as e:
            messagebox.showerror("画像を開けません",str(e))

    def select_file(self):
        path=filedialog.askopenfilename(title="ドット絵にしたい画像を選んでください",
                filetypes=[("画像ファイル","*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),("すべて","*.*")])
        if path:
            self.load_image(Path(path))

    def load_image(self,path:Path):
        try:
            self.source=open_local_image(path)
        except Exception as e:
            messagebox.showerror("画像を読み込めません",f"この画像を開けませんでした。\n\n{e}")
            return
        self.source_path=path
        self.status.set(f"画像を読み込みました：{path.name} （{self.source.width}×{self.source.height}）")
        self.convert()

    def cfg(self)->Settings:
        return Settings(pixel_width=self.pixel.get(),colors=self.colors.get(),dither=self.dither.get(),
          bg_brightness=self.brightness.get(),bg_tolerance=self.tolerance.get(),remove_bg=self.remove_bg.get())

    def apply_preset(self,pixel_width:int,colors:int,brightness:int):
        self.pixel.set(pixel_width)
        self.colors.set(colors)
        self.brightness.set(brightness)

    def schedule_refresh(self,*args):
        if self.after_job:
            self.root.after_cancel(self.after_job)
        self.after_job=self.root.after(350,self.convert)

    def convert(self):
        self.after_job=None
        if self.source is None: return
        try:
            self.status.set("変換中…")
            self.root.update_idletasks()
            self.results=create_all(self.source,self.cfg())
            self._image("source",self.source)
            for key in ("normal","game_background","sunset_background","night_background","built_in_hero","tile_repeat","game_demo"):
                self._image(key,self.results[key])
            self.note.set("画像の被写体切り抜き："+self.results["sprite_note"]+" （背景素材の変換とは別機能）")
            self.status.set("✅ 実写から8つの見本を生成しました。［全部保存］で背景・ゲーム画面・素材を出力できます。")
        except Exception as e:
            self.status.set("変換に失敗しました")
            messagebox.showerror("変換エラー",str(e))

    def _image(self,key,im:Image.Image):
        img=im.copy().convert("RGBA")
        self.original_images[key] = im.copy()
        img.thumbnail((520,300),Image.Resampling.NEAREST if key!="source" else Image.Resampling.LANCZOS)
        ref=ImageTk.PhotoImage(img)
        self.refs[key]=ref
        self.labels[key].configure(image=ref,width=516,height=296)


    def open_preview(self,key:str):
        if key not in self.original_images:
            return
        src = self.original_images[key].copy().convert("RGBA")
        top = tk.Toplevel(self.root)
        top.title(f"拡大表示 - {key}")
        top.configure(bg=BACKGROUND)
        top.geometry("980x760")
        top.minsize(720,560)

        title_map = {
            "source":"元の写真",
            "normal":"通常ドット絵",
            "game_background":"ゲーム用背景",
            "sprite":"写真からのスプライト（単色背景のみ）",
            "sunset_background":"夕暮れ背景",
            "night_background":"夜景背景",
            "built_in_hero":"付属のゲーム用キャラクター",
            "tile_repeat":"タイルを繰り返すと？",
            "game_demo":"ゲームの使用例",
        }
        tk.Label(top,text=title_map.get(key,key),bg=BACKGROUND,fg=FG,font=("Yu Gothic UI",15,"bold")).pack(anchor="w",padx=18,pady=(16,8))
        canvas = tk.Canvas(top,bg="#101828",highlightthickness=0)
        canvas.pack(fill="both",expand=True,padx=18,pady=(0,12))
        status = tk.Label(top,text="",bg=BACKGROUND,fg=DIM,font=("Yu Gothic UI",9))
        status.pack(fill="x",padx=18,pady=(0,14))

        holder = {"photo": None}

        def render(event=None):
            w = max(canvas.winfo_width()-16, 100)
            h = max(canvas.winfo_height()-16, 100)
            img = src.copy()
            img.thumbnail((w, h), Image.Resampling.NEAREST if key != "source" else Image.Resampling.LANCZOS)
            holder["photo"] = ImageTk.PhotoImage(img)
            canvas.delete("all")
            canvas.create_image(w//2+8, h//2+8, image=holder["photo"], anchor="center")
            status.config(text=f"元サイズ: {src.width}×{src.height}  |  表示サイズ: {img.width}×{img.height}  |  クリック画像を見やすく拡大表示")

        canvas.bind("<Configure>", render)
        top.after(60, render)

    def save_all(self):
        if self.source is None or self.results is None:
            messagebox.showinfo("まず画像を選択","最初に変換したい画像を選んでください。")
            return
        folder=filedialog.askdirectory(title="結果の保存先フォルダを選択",initialdir=str(ROOT))
        if not folder: return
        try:
            out=export_all(self.source,self.results,self.cfg(),Path(folder),self.source_path.stem if self.source_path else "photo")
            messagebox.showinfo("保存できました",f"PNG画像10枚＋設定JSONを保存しました。\n\n{out}\n\n00_before_after_comparison.png を開くと、全結果を一覧できます。")
            self.status.set("保存完了："+str(out))
        except Exception as e:
            messagebox.showerror("保存エラー",str(e))

    def show_help(self):
        messagebox.showinfo("写真からゲーム背景を作る手順",
            "① 写真を選ぶ（実写ロケット写真も同梱）\n"
            "② 元写真と通常ドット絵を比べる\n"
            "③ ゲーム向けの鮮やか・夕暮れ・夜を比べる\n"
            "④ 足場・主人公・コイン付きのゲーム配置例を見る\n"
            "⑤ ［全部保存］でPNGを出力\n\n"
            "ゲーム背景：960×540。HUDなしなのでゲームに組み込み可能。\n"
            "ゲーム画面：デモ画像（そのままプレイはできません）。\n"
            "人物切り抜き：単色背景のみ。複雑な写真をAIで切り抜きません。\n\n"
            "アプリはオフライン処理。画像は外部へ送信しません。")


def main():
    dnd=False
    if TkinterDnD is not None:
        try:
            root=TkinterDnD.Tk()
            dnd=True
        except Exception:
            root=tk.Tk()
    else:
        root=tk.Tk()
    PixelLabApp(root,dnd)
    root.mainloop()


if __name__=="__main__":
    main()
