# -*- coding: utf-8 -*-
"""
《去菜市仔買物件》旁白生成（發音精準版）。
- 整句旁白／對話：意傳媠聲（ithuan provider，餵 SCRIPT.md 驗證過的臺羅 KIP）
- 詞彙唸讀：教育部官方音檔（concat provider，真人錄音）
每頁由多段音訊以 ffmpeg 串接（段間插靜音），輸出 assets/narration/page-NN.wav，
並將實測時長寫入 durations.json 供 index.html / record.cjs 對時。

執行：PYTHONUTF8=1 .venv\\Scripts\\python video\\菜市仔買物件\\generate_narration.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PYTHONUTF8", "1")

from tts.generator import TaigiTTS

OUT = HERE / "assets" / "narration"
OUT.mkdir(parents=True, exist_ok=True)

# 段落型別：
#   ("s", 漢字, 臺羅KIP, 段後靜音秒)   → 意傳整句
#   ("w", 詞彙漢字, 重複次數, 段後靜音秒) → 官方詞彙音檔（重複間 0.7s）
PAGES = {
    1: [
        ("s", "逐家好！今仔日，咱來去菜市仔買物件！",
         "Ta̍k-ke hó! Kin-á-ji̍t, lán lâi-khì tshài-tshī-á bé mi̍h-kiānn!", 0.0),
    ],
    2: [
        ("s", "菜市仔，是上好的台語教室。",
         "Tshài-tshī-á, sī siōng hó ê Tâi-gí kàu-sik.", 0.4),
        ("s", "逐項物件，攏會當用台語講。",
         "Ta̍k hāng mi̍h-kiānn, lóng ē-tàng iōng Tâi-gí kóng.", 0.0),
    ],
    3: [
        ("s", "第一个詞。", "Tē-it ê sû.", 0.5),
        ("w", "菜市仔", 2, 0.6),
        ("s", "閣來。", "Koh lâi.", 0.5),
        ("w", "買物件", 2, 0.6),
        ("s", "咱逐工食的菜、魚仔、果子，攏是佇菜市仔買的。",
         "Lán ta̍k kang tsia̍h ê tshài, hî-á, kué-tsí, lóng sī tī tshài-tshī-á bé--ê.", 0.0),
    ],
    4: [
        ("s", "欲問價數，就講。", "Beh mn̄g kè-siàu, tō kóng.", 0.5),
        ("w", "偌濟錢", 2, 0.6),
        ("s", "買了，愛會記得說多謝。", "Bé liáu, ài ē-kì-tit seh to-siā.", 0.5),
        ("w", "多謝", 2, 0.0),
    ],
    5: [
        ("s", "注意聽！物件的物，尾音短短收。",
         "Tsù-ì thiann! Mi̍h-kiānn ê mi̍h, bué-im té-té siu.", 0.5),
        ("w", "買物件", 2, 0.7),
        ("s", "菜市仔，毋是一字一字念，連做伙念才會順。",
         "Tshài-tshī-á, m̄-sī tsi̍t jī tsi̍t jī liām, liân tsò-hué liām tsiah ē sūn.", 0.5),
        ("w", "菜市仔", 2, 0.0),
    ],
    6: [
        ("s", "阿媽，咱今仔日欲去菜市仔買物件無？",
         "A-má, lán kin-á-ji̍t beh khì tshài-tshī-á bé mi̍h-kiānn bô?", 0.6),
        ("s", "有啊，咱欲來去買一寡魚仔、肉佮菜。",
         "Ū--ah, lán beh lâi-khì bé tsi̍t-kuá hî-á, bah kah tshài.", 0.0),
    ],
    7: [
        ("s", "阿媽，這个魚仔一斤偌濟錢？",
         "A-má, tsit-ê hî-á tsi̍t-kin guā-tsē tsînn?", 0.6),
        ("s", "一斤兩百箍，多謝頭家。",
         "Tsi̍t-kin nn̄g-pah khoo, to-siā thâu-ke.", 0.0),
    ],
    8: [
        ("s", "萬用句型，啥物攏會當問，偌濟錢？綴我講。",
         "Bān-iōng kù-hîng, siánn-mih lóng ē-tàng mn̄g, guā-tsē tsînn? Tuè guá kóng.", 0.6),
        ("s", "菜頭一條偌濟錢？", "Tshài-thâu tsi̍t tiâu guā-tsē tsînn?", 0.8),
        ("s", "蘋果一粒偌濟錢？", "Phōng-kó tsi̍t lia̍p guā-tsē tsînn?", 0.0),
    ],
    9: [
        ("s", "上重要的一句話。頭家，這偌濟錢？",
         "Siōng tiōng-iàu ê tsi̍t kù uē. Thâu-ke, tse guā-tsē tsînn?", 0.6),
        ("s", "這禮拜，去菜市仔講看覓！多謝逐家！",
         "Tsit lé-pài, khì tshài-tshī-á kóng khuànn-māi! To-siā ta̍k-ke!", 0.0),
    ],
}


def ffprobe_dur(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def make_silence(sec: float, path: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
         "-t", f"{sec:.3f}", str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def norm(src: Path, dst: Path):
    """
    正規化每個音訊段：統一取樣率之外，並做 EBU R128 響度正規化（-18 LUFS）。
    兩個聲音來源（教育部官方音檔、意傳媠聲）原始音量差距大——官方音偏大聲、
    意傳偏小聲——不調和的話成片會忽大忽小。
    """
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-af", "loudnorm=I=-18:TP=-2:LRA=11",
         "-ar", "22050", "-ac", "1", str(dst)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    tts_sent = TaigiTTS(str(ROOT / "config.json"))
    tts_sent.provider = "ithuan"
    tts_word = TaigiTTS(str(ROOT / "config.json"))
    tts_word.provider = "concat"

    tmp = Path(tempfile.mkdtemp(prefix="tshi_narr_"))
    seg_cache = {}
    durations = {}

    try:
        for page, segs in PAGES.items():
            parts = []
            for si, seg in enumerate(segs):
                if seg[0] == "s":
                    _, hanji, kip, gap = seg
                    wav = tmp / f"p{page}s{si}.wav"
                    ok = tts_sent.synthesize_sentence(hanji, str(wav), tailo_diacritic=kip)
                    if not ok:
                        raise RuntimeError(f"意傳合成失敗：{hanji}")
                    parts.append((wav, gap))
                else:
                    _, word, times, gap = seg
                    if word not in seg_cache:
                        w = tmp / f"word_{word}.wav"
                        ok = tts_word.synthesize_sentence(word, str(w))
                        if not ok:
                            raise RuntimeError(f"官方詞彙音檔取得失敗：{word}")
                        seg_cache[word] = w
                    for t in range(times):
                        parts.append((seg_cache[word], 0.7 if t < times - 1 else gap))

            # 正規化 + 串接（段間插靜音）
            listing = tmp / f"list_p{page}.txt"
            norm_files = []
            with open(listing, "w", encoding="utf-8") as f:
                for pi, (wav, gap) in enumerate(parts):
                    nw = tmp / f"n_p{page}_{pi}.wav"
                    norm(wav, nw)
                    norm_files.append(nw)
                    f.write(f"file '{str(nw).replace(chr(92), '/')}'\n")
                    if gap > 0:
                        sil = tmp / f"sil_p{page}_{pi}.wav"
                        make_silence(gap, sil)
                        f.write(f"file '{str(sil).replace(chr(92), '/')}'\n")
            out = OUT / f"page-{page:02d}.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                 "-ar", "22050", "-ac", "1", str(out)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            durations[page] = round(ffprobe_dur(out), 2)
            print(f"[+] page-{page:02d}.wav  {durations[page]}s")

        with open(HERE / "durations.json", "w", encoding="utf-8") as f:
            json.dump(durations, f, ensure_ascii=False, indent=2)
        total = sum(durations.values())
        print(f"[*] 旁白完成，總語音長 {total:.1f}s；durations.json 已輸出。")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
