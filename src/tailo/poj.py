# 臺羅 (Tâi-lô) → 白話字 (POJ, Pe̍h-ōe-jī) 轉換工具 (poj.py)
#
# 用途：facebook/mms-tts-nan 這類 MMS 閩南語 TTS 是以「白話字」語料（白話字聖經）
# 訓練的，輸入需要白話字「調符式」拼音，且不接受數字聲調。本模組將專案內以
# 教育部臺羅「數字調」儲存的拼音（如 tsiah8-png7）轉成白話字調符式（chia̍h-pn̄g）。
#
# 主要差異（臺羅 -> 白話字）：
#   ts -> ch、tsh -> chh、oo -> o͘、ua -> oa、ue -> oe、uai -> oai、
#   ing -> eng、ik -> ek、母音後 -nn -> 鼻化符 ⁿ
# 調符放置規則兩者一致，故重用 validator 的 tailo_numeric_to_diacritic。
#
# 已知限制：白話字鼻化以上標 ⁿ 表示，部分 TTS tokenizer 未必收錄；少數罕用音節
# 與變體（如 ⁿ、o͘ 疊調）可能無法完美還原，正式音訊仍須教師審聽。
import os
import re
import sys

try:
    from tailo.validator import tailo_numeric_to_diacritic, TONE_MAP
except ImportError:  # 允許以單檔方式被載入
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tailo.validator import tailo_numeric_to_diacritic, TONE_MAP

# 聲母對應（長者優先）
_INITIALS = [("tsh", "chh"), ("ts", "ch")]
# 韻母對應（uai 須在 ua 之前判斷；用 replace 時 ua->oa 亦可自動把 uai 轉成 oai）
_FINALS = [("ua", "oa"), ("ue", "oe"), ("ing", "eng"), ("ik", "ek")]

# 帶調或不帶調的 o（用於 oo -> o͘ 的後處理）
_O_FORMS = ["ó", "ò", "ô", "ō", "o̍", "o"]

# 一個臺羅數字調音節的字型：字母 + 選擇性數字聲調
_SYLLABLE_RE = re.compile(r"^([A-Za-z]+)([1-8]?)$")
# 句中音節串（與 validator 相同）：字母+數字，可用連字號連接
_WORD_RE = re.compile(r"\b[A-Za-z]+[1-8](?:-[A-Za-z]+[1-8])*\b")


def _syllable_to_poj(syllable: str) -> str:
    """將單一臺羅數字調音節轉為白話字調符式。"""
    m = _SYLLABLE_RE.match(syllable)
    if not m:
        return syllable
    body, tone = m.group(1), m.group(2)
    low = body.lower()

    # 1. 聲母 ts/tsh -> ch/chh（保留首字母大小寫）
    for tl, poj in _INITIALS:
        if low.startswith(tl):
            repl = poj.upper() if body[0].isupper() else poj
            body = repl + body[len(tl):]
            low = body.lower()
            break

    # 2. 鼻化韻尾：母音後的 -nn -> 之後補上上標 ⁿ
    nasal = bool(re.search(r"[aeiou]nn$", low))
    if nasal:
        body = body[:-2]
        low = body.lower()

    # 3. 韻母對應（ua->oa 會一併把 uai 變成 oai）
    for tl, poj in _FINALS:
        if tl in low:
            body = re.sub(tl, poj, body, flags=re.IGNORECASE)
            low = body.lower()

    # 4. 調符放置
    #    白話字與臺羅放置規則大致一致，唯「oa / oe」(後不接母音時) 調符標在 o，
    #    而臺羅標在 a / e（如 我 góa vs guá、粿 kóe vs kué）。oai 等三母音仍標第二母音，
    #    故僅特判 oa / oe。
    diverge = re.search(r"o[ae](?![aeiou])", low) is not None
    if diverge and tone in TONE_MAP:
        idx = re.search(r"o[ae](?![aeiou])", low).start()  # 'o' 的位置
        toned_o = TONE_MAP[tone]["o"]
        diacritic = body[:idx] + toned_o + body[idx + 1:]
    else:
        # 重用臺羅調符放置，此時仍是 ASCII，oo 暫不轉
        diacritic = tailo_numeric_to_diacritic(body + tone)

    # 5. oo -> o͘（保留已落在第一個 o 上的調符，第二個 o 換成組合符 ◌͘）
    for o_form in _O_FORMS:
        target = o_form + "o"
        if target in diacritic:
            diacritic = diacritic.replace(target, o_form + "͘")
            break

    # 6. 補上鼻化上標
    if nasal:
        diacritic += "ⁿ"  # ⁿ

    return diacritic


def tailo_to_poj(text: str) -> str:
    """
    將含臺羅數字調的字串（單音節、詞或整句）轉為白話字調符式。
    例：'tsiah8-png7' -> 'chia̍h-pn̄g'、'a1-ma2' -> 'a-má'。
    """
    def _repl_word(m: "re.Match") -> str:
        parts = m.group(0).split("-")
        return "-".join(_syllable_to_poj(p) for p in parts)

    return _WORD_RE.sub(_repl_word, text)


if __name__ == "__main__":
    samples = {
        "tsiah8-png7": "chia̍h-pn̄g",
        "tshai3-tshi7-a2": "chhài-chhī-á",
        "gua7-tse7-tsinn5": "gōa-chē-chîⁿ",
        "kue2": "kóe",
        "kong1-hng5": "kong-hn̂g",
    }
    for num, expect in samples.items():
        got = tailo_to_poj(num)
        print(f"{num:18} -> {got:16} (期望 {expect}) {'OK' if got == expect else 'DIFF'}")
