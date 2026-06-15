# AI 教材大綱生成器 (outline_generator.py)
import os
import sys
import json
import requests
import argparse
from typing import Dict, Any, List

# 將當前與父目錄加入搜尋路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.dirname(current_dir))
sys.path.append(os.path.dirname(os.path.dirname(current_dir)))

from rag.retriever import TaigiRetriever
from generators.material_generator import MaterialGenerator
from generators.video_generator import TaigiVideoGenerator

from utils import safe_print
print = safe_print

class TaigiOutlineGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.retriever = TaigiRetriever()
        
        ollama_cfg = self.config.get("ollama", {})
        self.ollama_url = ollama_cfg.get("url", "http://localhost:11434")
        self.configured_model = ollama_cfg.get("model", "SARC-Taigi-LLM-12b:latest")

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    pass
        return {}

    def _get_available_models(self) -> List[str]:
        """
        取得本地 Ollama 伺服器中已下載的模型列表
        """
        try:
            url = f"{self.ollama_url}/api/tags"
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                data = res.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def _choose_model(self) -> str:
        """
        選擇可用模型。若配置模型不存在，自動挑選合適的本地替代模型。
        若 Ollama 未啟動，則拋出 ConnectionError。
        """
        models = self._get_available_models()
        if not models:
            raise ConnectionError("Ollama server offline or no models installed.")

        # 1. 優先使用配置的預設模型
        if self.configured_model in models:
            return self.configured_model
            
        # 2. 如果配置模型不帶 tag，進行模糊比對
        base_configured = self.configured_model.split(":")[0]
        for m in models:
            if m.startswith(base_configured):
                print(f"[*] 配置模型 「{self.configured_model}」 缺 tag，自動選擇本地替代：「{m}」")
                return m

        # 3. 若找不到台語模型，尋找 gemma、qwen 等大模型替代
        for m in models:
            if "gemma" in m or "qwen" in m or "llama" in m:
                print(f"[!] 警告: 未在 Ollama 中找到台語模型 「{self.configured_model}」。")
                print(f"    自動挑選本地可用替代模型：「{m}」 進行生成。")
                return m

        # 4. 兜底選取第一個可用模型
        print(f"[*] 自動挑選本地第一個可用模型：「{models[0]}」")
        return models[0]

    def generate_outline(self, prompt: str, grade: str, duration_minutes: int = 45) -> Dict[str, Any]:
        """
        生成台語教材 JSON 大綱。整合 RAG 檢索與 Ollama JSON 模型生成。
        """
        print(f"[*] 開始為主題 「{prompt}」 ({grade}) 生成教材大綱...")
        
        # 1. 透過 RAG 檢索常用詞庫 (做為 reference 提供給大模型)
        vocab_matches = self.retriever.retrieve_vocabulary(prompt)
        # 附上台羅拼音供 LLM 參考格式
        vocab_ref = [f"{v.get('hanji')} ({v.get('tailo_numeric')})" for v in vocab_matches[:8]]
        
        # 2. 透過 RAG 檢索對應年級的課綱績效
        syllabus_matches = self.retriever.retrieve_syllabus_by_grade(grade)
        syllabus_ref = [f"[{s.get('code')}] {s.get('description')}" for s in syllabus_matches[:5]]

        # 3. 偵測並選擇 LLM 模型
        try:
            model = self._choose_model()
            # 呼叫 Ollama 生成
            result = self._generate_via_ollama(
                model=model,
                prompt=prompt,
                grade=grade,
                duration=duration_minutes,
                vocab_ref=vocab_ref,
                syllabus_ref=syllabus_ref
            )
            # 驗證生成的拼音品質，不合格則降級
            if self._validate_outline(result):
                return result
            else:
                return self._generate_via_mock(prompt, grade, duration_minutes)
        except (ConnectionError, requests.exceptions.RequestException) as e:
            # 智慧降級：Ollama 未啟動或失敗，執行 Mock 模擬生成
            return self._generate_via_mock(prompt, grade, duration_minutes)

    def _generate_via_ollama(
        self, model: str, prompt: str, grade: str, duration: int,
        vocab_ref: List[str], syllabus_ref: List[str]
    ) -> Dict[str, Any]:
        """
        向 Ollama 發送 POST 請求，以 JSON 格式生成教材。
        """
        print(f"[*] 正在調用本地 Ollama 模型 「{model}」 生成 JSON 大綱...")
        url = f"{self.ollama_url}/api/chat"
        
        #         參考詞彙與課綱上下文
        ref_text = ""
        if vocab_ref:
            ref_text += f"參考詞彙庫已收錄台語詞: {', '.join(vocab_ref)}\n"
        if syllabus_ref:
            ref_text += f"參考108課綱指標:\n" + "\n".join(syllabus_ref) + "\n"

        system_instruction = f"""你是一位專業的臺灣台語教師，為 {grade} 學生設計一份台語教材大綱 JSON。

輸出必須是合法 JSON，不含 Markdown 標記或對話文字。

JSON Schema：
{{
  "title": "單元標題",
  "grade": "{grade}",
  "duration_minutes": {duration},
  "vocabulary": ["台語漢字詞1", "台語漢字詞2", "台語漢字詞3"],
  "dialogues": [
    {{
      "role": "角色名（如：阿偉）",
      "hanji": "台語漢字對話句",
      "tailo_numeric": "台羅數字調拼音",
      "zh_tw": "華語翻譯"
    }}
  ],
  "questions": [
    {{
      "id": "q1",
      "question": "題目",
      "options": ["選項1", "選項2", "選項3", "選項4"],
      "answer_index": 0,
      "explanation": "解析"
    }}
  ]
}}

⚠️ 台羅數字調拼音規範（嚴格遵守）：
- 聲調只能用 1,2,3,4,5,7,8（沒有 6,9,0）
- 音節格式：聲母+韻母+數字聲調，例：tsiah8, png7, a1, be2, tshai3, lai5
- 多音節用 - 連接：tsiah8-png7, a1-ma2, tshai3-tshi7-a2
- 聲母清單：p, ph, m, b, t, th, n, l, k, kh, ng, g, h, ts, tsh, s, j
- 韻母例：a, e, i, o, oo, u, ai, au, ia, iu, ua, ue, ui, iau, uai, am, an, ang, eng, ian, iang, iong, im, in, ing, om, ong, un, uan
- ❌ 嚴禁使用普通話拼音（qiao, lun, ni, san, yu 等）
- ❌ 嚴禁使用簡體字或中國用語
- ❌ 嚴禁所有選項內容完全相同

規範：
1. vocabulary 提供 3-5 個教育部推薦台語漢字詞
2. dialogues 提供 3-4 句自然台語情境對話
3. questions 提供 3 題，每題 4 個不同選項
4. grade 必須是繁體中文（如「國中七年級」非「七年级」）

{ref_text}
"""

        user_content = f"請為主題 「{prompt}」 ({grade}) 產生教學大綱 JSON。"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content}
            ],
            "format": "json",
            "stream": False
        }

        try:
            res = requests.post(url, json=payload, timeout=60)
            if res.status_code == 200:
                content = res.json().get("message", {}).get("content", "").strip()
                return self._parse_json_response(content)
            else:
                print(f"  [-] Ollama 呼叫失敗: HTTP {res.status_code}")
                # 失敗時降級為 mock
                return self._generate_via_mock(prompt, grade, duration)
        except Exception as e:
            print(f"  [-] Ollama 呼叫發生異常: {str(e)}")
            return self._generate_via_mock(prompt, grade, duration)

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        解析 LLM 回傳的 JSON，處理可能包夾的 Markdown 標記
        """
        clean_text = text.strip()
        # 去除 markdown 標記
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                clean_text = "\n".join(lines[1:-1]).strip()
                
        try:
            return json.loads(clean_text)
        except Exception as e:
            print(f"  [-] JSON 解析失敗: {str(e)}。回傳內容: {text[:100]}...")
            raise e

    def _validate_outline(self, data: Dict[str, Any]) -> bool:
        """
        驗證 Ollama 生成的大綱品質。檢查台羅拼音格式、選項數量、年級格式等。
        回傳 True 表示通過，False 表示品質不合格應降級為 Mock。
        """
        import re
        
        issues = []
        
        # 1. 檢查 grade 是否繁體中文格式（不能是簡體 "七年级"）
        grade = data.get("grade", "")
        if "七" in grade and "级" in grade:
            issues.append("年級使用簡體中文")
        
        # 2. 檢查詞彙是否為台語漢字（至少要有漢字）
        vocab = data.get("vocabulary", [])
        if len(vocab) < 2:
            issues.append("詞彙少於 2 個")
        
        # 3. 檢查對話的台羅拼音品質
        dialogues = data.get("dialogues", [])
        invalid_tailo_count = 0
        tailo_syllable_pattern = re.compile(
            r'^[ptkbmnlghjzcs][a-z]*[1-8]$|^[aouei][a-z]*[1-8]$|^[mng]+[1-8]$'
        )
        mandarin_pinyin_pattern = re.compile(r'[qvx]')
        
        for dia in dialogues:
            tn = dia.get("tailo_numeric", "")
            # 檢查是否含有普通話拼音特徵
            if mandarin_pinyin_pattern.search(tn.lower()):
                invalid_tailo_count += 1
                continue
            # 檢查是否含有非法聲調 (6, 9, 0)
            if re.search(r'[69]($|[^0-9])|[a-z]0', tn):
                invalid_tailo_count += 1
                continue
            # 分離音節並驗證格式
            cleaned = re.sub(r'[，。！？、；：\?\.,!]', ' ', tn)
            syllables = re.split(r'[\s\-]+', cleaned)
            valid_syllables = 0
            for s in syllables:
                s = s.strip()
                if not s:
                    continue
                if tailo_syllable_pattern.match(s):
                    valid_syllables += 1
            if valid_syllables == 0 and len(syllables) > 0:
                invalid_tailo_count += 1
        
        if invalid_tailo_count > 0:
            issues.append(f"對話中有 {invalid_tailo_count} 句的台羅拼音格式不合規")
        
        # 4. 檢查題目選項是否重複
        questions = data.get("questions", [])
        for q in questions:
            options = q.get("options", [])
            if len(options) < 4:
                issues.append(f"題目 {q.get('id')} 只有 {len(options)} 個選項（需要 4 個）")
            if len(set(options)) != len(options):
                issues.append(f"題目 {q.get('id')} 有重複選項")
        
        if issues:
            print(f"  [!] 大綱品質驗證失敗：{'；'.join(issues)}")
            print(f"  [!] 自動降級為 Mock 離線模式。")
            return False
        
        print(f"  [+] 大綱品質驗證通過。")
        return True

    def _generate_via_mock(self, prompt: str, grade: str, duration: int) -> Dict[str, Any]:
        """
        Mock 降級生成模式：當本地 Ollama 未開啟或異常時，使用規則與範本組裝出合法的教材 Outline JSON。
        """
        print(f"[!] 偵測到本地 Ollama 伺服器未啟動或無模型。自動切換至離線模擬大綱生成器...")
        
        # 針對菜市仔或購物主題
        if "菜市" in prompt or "買" in prompt or "錢" in prompt:
            return {
                "title": f"情境會話：{prompt}",
                "grade": grade,
                "duration_minutes": duration,
                "vocabulary": ["菜市仔", "買物件", "偌濟錢", "多謝"],
                "dialogues": [
                    {
                        "role": "阿偉",
                        "hanji": "阿媽，咱今仔日欲去菜市仔買物件無？",
                        "tailo_numeric": "a1-ma2, lan2 kin1-a2-jit8 beh4 khi3 tshai3-tshi7-a2 be2-mih8-kiann7 bo5?",
                        "zh_tw": "阿嬤，我們今天要去菜市場買東西嗎？"
                    },
                    {
                        "role": "阿媽",
                        "hanji": "有啊，咱欲來去買一些魚仔、肉跟菜，順便買你愛食的麵包。",
                        "tailo_numeric": "u7-a2, lan2 beh4 lai5-khi3 be2 tsit-khua2 hi5-a2, bah kap tshai3, sun7-pien7 be2 li2 ai3 tsiah8 e5 mian7-pao1.",
                        "zh_tw": "有啊，我們要來去買一些魚、肉和菜，順便買你愛吃的麵包。"
                    },
                    {
                        "role": "阿偉",
                        "hanji": "阿媽，這个魚仔一斤偌濟錢？",
                        "tailo_numeric": "a1-ma2, tsit-e5 hi5-a2 tsit-kin1 gua7-tse7-tsinn2?",
                        "zh_tw": "阿嬤，這個魚一斤多少錢？"
                    },
                    {
                        "role": "阿媽",
                        "hanji": "一斤兩百塊，多謝老闆。",
                        "tailo_numeric": "tsit-kin1 nn7-pah-khoo1, to1-sia7 lau7-pan7.",
                        "zh_tw": "一斤兩百元，多謝老闆。"
                    }
                ],
                "questions": [
                    {
                        "id": "q1",
                        "question": "「菜市仔」的臺羅拼音是甚麼？",
                        "options": [
                            "tshài-tshī-á (tshai3-tshi7-a2)",
                            "tsiah8-png7 (tsia̍h-pn̄g)",
                            "bé-mi̍h-kiānn (be2-mih8-kiann7)",
                            "to-siā (to1-sia7)"
                        ],
                        "answer_index": 0,
                        "explanation": "「菜市仔」指菜市場，臺羅標音為 tshài-tshī-á。"
                    },
                    {
                        "id": "q2",
                        "question": "對話中阿偉問阿媽魚一斤多少錢，使用了哪一個台語詞彙？",
                        "options": [
                            "讀冊 (tha̍k-tsheh)",
                            "偌濟錢 (guā-tsē-tsînn)",
                            "多謝 (to-siā)",
                            "好食 (hó-tsia̍h)"
                        ],
                        "answer_index": 1,
                        "explanation": "「偌濟錢」在台語中意為「多少錢」，是用來詢問價格的常用詞彙。"
                    },
                    {
                        "id": "q3",
                        "question": "阿媽說「一斤兩百塊」，「兩百塊」的台語數字拼音怎麼寫？",
                        "options": [
                            "tsit-kin1 (一斤)",
                            "nn̄g-pah (兩百)",
                            "tsit-pah (一百)",
                            "saⁿ-pah (三百)"
                        ],
                        "answer_index": 1,
                        "explanation": "「兩百」的台語發音為 nn̄g-pah (聲調為 nn7-pah4)。"
                    }
                ]
            }
        else:
            # 預設通用模擬資料 (關於吃飯、學習)
            return {
                "title": f"情境會話：{prompt}",
                "grade": grade,
                "duration_minutes": duration,
                "vocabulary": ["食飯", "讀冊", "多謝"],
                "dialogues": [
                    {
                        "role": "老師",
                        "hanji": "學生，咱準備欲來食飯無？",
                        "tailo_numeric": "hak8-sing1, lan2 tshun2-pi7 beh4 lai5 tsiah8-png7 bo5?",
                        "zh_tw": "學生，我們準備要來吃飯了嗎？"
                    },
                    {
                        "role": "學生",
                        "hanji": "有啊，我腹肚真枵，多謝老師！",
                        "tailo_numeric": "u7-a2, gua2 pak8-too2 tsin1 iau1, to1-sia7 lau7-si1!",
                        "zh_tw": "有啊，我肚子很餓，多謝老師！"
                    },
                    {
                        "role": "老師",
                        "hanji": "食飽了後，咱欲來去讀冊囉！",
                        "tailo_numeric": "tsiah8-pa2 liau2-au7, lan2 beh4 lai5-khi3 thak8-tsheh4 lo1!",
                        "zh_tw": "吃飽之後，我們要來去讀書囉！"
                    }
                ],
                "questions": [
                    {
                        "id": "q1",
                        "question": "「食飯」的台羅發音是什麼？",
                        "options": [
                            "tsia̍h-pn̄g (tsiah8-png7)",
                            "tha̍k-tsheh (thak8-tsheh4)",
                            "to-siā (to1-sia7)",
                            "lāu-su (lau7-si1)"
                        ],
                        "answer_index": 0,
                        "explanation": "「食飯」的台語發音為 tsia̍h-pn̄g。"
                    },
                    {
                        "id": "q2",
                        "question": "學生說他很餓，「肚子餓」的台語怎麼寫？",
                        "options": [
                            "腹肚真枵 (pak8-too2 tsin1 iau1)",
                            "食飽 (tsiah8-pa2)",
                            "讀冊 (thak8-tsheh4)",
                            "多謝 (to1-sia7)"
                        ],
                        "answer_index": 0,
                        "explanation": "「肚子餓」台語說「腹肚枵 (pak-tōo iau)」，「真枵」即很餓。"
                    },
                    {
                        "id": "q3",
                        "question": "「讀冊」的華語意思是什麼？",
                        "options": [
                            "吃飯",
                            "讀書/上學",
                            "謝謝",
                            "老師"
                        ],
                        "answer_index": 1,
                        "explanation": "「讀冊」在台語中意為「讀書」或「上學」，是學校生活中常用的詞彙。"
                    }
                ]
            }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--prompt", required=True, help="教學單元主題")
    parser.add_argument("--grade", default="國中七年級", help="適用年級")
    parser.add_argument("--output", help="輸出之 JSON 大綱路徑")
    parser.add_argument("--compile", action="store_true", help="是否直接鏈接教材生成器編譯成講義與互動網站")
    args = parser.parse_args()

    generator = TaigiOutlineGenerator(args.config)
    outline_data = generator.generate_outline(args.prompt, args.grade)

    # 決定輸出路徑
    out_path = args.output
    if not out_path:
        # 預設儲存於 output/lessons/
        lesson_dir = "output/lessons"
        os.makedirs(lesson_dir, exist_ok=True)
        # 用主題做為檔名
        safe_title = "".join(x for x in args.prompt if x.isalnum())
        out_path = os.path.join(lesson_dir, f"outline_{safe_title}.json")

    # 寫入檔案
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(outline_data, f, ensure_ascii=False, indent=2)
    print(f"  [+] 已將教材大綱 JSON 存入: {out_path}")

    # 若啟用了一鍵連鎖編譯
    if args.compile:
        print("\n[*] 鏈接教材編譯程序中 (MaterialGenerator)...")
        compiler = MaterialGenerator(args.config)
        compiler.generate_all(out_path)
        
        print("\n[*] 鏈接教學影片生成器中 (TaigiVideoGenerator)...")
        lesson_structure_path = "output/lesson_structure.json"
        video_output_path = "output/lesson_video.mp4"
        
        video_gen = TaigiVideoGenerator(args.config)
        video_success = video_gen.generate_video(lesson_structure_path, video_output_path)
        if video_success:
            print(f"[+] 一鍵影片編譯完成！影片路徑: {video_output_path}")
        else:
            print("[-] 影片編譯失敗，請檢查日誌。")
            
        print("[*] 一鍵連鎖全套教材與教學影片編譯完成！")
