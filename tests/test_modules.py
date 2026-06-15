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

def test_api_stt_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from server import app
    from stt.generator import TaigiSTT
    
    # Mock stt.speech_to_text 避免 real ASR 在 API 測試中干擾
    monkeypatch.setattr(TaigiSTT, "speech_to_text", lambda self, p, t="": t)
    
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

def test_outline_generator_mock_default():
    from agent.outline_generator import TaigiOutlineGenerator
    generator = TaigiOutlineGenerator()
    generator._get_available_models = lambda: []
    
    outline = generator.generate_outline("在茶莊品茶", "國中七年級")
    assert outline["title"] == "情境會話：在茶莊品茶"
    assert outline["grade"] == "國中七年級"
    assert len(outline["vocabulary"]) == 3
    assert "食飯" in outline["vocabulary"]
    assert len(outline["dialogues"]) == 3
    assert len(outline["questions"]) == 3  # 驗證已補上第 3 題
    assert outline["questions"][2]["id"] == "q3"

def test_outline_generator_compile_flag(monkeypatch, tmp_path):
    from agent.outline_generator import TaigiOutlineGenerator
    generator = TaigiOutlineGenerator()
    generator._get_available_models = lambda: []
    
    outline = generator.generate_outline("去菜市仔買物件", "國中七年級")
    assert outline["vocabulary"][0] == "菜市仔"
    assert len(outline["dialogues"]) == 4

def test_image_generator_config_url():
    from generators.image_generator import FreeImageGenerator
    import json, tempfile, os
    
    config = {"ollama": {"url": "http://localhost:9999", "model": "test-model"}}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(config, tmp)
    tmp.close()
    
    try:
        gen = FreeImageGenerator(tmp.name)
        assert gen.ollama_url == "http://localhost:9999"
    finally:
        os.unlink(tmp.name)

def test_sentence_conversion_mixed():
    from tailo.validator import convert_sentence_numeric_to_diacritic
    result = convert_sentence_numeric_to_diacritic("tsiah8-png7 to1-sia7")
    assert "tsia̍h-pn̄g" in result
    assert "to-siā" in result

def test_tailo_iou_ui_rules():
    from tailo.validator import tailo_numeric_to_diacritic
    assert tailo_numeric_to_diacritic("iu5") == "iû"
    assert tailo_numeric_to_diacritic("ui7") == "uī"
    assert tailo_numeric_to_diacritic("gue5") == "guê"
    assert tailo_numeric_to_diacritic("ng5") == "n̂g"
    assert tailo_numeric_to_diacritic("m7") == "m̄"

def test_retriever_no_results():
    from rag.retriever import TaigiRetriever
    retriever = TaigiRetriever()
    results = retriever.retrieve_vocabulary("不存在的詞彙xyz")
    assert len(results) == 0

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

def test_stt_local_whisper_integration(tmp_path):
    from stt.generator import TaigiSTT
    stt = TaigiSTT()
    # 強制設定為 whisper 模式以執行實體推理
    stt.provider = "whisper"
    stt.stt_config["local_model_size"] = "tiny"
    
    # 藉由 TaigiTTS 下載一個合法的台語語音檔 (例如「食飯」)
    from tts.generator import TaigiTTS
    tts = TaigiTTS()
    audio_file = tmp_path / "vocab_食飯.ogg"
    fetch_success = tts.fetch_vocab_audio("食飯", str(audio_file))
    
    if fetch_success:
        recognized = stt.speech_to_text(str(audio_file))
        assert len(recognized) > 0

def test_outline_validator_rejects_bad_romanization():
    from agent.outline_generator import TaigiOutlineGenerator
    gen = TaigiOutlineGenerator()
    
    bad_data = {
        "title": "測試",
        "grade": "國中七年級",
        "duration_minutes": 45,
        "vocabulary": ["食飯", "買物件"],
        "dialogues": [
            {
                "role": "阿偉",
                "hanji": "你好",
                "tailo_numeric": "qiao2-lun4-ni3-san4",
                "zh_tw": "你好"
            }
        ],
        "questions": [
            {
                "id": "q1",
                "question": "測試",
                "options": ["A", "B", "C", "D"],
                "answer_index": 0,
                "explanation": "測試"
            }
        ]
    }
    assert gen._validate_outline(bad_data) is False

def test_outline_validator_rejects_grade_simplified():
    from agent.outline_generator import TaigiOutlineGenerator
    gen = TaigiOutlineGenerator()
    
    data = {
        "title": "測試",
        "grade": "七年级",
        "duration_minutes": 45,
        "vocabulary": ["食飯", "買物件"],
        "dialogues": [
            {
                "role": "阿偉",
                "hanji": "咱來去食飯",
                "tailo_numeric": "lan2 lai5-khi3 tsiah8-png7",
                "zh_tw": "我們來去吃飯"
            }
        ],
        "questions": [
            {
                "id": "q1",
                "question": "測試",
                "options": ["A", "B", "C", "D"],
                "answer_index": 0,
                "explanation": "測試"
            }
        ]
    }
    assert gen._validate_outline(data) is False

def test_outline_validator_rejects_duplicate_options():
    from agent.outline_generator import TaigiOutlineGenerator
    gen = TaigiOutlineGenerator()
    
    data = {
        "title": "測試",
        "grade": "國中七年級",
        "duration_minutes": 45,
        "vocabulary": ["食飯", "買物件"],
        "dialogues": [
            {
                "role": "阿偉",
                "hanji": "咱來去食飯",
                "tailo_numeric": "lan2 lai5-khi3 tsiah8-png7",
                "zh_tw": "我們來去吃飯"
            }
        ],
        "questions": [
            {
                "id": "q1",
                "question": "測試",
                "options": ["相同", "相同", "相同", "相同"],
                "answer_index": 0,
                "explanation": "測試"
            }
        ]
    }
    assert gen._validate_outline(data) is False

def test_outline_validator_accepts_good_data():
    from agent.outline_generator import TaigiOutlineGenerator
    gen = TaigiOutlineGenerator()
    
    good_data = {
        "title": "情境會話：去菜市仔買物件",
        "grade": "國中七年級",
        "duration_minutes": 45,
        "vocabulary": ["菜市仔", "買物件", "偌濟錢"],
        "dialogues": [
            {
                "role": "阿偉",
                "hanji": "阿媽，咱今仔日欲去菜市仔買物件無？",
                "tailo_numeric": "a1-ma2 lan2 kin1-a2-jit8 beh4 khi3 tshai3-tshi7-a2 be2-mih8-kiann7 bo5",
                "zh_tw": "阿嬤，我們今天要去菜市場買東西嗎？"
            }
        ],
        "questions": [
            {
                "id": "q1",
                "question": "測試題目",
                "options": ["選項A", "選項B", "選項C", "選項D"],
                "answer_index": 0,
                "explanation": "解析說明"
            }
        ]
    }
    assert gen._validate_outline(good_data) is True

def test_html_pronunciation_eval_not_broken(tmp_path):
    """回歸測試：確保產生的互動網頁 JS 樣板字串沒有多餘的 $（曾導致發音評估功能整個失效）。"""
    from generators.material_generator import MaterialGenerator
    gen = MaterialGenerator()

    data = {
        "title": "測試單元",
        "grade": "國中七年級",
        "duration_minutes": 45,
        "curriculum": {"learning_performance": [], "learning_content": []},
        "vocabulary": [
            {"hanji": "食飯", "tailo_diacritic": "tsia̍h-pn̄g", "zh_tw": "吃飯",
             "audio_file": "audio/vocab_食飯.wav", "image_file": ""}
        ],
        "dialogues": [
            {"role": "阿偉", "hanji": "咱來去食飯", "tailo_diacritic": "lán lâi-khì tsia̍h-pn̄g",
             "zh_tw": "我們來去吃飯", "audio_file": "audio/dialogue_0.wav"}
        ],
        "questions": [
            {"id": "q1", "question": "測試", "options": ["A", "B", "C", "D"],
             "answer_index": 0, "explanation": "解析"}
        ]
    }

    gen._generate_html(data, str(tmp_path))
    html = (tmp_path / "interactive_website.html").read_text(encoding="utf-8")

    # 1. 絕不能再出現多餘的 $${ 樣式（這是先前的 bug）
    assert "$${" not in html
    # 2. 正確的 JS 樣板插值應原樣輸出
    assert "evaluateSpeech(event, '${type}', ${idx}, '${targetText}')" in html
    assert "playRecord(event, '${audioUrl}')" in html
    assert "${scoreClass}" in html


def test_html_handles_empty_role(tmp_path):
    """role 為空字串時不應拋 IndexError。"""
    from generators.material_generator import MaterialGenerator
    gen = MaterialGenerator()
    data = {
        "title": "測試", "grade": "國中七年級", "duration_minutes": 45,
        "curriculum": {"learning_performance": [], "learning_content": []},
        "vocabulary": [],
        "dialogues": [{"role": "", "hanji": "test", "tailo_diacritic": "test",
                       "zh_tw": "測試", "audio_file": ""}],
        "questions": []
    }
    gen._generate_html(data, str(tmp_path))  # 不應拋例外
    assert (tmp_path / "interactive_website.html").exists()


def test_vocabulary_db_expanded():
    from rag.retriever import TaigiRetriever
    retriever = TaigiRetriever()
    
    assert len(retriever.vocabulary_db) >= 30
    
    categories = {
        "食物": ["咖啡", "茶", "牛奶", "果子", "麵包"],
        "家人": ["阿公", "阿爸", "阿母", "小妹"],
        "學校": ["學校", "先生", "考試", "寫字"],
        "時間": ["今仔日", "明仔載", "昨昏"],
        "生活": ["你好", "再會", "電腦", "手機", "電影", "火車", "醫生", "公園"]
    }
    
    for cat, words in categories.items():
        for w in words:
            results = retriever.retrieve_vocabulary(w)
            assert len(results) > 0, f"找不到 {cat} 類詞彙: {w}"
            assert results[0]["hanji"] == w
            assert "pending" not in results[0].get("tailo_numeric", "")

