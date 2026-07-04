# -*- coding: utf-8 -*-
"""
對時腳本：讀 durations.json（旁白實測長度），計算每頁 dur = 旁白 + 2.0s 消化，
回填 index.html 的 PAGES 與 record.cjs 的 TOTAL_MS，並產出 master 音軌用的
每頁目標長度 page_targets.json。三處時長由同一來源生成，不會漂移。
"""
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAIL = 2.0   # 每頁旁白結束後的靜止消化秒數
END_HOLD = 3.0  # 末頁收尾多錄秒數

durations = {int(k): v for k, v in json.loads((HERE / "durations.json").read_text(encoding="utf-8")).items()}
targets = {p: round(math.ceil((d + TAIL) * 10) / 10, 1) for p, d in sorted(durations.items())}
total = round(sum(targets.values()), 1)

# 1) 回填 index.html PAGES 的 dur
html = (HERE / "index.html").read_text(encoding="utf-8")
def repl(m):
    page = int(m.group(1))
    return f"{{i:{page}, dur:{targets[page]},"
html2 = re.sub(r"\{i:(\d+), dur:[\d.]+,", repl, html)
(HERE / "index.html").write_text(html2, encoding="utf-8")

# 2) 回填 record.cjs TOTAL_MS
cjs = (HERE / "record.cjs").read_text(encoding="utf-8")
total_ms = int((total + END_HOLD) * 1000)
cjs2 = re.sub(r"const TOTAL_MS = \d+;", f"const TOTAL_MS = {total_ms};", cjs)
(HERE / "record.cjs").write_text(cjs2, encoding="utf-8")

# 3) 每頁目標長度（master 音軌組裝用）
(HERE / "page_targets.json").write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8")

for p in sorted(targets):
    print(f"  page {p}: 旁白 {durations[p]:.2f}s → 頁長 {targets[p]}s")
print(f"[*] 總片長 {total}s（+{END_HOLD}s 收尾錄影）；TOTAL_MS={total_ms}；三處已回填。")
