# 核心模組單元測試 (test_modules.py)
import os
import sys
import json
import pytest

# 加入 src 到搜尋路徑
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from tailo.validator import tailo_numeric_to_diacritic, convert_sentence_numeric_to_diacritic
from rag.retriever import TaigiRetriever

def test_tailo_conversion():
    # 測試聲調轉換
    assert tailo_numeric_to_diacritic("tsiah8") == "tsia̍h"
    assert tailo_numeric_to_diacritic("png7") == "pn̄g"
    assert tailo_numeric_to_diacritic("tshai3") == "tshài"
    assert tailo_numeric_to_diacritic("tshi7") == "tshī"
    assert tailo_numeric_to_diacritic("a2") == "á"
    assert tailo_numeric_to_diacritic("Tai5") == "Tâi"
    assert tailo_numeric_to_diacritic("uan5") == "uân"
    assert tailo_numeric_to_diacritic("thak8") == "tha̍k"
    assert tailo_numeric_to_diacritic("tsheh4") == "tsheh"
    assert tailo_numeric_to_diacritic("iu5") == "iû"

def test_sentence_conversion():
    # 測試整句轉換
    sentence_num = "tsiah8-png7 e7-poo khī-tshai3-tshi7-a2"
    sentence_dia = convert_sentence_numeric_to_diacritic(sentence_num)
    # 驗證拼音轉換 (部分詞語如 e7-poo, khī 未在單元測試字庫中但仍應套用轉換規則)
    assert "tsia̍h-pn̄g" in sentence_dia
    assert "tshài-tshī-á" in sentence_dia

def test_retriever():
    retriever = TaigiRetriever()
    
    # 測試詞彙檢索
    results = retriever.retrieve_vocabulary("食飯")
    assert len(results) > 0
    assert results[0]["hanji"] == "食飯"
    assert results[0]["tailo_numeric"] == "tsiah8-png7"
    
    # 測試課綱年級過濾 (國中)
    syllabus_jh = retriever.retrieve_syllabus_by_grade("國中七年級")
    assert len(syllabus_jh) > 0
    # 確保含有國中七至九年級課綱
    assert any("1-Ⅳ-1" in item["code"] for item in syllabus_jh)

def test_enrichment():
    retriever = TaigiRetriever()
    
    # 測試教材結構豐富化
    lesson_draft = {
        "title": "菜市場買物件",
        "grade": "國中七年級",
        "vocabulary": ["食飯", "偌濟錢"],
        "dialogues": []
    }
    
    enriched = retriever.enrich_lesson_json(lesson_draft)
    
    # 1. 確保詞彙成功被豐富為物件
    assert isinstance(enriched["vocabulary"][0], dict)
    assert enriched["vocabulary"][0]["hanji"] == "食飯"
    assert enriched["vocabulary"][0]["tailo_numeric"] == "tsiah8-png7"
    
    # 2. 確保課綱自動被帶出
    assert len(enriched["curriculum"]["learning_performance"]) > 0
    assert any("1-Ⅳ-1" in x for x in enriched["curriculum"]["learning_performance"])

def test_tts_fetch_moedict(tmp_path):
    from tts.generator import TaigiTTS
    tts = TaigiTTS()
    # 測試下載「菜市仔」
    output_file = tmp_path / "vocab_菜市仔.ogg"
    success = tts.fetch_vocab_audio("菜市仔", str(output_file))
    assert success is True
    assert output_file.exists()
    assert output_file.stat().st_size > 0

def test_tts_dummy_synthesize(tmp_path):
    from tts.generator import TaigiTTS
    tts = TaigiTTS()
    # 強制設定為 dummy
    tts.provider = "dummy"
    output_file = tmp_path / "sentence.wav"
    success = tts.synthesize_sentence("這是一句測試句子", str(output_file))
    assert success is True
    assert output_file.exists()
    assert output_file.stat().st_size > 0
