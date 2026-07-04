# -*- coding: utf-8 -*-
"""
主音軌組裝：每頁 page-NN.wav 尾端補靜音至 page_targets.json 的頁長，
開頭補 lead_ms.txt（錄影開始→點擊）的靜音，串接成 renders/master_audio.wav。
如此音軌與 Playwright 錄影的時間軸完全對齊，mux 不需再裁切影片。
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NARR = HERE / "assets" / "narration"
REN = HERE / "renders"
REN.mkdir(exist_ok=True)
TMP = REN / "tmp"
TMP.mkdir(exist_ok=True)

targets = {int(k): float(v) for k, v in json.loads((HERE / "page_targets.json").read_text(encoding="utf-8")).items()}
lead_ms = int((REN / "lead_ms.txt").read_text().strip())

def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        sys.exit(f"ffmpeg 失敗：{' '.join(map(str, cmd))}")

listing = TMP / "list.txt"
with open(listing, "w", encoding="utf-8") as f:
    # 開頭 lead 靜音
    lead = TMP / "lead.wav"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
         "-t", f"{lead_ms/1000:.3f}", str(lead)])
    f.write(f"file '{str(lead).replace(chr(92), '/')}'\n")
    # 每頁補靜音至頁長（apad + -t 截齊）
    for p in sorted(targets):
        src = NARR / f"page-{p:02d}.wav"
        dst = TMP / f"p{p:02d}.wav"
        run(["ffmpeg", "-y", "-i", str(src), "-af", "apad", "-t", f"{targets[p]:.1f}",
             "-ar", "22050", "-ac", "1", str(dst)])
        f.write(f"file '{str(dst).replace(chr(92), '/')}'\n")

master = REN / "master_audio.wav"
run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
     "-ar", "22050", "-ac", "1", str(master)])
print(f"[+] master_audio.wav 完成（lead {lead_ms}ms + {len(targets)} 頁）")
