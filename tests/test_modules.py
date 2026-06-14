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

def test_stt_dummy(tmp_path):
    from stt.generator import TaigiSTT
    stt = TaigiSTT()
    stt.provider = "dummy"
    
    # 建立一個測試用的虛擬檔案
    audio_file = tmp_path / "test.webm"
    audio_file.write_bytes(b"dummy")
    
    recognized = stt.speech_to_text(str(audio_file), target_text="買物件")
    assert recognized == "買物件"

def test_api_stt_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from server import app
    
    client = TestClient(app)
    
    # 建立一個測試用的音訊檔案
    test_file = tmp_path / "test.webm"
    test_file.write_bytes(b"dummy audio content")
    
    with open(test_file, "rb") as f:
        response = client.post(
            "/api/stt",
            files={"file": ("test.webm", f, "audio/webm")},
            data={"target_text": "多謝"}
        )
        
    assert response.status_code == 200
    assert response.json() == {"text": "多謝"}

def test_outline_generator_mock():
    from agent.outline_generator import TaigiOutlineGenerator
    generator = TaigiOutlineGenerator()
    # 關閉 Ollama 模擬離線
    generator._get_available_models = lambda: []
    
    outline = generator.generate_outline("去菜市仔買物件", "國中七年級")
    assert outline["title"] == "情境會話：去菜市仔買物件"
    assert outline["grade"] == "國中七年級"
    assert "菜市仔" in outline["vocabulary"]
    assert len(outline["dialogues"]) > 0
    assert len(outline["questions"]) == 3

def test_outline_generator_choose_model():
    from agent.outline_generator import TaigiOutlineGenerator
    generator = TaigiOutlineGenerator()
    
    # 1. 測試預設模型存在時，選擇預設模型
    generator.configured_model = "SARC-Taigi-LLM-12b:latest"
    generator._get_available_models = lambda: ["SARC-Taigi-LLM-12b:latest", "gemma4:12b"]
    assert generator._choose_model() == "SARC-Taigi-LLM-12b:latest"
    
    # 2. 測試預設模型不存在時，自動選擇本地替代大模型 (例如 gemma4)
    generator._get_available_models = lambda: ["gemma4:12b", "qwen2.5-coder:1.5b"]
    assert generator._choose_model() == "gemma4:12b"

def test_free_image_generator(tmp_path, monkeypatch):
    from generators.image_generator import FreeImageGenerator
    import requests
    
    gen = FreeImageGenerator()
    # Mock 翻譯為 "apple"
    gen.translate_to_english_prompt = lambda x: "apple"
    
    # 建立 Mock 的 Response 物件
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
            self.content = b"fake image bytes"
            self.text = json.dumps(json_data)
            
        def json(self):
            return self.json_data
            
    # Mock post (提交任務)
    def mock_post(*args, **kwargs):
        return MockResponse({"id": "mock-task-123"}, 202)
        
    # Mock get (狀態查詢與下載)
    def mock_get(url, *args, **kwargs):
        if "check" in url:
            return MockResponse({"done": True}, 200)
        elif "status" in url:
            return MockResponse({
                "generations": [{"img": "https://example.com/mock.jpg"}]
            }, 200)
        else:
            # 下載圖片
            return MockResponse({}, 200)
            
    monkeypatch.setattr(requests, "post", mock_post)
    monkeypatch.setattr(requests, "get", mock_get)
    
    out_path = tmp_path / "vocab_apple.jpg"
    success = gen.generate_image("蘋果", str(out_path), width=128, height=128)
    assert success is True
    assert out_path.exists()
    assert out_path.read_bytes() == b"fake image bytes"

def test_video_generator_basic():
    from generators.video_generator import TaigiVideoGenerator
    gen = TaigiVideoGenerator()
    # 測試時長獲取預設值
    assert gen.get_audio_duration("") == 3.0

