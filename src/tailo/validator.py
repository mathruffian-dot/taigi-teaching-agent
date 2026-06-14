# 臺羅拼音格式轉換與檢核工具 (validator.py)
import re

# 教育部臺羅聲調符號對照表
TONE_MAP = {
    # 聲調 2 (á, é, í, ó, ú, ḿ, ńg)
    '2': {'a': 'á', 'e': 'é', 'i': 'í', 'o': 'ó', 'u': 'ú', 'm': 'ḿ', 'ng': 'ńg', 'A': 'Á', 'E': 'É', 'I': 'Í', 'O': 'Ó', 'U': 'Ú', 'M': 'Ḿ'},
    # 聲調 3 (à, è, ì, ò, ù, m̀, ǹg)
    '3': {'a': 'à', 'e': 'è', 'i': 'ì', 'o': 'ò', 'u': 'ù', 'm': 'm̀', 'ng': 'ǹg', 'A': 'À', 'E': 'È', 'I': 'Ì', 'O': 'Ò', 'U': 'Ù', 'M': 'M̀'},
    # 聲調 5 (â, ê, î, ô, û, m̂, n̂g)
    '5': {'a': 'â', 'e': 'ê', 'i': 'î', 'o': 'ô', 'u': 'û', 'm': 'm̂', 'ng': 'n̂g', 'A': 'Â', 'E': 'Ê', 'I': 'Î', 'O': 'Ô', 'U': 'Û', 'M': 'M̂'},
    # 聲調 7 (ā, ē, ī, ō, ū, m̄, n̄g)
    '7': {'a': 'ā', 'e': 'ē', 'i': 'ī', 'o': 'ō', 'u': 'ū', 'm': 'm̄', 'ng': 'n̄g', 'A': 'Ā', 'E': 'Ē', 'I': 'Ī', 'O': 'Ō', 'U': 'Ū', 'M': 'M̄'},
    # 聲調 8 (a̍, e̍, i̍, o̍, u̍, m̍, n̍g) - 採用 Unicode 組合字元 \u030d (Combining Vertical Line Above)
    '8': {'a': 'a̍', 'e': 'e̍', 'i': 'i̍', 'o': 'o̍', 'u': 'u̍', 'm': 'm̍', 'ng': 'n̍g', 'A': 'A̍', 'E': 'E̍', 'I': 'I̍', 'O': 'O̍', 'U': 'U̍', 'M': 'M̍'},
}

def tailo_numeric_to_diacritic(word: str) -> str:
    """
    將單個臺羅數字調單字（例如 tsiah8, png7, a2）轉換為調符式（例如 tsia̍h, pn̄g, á）。
    """
    # 匹配末尾數字聲調
    match = re.match(r'^([a-zA-Z̍\u030d\u0358]+)([1-9])$', word)
    if not match:
        return word  # 若無聲調數字或格式不符，直接返回原字
    
    syllable, tone = match.groups()
    
    # 聲調 1, 4, 6, 9 不需要標記變音符號（9為特殊三聲調）
    if tone in ['1', '4', '6', '9']:
        return syllable
    
    # 尋找放置調符的母音字母，順序優先級：a > o > e > i > u > (m/ng)
    # 1. 含有 'a' 則標在 'a' 上
    # 2. 含有 'oo' 標在第一個 'o' 上，若有 'o' 且非 'o' 結尾 (如 oa, oe) 則標在後續母音，
    #    但一般教育部規則：o 優先於 e/i/u。若有 oa/oe/oi，聲調標在後面的母音 (a/e/i)
    target_char = None
    
    lower_syllable = syllable.lower()
    
    if 'a' in lower_syllable:
        target_char = 'a' if 'a' in syllable else 'A'
    elif 'o' in lower_syllable:
        # 處理 oa, oe, oi 等情況，聲調標在後面的母音上
        if len(lower_syllable) > 1 and lower_syllable.index('o') < len(lower_syllable) - 1:
            next_char = lower_syllable[lower_syllable.index('o') + 1]
            if next_char in ['a', 'e', 'i']:
                target_char = syllable[lower_syllable.index('o') + 1]
        
        if not target_char:
            target_char = 'o' if 'o' in syllable else 'O'
    elif 'e' in lower_syllable:
        target_char = 'e' if 'e' in syllable else 'E'
    elif 'i' in lower_syllable and 'u' in lower_syllable:
        # iu 或 ui，標在後面的母音上
        if lower_syllable.index('i') < lower_syllable.index('u'):
            target_char = 'u' if 'u' in syllable else 'U'
        else:
            target_char = 'i' if 'i' in syllable else 'I'
    elif 'i' in lower_syllable:
        target_char = 'i' if 'i' in syllable else 'I'
    elif 'u' in lower_syllable:
        target_char = 'u' if 'u' in syllable else 'U'
    elif 'ng' in lower_syllable:
        target_char = 'ng' if 'ng' in syllable else 'NG'
    elif 'm' in lower_syllable:
        target_char = 'm' if 'm' in syllable else 'M'
        
    if target_char and tone in TONE_MAP and target_char in TONE_MAP[tone]:
        diacritic_char = TONE_MAP[tone][target_char]
        # 取代原字元
        # 注意若 target_char 為 'ng'，需特殊取代
        if target_char.lower() == 'ng':
            idx = lower_syllable.index('ng')
            return syllable[:idx] + diacritic_char + syllable[idx+2:]
        else:
            idx = syllable.index(target_char)
            return syllable[:idx] + diacritic_char + syllable[idx+1:]
            
    return syllable

def convert_sentence_numeric_to_diacritic(sentence: str) -> str:
    """
    將含有數字調的臺羅句子（例如 "tsiah8-pn̄g e7-poo khī-tshài-tshī-á"）轉換為調符式。
    """
    # 匹配所有含數字的臺羅音節字詞，考慮連字符
    def replace_match(m):
        word = m.group(0)
        # 用連字號分割多音節
        parts = word.split('-')
        converted = [tailo_numeric_to_diacritic(p) for p in parts]
        return '-'.join(converted)
        
    # 音節由英文母音子音與數字組成，並以連字符連接
    return re.sub(r'\b[a-zA-Z]+[1-9](?:-[a-zA-Z]+[1-9])*\b', replace_match, sentence)

if __name__ == '__main__':
    # 簡單單元測試
    test_words = {
        'tsia̍h-pn̄g': convert_sentence_numeric_to_diacritic('tsiah8-png7'),
        'tshài-tshī-á': convert_sentence_numeric_to_diacritic('tshai3-tshi7-a2'),
        'Tâi-uân': convert_sentence_numeric_to_diacritic('Tai5-uan5'),
        'tha̍k-tsheh': convert_sentence_numeric_to_diacritic('thak8-tsheh4'),
        'iu5': convert_sentence_numeric_to_diacritic('iu5')
    }
    for k, v in test_words.items():
        print(f"原始: {k} | 轉換: {v} | 結果: {'成功' if k == v else '失敗'}")
