# -*- coding: utf-8 -*-
"""
《拍招呼——台語的好禮數》旁白生成。
與 Hyperframe 範本不同：旁白**用台語 TTS**（本專案 concat 接音合成，串接教育部官方音檔），
不用華語 Edge-TTS。輸出 assets/narration/page-NN.wav。

執行：.venv\\Scripts\\python video\\拍招呼\\generate_narration.py
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                 # 專案根目錄 2026本土語
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PYTHONUTF8", "1")

from tts.generator import TaigiTTS

OUT = HERE / "assets" / "narration"
OUT.mkdir(parents=True, exist_ok=True)

# 逐頁台語旁白（漢字）。皆為草稿，正式發布前需教師審聽（專案規範）。
SCRIPT = [
    (1, "逐家好！咱來學台語的禮數，學拍招呼。"),
    (2, "一工內底，對早到暗，咱攏會拍招呼。"),
    (3, "天光的時，會當講：逐家早起！"),
    (4, "別人鬥相共，愛會記得講：多謝、勞力。"),
    (5, "做毋著代誌，就講歹勢、失禮。對方會應你：無要緊。"),
    (6, "欲走的時陣，講一聲：再會，明仔載見。"),
    (7, "這馬咱來練習，鬥做一段對話。"),
    (8, "拍招呼有四款：相見、說多謝、會失禮、相辭。"),
    (9, "有禮數，逐家疼。咱做伙講台語！"),
]


def main():
    tts = TaigiTTS(str(ROOT / "config.json"))
    print(f"[*] TTS provider = {tts.provider}（應為 concat）")
    for i, text in SCRIPT:
        out = OUT / f"page-{i:02d}.wav"
        ok = tts.synthesize_sentence(text, str(out))
        size = out.stat().st_size if out.exists() else 0
        print(f"  page-{i:02d}: {'OK' if ok else 'FAIL'}  {size} bytes  ←  {text}")
    print("[*] 旁白生成完成。")


if __name__ == "__main__":
    main()
