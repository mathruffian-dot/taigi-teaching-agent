# 教材內容自動檢核 (content_checker.py)
#
# 在教材生成後、進教師審核前，對課文做啟發式品質把關。對 Mock 與 LLM 產出皆適用。
# 設計原則：只「標記提醒」、不自動改寫；最終仍由教師審聽審核（見 CLAUDE.md）。
#
# 檢查項目：
#   1. 漢字夾雜華語常用詞（非道地台語用字）——附建議台語用字。
#   2. 對話／詞彙的「漢字字數」與「臺羅音節數」不一致——常代表漢字與拼音對不上。
import re
import unicodedata
from typing import Dict, Any, List

# 華語慣用詞 -> 建議台語用字（高把握度清單；僅作審核提醒，非自動更正）
MANDARIN_HINTS = {
    "老闆": "頭家 (thâu-ke)",
    "一些": "一寡 (tsi̍t-kuá)",
    "什麼": "啥物 (siánn-mih)",
    "甚麼": "啥物 (siánn-mih)",
    "怎麼": "按怎 (án-tsuánn)",
    "這個": "這个 (tsit-ê)",
    "那個": "彼个 (hit-ê)",
    "沒有": "無 (bô)",
    "可是": "毋過 (m̄-koh)",
    "現在": "這馬 (tsit-má)",
    "知道": "知影 (tsai-iánn)",
    "漂亮": "媠 (suí)",
}
# 單字層級提醒（較易誤判，標為提醒）
MANDARIN_CHAR_HINTS = {
    "跟": "佮 (kah)",
    "和": "佮 (kah)",
    "嗎": "（台語疑問句用「無／敢／喔」，不用「嗎」）",
    "呢": "（台語少用「呢」）",
    "們": "（台語複數用「阮／恁／𪜶」）",
    "很": "真 (tsin)",
    "都": "攏 (lóng)",
}

# 標點（計算漢字字數時排除）
_PUNCT = "，。！？、；：「」『』（）,.!?;:\"'()…—～~ 　\n\r\t"


def _count_hanji(text: str) -> int:
    """計算 CJK 漢字數（排除標點與空白）。"""
    return sum(1 for c in text if "一" <= c <= "鿿")


def _count_syllables(tailo: str) -> int:
    """
    以拉丁字母連續段估算臺羅音節數（數字與連字號/空白皆為分隔）。
    同時支援數字調（tsiah8）與調符式 KIP（tsia̍h）：調符式先做 NFD 分解、
    剝離變音符號（Mn），否則 a̍/ó 等會把一個音節拆成多段而誤報。
    """
    if not tailo:
        return 0
    stripped = "".join(c for c in unicodedata.normalize("NFD", tailo)
                       if unicodedata.category(c) != "Mn")
    return len(re.findall(r"[A-Za-z]+", stripped))


def _scan_mandarin(hanji: str) -> List[str]:
    hits = []
    for word, sug in MANDARIN_HINTS.items():
        if word in hanji:
            hits.append(f"「{word}」建議改用 {sug}")
    for ch, sug in MANDARIN_CHAR_HINTS.items():
        if ch in hanji:
            hits.append(f"「{ch}」{('建議改用 ' + sug) if '建議' not in sug and '（' not in sug else sug}")
    return hits


def check_lesson_content(data: Dict[str, Any]) -> List[str]:
    """
    對教材大綱做內容檢核，回傳警告字串清單（空清單代表未發現問題）。
    """
    warnings: List[str] = []

    # 1. 詞彙：華語用字提醒
    for v in data.get("vocabulary", []):
        hanji = v.get("hanji", "") if isinstance(v, dict) else str(v)
        for msg in _scan_mandarin(hanji):
            warnings.append(f"詞彙「{hanji}」：{msg}")

    # 2. 對話：華語用字 + 漢字/臺羅音節數一致性
    for idx, dia in enumerate(data.get("dialogues", [])):
        hanji = dia.get("hanji", "")
        tailo = dia.get("tailo_numeric", "") or dia.get("tailo_diacritic", "")

        for msg in _scan_mandarin(hanji):
            warnings.append(f"對話第 {idx + 1} 句：{msg}")

        if hanji and tailo:
            n_hanji = _count_hanji(hanji)
            n_syll = _count_syllables(tailo)
            # 容許 ±1 的誤差（合音、輕聲等），差距較大才提醒
            if abs(n_hanji - n_syll) >= 2:
                warnings.append(
                    f"對話第 {idx + 1} 句：漢字 {n_hanji} 字與臺羅 {n_syll} 音節數差距較大，"
                    f"請確認漢字與拼音是否對應。（{hanji}）"
                )

    return warnings


if __name__ == "__main__":
    sample = {
        "vocabulary": [{"hanji": "老闆"}, {"hanji": "菜市仔"}],
        "dialogues": [
            {"hanji": "你欲去買一些物件嗎？", "tailo_numeric": "li2 beh4 khi3 be2 mih8-kiann7"},
        ],
    }
    for w in check_lesson_content(sample):
        print("⚠️", w)
