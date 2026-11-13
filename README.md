# RiG++ PixelLab 🎮

**実写写真をゲーム風のドット絵に変換するPythonアプリ**

RiG++ PixelLabは、実写写真をドット絵に変換し、ゲーム用の背景素材を作成できるWindows向けアプリです。

写真を1枚選ぶだけで、通常のドット絵、鮮やかなゲーム背景、夕暮れ・夜のバリエーション、ゲーム画面の使用例をまとめて生成できます。

Python初心者でも操作できるように、GUI（グラフィカルユーザーインターフェース）を用意しています。


## 主な機能

- **写真のドット絵化**：縮小・減色・最近傍補間を使ったピクセルアート変換
- **ゲーム背景の生成**：彩度・コントラスト・色調を調整した960×540の背景画像を出力
- **3種類の背景スタイル**：通常・夕暮れ・夜
- **ゲーム画面のプレビュー**：背景にキャラクター・足場・コイン・スコア表示を追加
- **スプライト生成**：単色背景の画像から透過PNGを作成
- **タイル生成**：繰り返し配置できるタイル画像を生成
- **日本語GUI**：画像の選択、設定変更、プレビュー、保存に対応
- **一括保存**：生成した画像をPNG形式で保存

※ゲーム画面のプレビューは静止画像です。遊べるゲームそのものを生成する機能ではありません。

## 動作環境

| 項目 | 内容 |
|---|---|
| OS | Windows |
| Python | 3.11以降を推奨 |
| 動作確認環境 | Python 3.13.5 |
| 画像処理 | Pillow |
| GUI | Tkinter |
| ドラッグ＆ドロップ | tkinterdnd2 |

## インストールと起動方法

### 方法1：Windowsで簡単に起動する

1. GitHubの「Code」→「Download ZIP」をクリックします。
2. ダウンロードしたZIPを展開します。
3. `RiG_PixelLab_2026` フォルダを開きます。
4. `START_HERE_Windows.bat` をダブルクリックします。

初回のみ、専用の仮想環境を作成して必要なライブラリをインストールします。

Python本体がインストールされていれば、別のバージョンを追加する必要はありません。

### 方法2：コマンドから起動する

PowerShellでプロジェクトのフォルダを開きます。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## アプリの使い方

1. 「画像を選ぶ」をクリックして写真を読み込みます。
2. 「レトロ風」「ゲーム向け」「細かめ」から設定を選びます。
3. 必要に応じて解像度・色数・明るさを変更します。
4. 画面を下にスクロールして変換結果を比較します。
5. 「生成した画像を全部保存（PNG）」をクリックします。

画像をクリックすると拡大表示できます。

## 生成される画像

| ファイル | 用途 |
|---|---|
| `01_normal_pixel_art.png` | 通常のドット絵 |
| `02_game_background_960x540.png` | ゲーム用背景 |
| `03_game_background_sunset.png` | 夕暮れ版 |
| `04_game_background_night.png` | 夜版 |
| `05_game_stage_mockup.png` | ゲーム画面の使用例 |
| `08_builtin_pixel_hero.png` | ゲーム用キャラクター |
| `09_seamless_tile.png` | タイル素材 |
| `10_repeating_tile_preview.png` | タイルの配置例 |

このほかに比較一覧、条件付きのスプライト画像、設定JSONなども保存されます。

## 画像変換の仕組み

基本的なドット絵変換は次の3段階です。

1. **画像の縮小**：画素数を減らして細部を単純化
2. **減色**：使用する色数を制限
3. **最近傍補間**：ドットの境界をぼかさず拡大

ゲーム用背景では、さらに色調・彩度・コントラストを調整し、ゲーム向けの見た目に加工します。

詳細な処理は`pixel_engine.py`に実装されています。

## フォルダ構成

```text
RiG_PixelLab_2026/
├── app.py
├── pixel_engine.py
├── cli.py
├── requirements.txt
├── START_HERE_Windows.bat
├── RUN_TESTS_Windows.bat
├── README.md
├── LICENSE
├── PHOTO_CREDITS.md
├── samples/
│   └── sample_real_rocket.jpg
├── examples/
│   └── new_photo_3stages.png
└── tests/
    └── test_pixel_engine.py
```

`examples/`には、このほかにも背景画像などのサンプルを収録しています。

## 注意事項

- 画像変換はPC内で実行され、画像が外部サーバーに送信されることはありません。
- 画像生成AIによるイラストの描き直しは行いません。
- 複雑な背景から人物を自動で切り抜く機能はありません。
- ゲーム画面のプレビューは静止画像です。
- 自分の写真を公開する際は、個人情報や著作権に注意してください。

## サンプル写真について

同梱する実写ロケット写真は、scikit-imageのサンプル画像`skimage.data.rocket()`に由来します。

詳細は`PHOTO_CREDITS.md`を参照してください。

## 参考資料

- [Python](https://www.python.org/)
- [Pillow](https://pillow.readthedocs.io/en/stable/)
- [scikit-image](https://scikit-image.org/)

## ライセンス

MIT License

詳細は`LICENSE`を参照してください。

---

RiG++ Advent Calendar 2026 — 12月9日
