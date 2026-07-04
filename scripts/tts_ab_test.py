# 台語 TTS A/B 審聽測試 (tts_ab_test.py)
#
# 讀取固定測試句組（data/evaluations/tts_ab_test_sentences.json），為每個語音引擎
# 合成同一批測試句，輸出到本機目錄（config 的 output.base_dir），並產生離線審聽頁
# review.html：教師逐句試聽、評分（發音／聲調／自然度／整體），評分可匯出 JSON。
#
# 引擎規格（--engines，逗號分隔）：
#   concat                 接音合成（教育部官方單詞音檔，發音基準對照組）
#   ithuan                 意傳媠聲線上合成（免費展示服務，限流 3 句/分鐘 → 20 句約 7 分鐘）
#   voxcpm                 VoxCPM2 三師爸台語聲音（現行 provider）
#   mms                    本地 facebook/mms-tts-nan（需 torch，CC-BY-NC）
#   yating:tai_female_1    雅婷 TTS 台語女聲（雅婷）；亦可 tai_male_1／tai_female_2
#
# 用法：
#   .venv\Scripts\python scripts/tts_ab_test.py
#   .venv\Scripts\python scripts/tts_ab_test.py --engines concat,yating:tai_female_1
#
# 注意：已存在的音檔會跳過（--force 可重新合成），因此可先跑 concat 基準，
#       之後拿到雅婷 API key 再補跑，review.html 會自動納入所有已完成的引擎。
import os
import re
import sys
import json
import html
import shutil
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from utils import safe_print  # noqa: E402
from tts.generator import TaigiTTS  # noqa: E402

print = safe_print

DEFAULT_ENGINES = "concat,ithuan,voxcpm,yating:tai_female_1,yating:tai_male_1,yating:tai_female_2"

# 引擎顯示名稱（審聽頁用）
ENGINE_LABELS = {
    "concat": "接音合成（教育部官方音檔）",
    "ithuan": "意傳媠聲（免費展示服務）",
    "voxcpm": "VoxCPM2（三師爸台語聲）",
    "mms": "MMS（mms-tts-nan）",
    "yating:tai_female_1": "雅婷 TTS 女聲（雅婷）",
    "yating:tai_male_1": "雅婷 TTS 男聲（家豪）",
    "yating:tai_female_2": "雅婷 TTS 女聲（意晴）",
}


def engine_dir_name(spec: str) -> str:
    """引擎規格轉為安全目錄名，例如 yating:tai_male_1 -> yating_tai_male_1。"""
    return re.sub(r"[^A-Za-z0-9_-]", "_", spec)


def build_tts(config_path: str, spec: str):
    """
    依引擎規格建立 TaigiTTS 實例（覆寫 provider／聲音）。
    回傳 (tts, skip_reason)；skip_reason 非 None 代表此引擎環境不足應跳過，
    避免 generator 內部靜默降級成別的引擎、混淆 A/B 標籤。
    """
    provider, _, voice = spec.partition(":")
    tts = TaigiTTS(config_path)
    tts.provider = provider
    if voice:
        tts.tts_config["yating_voice"] = voice

    if provider == "yating" and not tts.api_key:
        return tts, "未設定 tts.api_key（雅婷 API 金鑰），先跳過。拿到 key 後填入 config.json 再重跑即可。"
    if provider in ("concat", "ithuan") and not shutil.which("ffmpeg"):
        return tts, "找不到 ffmpeg，無法合成／轉檔。"
    if provider == "voxcpm":
        py = tts.voxcpm_config.get("python", "")
        script = tts.voxcpm_config.get("script", "")
        if not (py and os.path.exists(py) and script and os.path.exists(script)):
            return tts, "找不到 VoxCPM2 語音專案（config 的 tts.voxcpm.python / script）。"
    if provider == "mms":
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return tts, "未安裝 torch/transformers，無法使用 mms。"
    return tts, None


def synthesize_engine(tts: TaigiTTS, spec: str, sentences, out_dir: str, force: bool):
    """為單一引擎合成整組測試句，回傳 {sentence_id: bool}。"""
    provider = spec.partition(":")[0]
    os.makedirs(out_dir, exist_ok=True)
    results = {}

    todo = []
    for s in sentences:
        wav = os.path.join(out_dir, f"{s['id']}.wav")
        if not force and os.path.exists(wav) and os.path.getsize(wav) > 0:
            results[s["id"]] = True
            continue
        todo.append((s, wav))

    if not todo:
        print(f"  [=] 全部 {len(sentences)} 句已存在，跳過（--force 可重跑）。")
        return results

    if provider == "voxcpm":
        # VoxCPM2 走批次介面，模型只載一次
        items = [{"text": tts._voxcpm_feed_text(s["hanji"], s.get("tailo_diacritic", "")),
                  "output": wav} for s, wav in todo]
        flags = tts.synthesize_voxcpm_batch(items)
        for (s, _), ok in zip(todo, flags):
            results[s["id"]] = bool(ok)
    else:
        for s, wav in todo:
            ok = tts.synthesize_sentence(
                s["hanji"], wav,
                tailo_numeric=s.get("tailo_numeric", ""),
                tailo_diacritic=s.get("tailo_diacritic", ""),
            )
            results[s["id"]] = bool(ok)
    return results


def render_review_html(data, engines_done, manifest, out_path: str):
    """產生離線審聽頁：逐句試聽各引擎音檔、評分（1-5）與備註，可匯出 JSON。"""
    rubric = data.get("scoring_rubric", {})
    rubric_html = "".join(
        f"<li><b>{html.escape(k)}</b>：{html.escape(v)}</li>" for k, v in rubric.items()
    )

    head_cols = "".join(
        f"<th>{html.escape(ENGINE_LABELS.get(spec, spec))}</th>" for spec in engines_done
    )

    rows = []
    for s in data["sentences"]:
        sid = s["id"]
        cells = []
        for spec in engines_done:
            ok = manifest["results"].get(sid, {}).get(spec, False)
            rel = f"{engine_dir_name(spec)}/{sid}.wav"
            if ok:
                cells.append(
                    f'<td><audio controls preload="none" src="{rel}"></audio>'
                    f'<select data-score="{sid}|{html.escape(spec)}">'
                    f'<option value="">評分</option>'
                    + "".join(f'<option value="{i}">{i}</option>' for i in range(1, 6))
                    + "</select></td>"
                )
            else:
                cells.append("<td class='miss'>（未合成）</td>")
        rows.append(
            "<tr>"
            f"<td class='hanji'>{html.escape(s['hanji'])}<div class='tailo'>{html.escape(s['tailo_diacritic'])}</div>"
            f"<div class='zh'>{html.escape(s['zh_tw'])}</div></td>"
            f"<td class='focus'>{html.escape(s['test_focus'])}</td>"
            + "".join(cells)
            + f"<td><input class='note' data-note='{sid}' placeholder='備註（哪個字錯、變調怪…）'></td></tr>"
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>台語 TTS A/B 審聽 — {html.escape(data.get('version', ''))}</title>
<style>
  body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif; margin: 24px; background: #fafaf7; color: #333; }}
  h1 {{ font-size: 1.4em; }}
  .rubric {{ background: #fff8e1; border: 1px solid #e0c96f; border-radius: 8px; padding: 10px 24px; max-width: 900px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 16px; background: #fff; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; font-size: 0.92em; }}
  th {{ background: #34515e; color: #fff; position: sticky; top: 0; }}
  td.hanji {{ font-size: 1.15em; font-weight: bold; min-width: 12em; }}
  .tailo {{ color: #1a6b54; font-weight: normal; font-size: 0.85em; margin-top: 2px; }}
  .zh {{ color: #999; font-weight: normal; font-size: 0.8em; }}
  td.focus {{ color: #7a5c00; max-width: 14em; }}
  td.miss {{ color: #bbb; text-align: center; }}
  audio {{ width: 200px; display: block; margin-bottom: 4px; }}
  select {{ font-size: 1em; }}
  input.note {{ width: 14em; }}
  #export {{ margin: 16px 0; padding: 8px 20px; font-size: 1em; background: #1a6b54; color: #fff; border: none; border-radius: 6px; cursor: pointer; }}
  .hint {{ color: #888; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>台語 TTS A/B 審聽測試（{len(data['sentences'])} 句 × {len(engines_done)} 引擎）</h1>
<p>產生時間：{manifest['generated_at']}｜臺羅為教育部辭典<b>本調</b>，請特別聽<b>連讀變調</b>是否正確。</p>
<div class="rubric"><b>評分基準（1 最差、5 最好）</b><ul>{rubric_html}</ul></div>
<button id="export">⬇ 匯出評分 JSON</button>
<span class="hint">評分與備註會自動存在瀏覽器（localStorage），關掉再開不會不見。</span>
<table>
<tr><th>測試句</th><th>測試重點</th>{head_cols}<th>備註</th></tr>
{''.join(rows)}
</table>
<script>
const KEY = "taigi_tts_ab_scores";
const saved = JSON.parse(localStorage.getItem(KEY) || "{{}}");
document.querySelectorAll("select[data-score]").forEach(el => {{
  if (saved[el.dataset.score]) el.value = saved[el.dataset.score];
  el.addEventListener("change", () => {{ saved[el.dataset.score] = el.value; localStorage.setItem(KEY, JSON.stringify(saved)); }});
}});
document.querySelectorAll("input[data-note]").forEach(el => {{
  const k = "note|" + el.dataset.note;
  if (saved[k]) el.value = saved[k];
  el.addEventListener("input", () => {{ saved[k] = el.value; localStorage.setItem(KEY, JSON.stringify(saved)); }});
}});
document.getElementById("export").addEventListener("click", () => {{
  const blob = new Blob([JSON.stringify({{ exported_at: new Date().toISOString(), scores: saved }}, null, 2)],
                        {{ type: "application/json" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "tts_ab_scores.json";
  a.click();
}});
</script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)


def main():
    parser = argparse.ArgumentParser(description="台語 TTS A/B 審聽測試")
    parser.add_argument("--config", default=os.path.join(PROJECT_ROOT, "config.json"))
    parser.add_argument("--sentences",
                        default=os.path.join(PROJECT_ROOT, "data", "evaluations",
                                             "tts_ab_test_sentences.json"))
    parser.add_argument("--engines", default=DEFAULT_ENGINES,
                        help="逗號分隔的引擎清單，例如 concat,yating:tai_female_1")
    parser.add_argument("--output", default=None,
                        help="輸出目錄；未指定時為 <output.base_dir>/tts_ab_test")
    parser.add_argument("--force", action="store_true", help="重新合成已存在的音檔")
    args = parser.parse_args()

    with open(args.sentences, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    sentences = data["sentences"]

    # 輸出目錄優先序：--output > config 的 output.base_dir > 專案內 output/
    if args.output:
        out_root = args.output
    else:
        cfg = {}
        if os.path.exists(args.config):
            with open(args.config, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
        from utils import resolve_output_base_dir
        out_root = os.path.join(resolve_output_base_dir(cfg), "tts_ab_test")
    os.makedirs(out_root, exist_ok=True)

    print(f"[*] 測試句組：{len(sentences)} 句（{data.get('version', '')}）")
    print(f"[*] 輸出目錄：{out_root}")

    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sentences_file": os.path.abspath(args.sentences),
        "engines": {},
        "results": {s["id"]: {} for s in sentences},
    }

    engines_done = []
    for spec in [e.strip() for e in args.engines.split(",") if e.strip()]:
        label = ENGINE_LABELS.get(spec, spec)
        print(f"\n[=] 引擎：{label}（{spec}）")
        tts, skip = build_tts(args.config, spec)
        if skip:
            print(f"  [!] 跳過：{skip}")
            manifest["engines"][spec] = {"skipped": skip}
            continue

        out_dir = os.path.join(out_root, engine_dir_name(spec))
        results = synthesize_engine(tts, spec, sentences, out_dir, args.force)
        ok_n = sum(1 for v in results.values() if v)
        print(f"  [+] 完成 {ok_n}/{len(sentences)} 句 → {out_dir}")
        manifest["engines"][spec] = {"dir": engine_dir_name(spec), "ok": ok_n}
        for sid, ok in results.items():
            manifest["results"][sid][spec] = ok
        if ok_n:
            engines_done.append(spec)

    # 渲染前掃描輸出目錄：納入「所有已有音檔的引擎」（含先前跑過、本輪未執行的），
    # 避免分次執行不同引擎時，review.html 只剩本輪引擎的欄位。
    known_dirs = {engine_dir_name(s): s for s in ENGINE_LABELS}
    engines_done = []
    if os.path.isdir(out_root):
        for entry in sorted(os.listdir(out_root)):
            d = os.path.join(out_root, entry)
            if not os.path.isdir(d):
                continue
            spec = known_dirs.get(entry, entry)
            has_audio = False
            for s in sentences:
                wav = os.path.join(d, f"{s['id']}.wav")
                ok = os.path.exists(wav) and os.path.getsize(wav) > 0
                if ok:
                    has_audio = True
                manifest["results"][s["id"]][spec] = ok
            if has_audio and spec not in engines_done:
                engines_done.append(spec)
    # 依 ENGINE_LABELS 的順序排欄位（未知引擎排最後）
    order = list(ENGINE_LABELS)
    engines_done.sort(key=lambda s: order.index(s) if s in order else len(order))

    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    if engines_done:
        review_path = os.path.join(out_root, "review.html")
        render_review_html(data, engines_done, manifest, review_path)
        print(f"\n[+] 審聽頁已產生：{review_path}")
        print("    請用瀏覽器開啟，逐句試聽、評分後按「匯出評分 JSON」。")
    else:
        print("\n[!] 沒有任何引擎完成合成，未產生審聽頁。")


if __name__ == "__main__":
    main()
