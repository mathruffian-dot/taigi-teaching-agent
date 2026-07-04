# 台語互動遊戲網站生成器 (game_generator.py)
#
# 以「固定模板 × 內容替換」產出離線可玩的台語遊戲網頁：
# 讀取教材產出資料夾（lesson_structure.json ＋ audio/ ＋ images/），
# 將音檔轉 mp3（含 loudnorm 響度調和），渲染 games/ 底下的遊戲頁與大廳。
#
# M1 模板：match（拖拉配對）、listen（聽音揀圖）。
# 語音一律用預生成音檔（教育部官方音／意傳媠聲），禁用瀏覽器 TTS（專案規範）。
import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Dict, Any, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print
print = safe_print

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "games")

# M1 遊戲清單；M2 擴充 memory/bingo/mole/builder
GAME_META = {
    "match": {"title": "拖拉配對", "tailo": "Thua-lâi phòe-tùi", "desc": "共漢字卡拖去對的臺羅遐", "icon": "🧩"},
    "listen": {"title": "聽音配對", "tailo": "Thiann im phòe-tùi", "desc": "揤喇叭聽聲，共圖卡拖去對的聲遐", "icon": "👂"},
}


class GameGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

    def _convert_audio(self, src: str, dst: str) -> bool:
        """wav → 64kbps mp3，並做 loudnorm 響度調和（官方音檔與意傳音量差異大）。"""
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", src,
             "-af", "loudnorm=I=-18:TP=-2:LRA=11",
             "-codec:a", "libmp3lame", "-b:a", "64k", "-ar", "22050", dst],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0

    def _collect_vocab(self, lesson: Dict[str, Any], lesson_dir: str, out_dir: str) -> List[Dict[str, str]]:
        """整理遊戲可用詞彙：需有漢字＋臺羅＋存在的音檔；音檔轉 mp3、插圖複製進遊戲包。"""
        items = []
        for v in lesson.get("vocabulary", []):
            hanji = v.get("hanji", "")
            tailo = v.get("tailo_diacritic", "")
            audio_rel = v.get("audio_file", "")
            src_audio = os.path.join(lesson_dir, audio_rel) if audio_rel else ""
            if not (hanji and tailo and src_audio and os.path.exists(src_audio)):
                print(f"  [!] 略過詞彙「{hanji}」（缺臺羅或音檔）")
                continue

            mp3_rel = f"audio/{os.path.splitext(os.path.basename(audio_rel))[0]}.mp3"
            if not self._convert_audio(src_audio, os.path.join(out_dir, mp3_rel)):
                print(f"  [!] 略過詞彙「{hanji}」（音檔轉檔失敗）")
                continue

            img_rel = ""
            src_img = os.path.join(lesson_dir, v.get("image_file", "") or "")
            if v.get("image_file") and os.path.exists(src_img):
                img_rel = f"images/{os.path.basename(src_img)}"
                os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)
                shutil.copy2(src_img, os.path.join(out_dir, img_rel))

            items.append({"hanji": hanji, "tailo": tailo, "zh": v.get("zh_tw", ""),
                          "audio": mp3_rel, "image": img_rel})
        return items

    def generate(self, lesson_dir: str, templates: List[str] = None, output_dir: str = None) -> str:
        lesson_path = os.path.join(lesson_dir, "lesson_structure.json")
        if not os.path.exists(lesson_path):
            raise FileNotFoundError(f"找不到 {lesson_path}（請先用 generate 產出教材）")
        with open(lesson_path, "r", encoding="utf-8-sig") as f:
            lesson = json.load(f)

        templates = [t for t in (templates or list(GAME_META)) if t in GAME_META]
        out_dir = output_dir or os.path.join(lesson_dir, "games")
        os.makedirs(os.path.join(out_dir, "audio"), exist_ok=True)

        title = lesson.get("title", "台語練習")
        print(f"[*] 生成遊戲網站：《{title}》 → {out_dir}")
        vocab = self._collect_vocab(lesson, lesson_dir, out_dir)
        if len(vocab) < 3:
            raise RuntimeError(f"可用詞彙只有 {len(vocab)} 個，至少需要 3 個（漢字＋臺羅＋音檔齊備）")

        ctx_base = {
            "lesson_title": title,
            "grade": lesson.get("grade", ""),
            "vocab_json": json.dumps(vocab, ensure_ascii=False),
            "vocab": vocab,
        }
        built = []
        for name in templates:
            page = f"{name}.html"
            tpl = self.env.get_template(f"{name}.html.j2")
            with open(os.path.join(out_dir, page), "w", encoding="utf-8") as f:
                f.write(tpl.render(**ctx_base, meta=GAME_META[name]))
            built.append({"page": page, **GAME_META[name]})
            print(f"  [+] {GAME_META[name]['title']} → {page}")

        hub = self.env.get_template("hub.html.j2")
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(hub.render(**ctx_base, games=built, n_vocab=len(vocab)))
        print(f"  [+] 遊戲大廳 → index.html（{len(built)} 個遊戲、{len(vocab)} 個詞彙）")
        return out_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台語互動遊戲網站生成器")
    parser.add_argument("--lesson", required=True, help="教材產出資料夾（含 lesson_structure.json）")
    parser.add_argument("--templates", default=None, help="逗號分隔，如 match,listen（預設全部）")
    parser.add_argument("--output", default=None, help="輸出資料夾（預設 <lesson>/games）")
    args = parser.parse_args()
    tpls = [t.strip() for t in args.templates.split(",")] if args.templates else None
    GameGenerator().generate(args.lesson, tpls, args.output)
