# 臺語教材生成器主程式 (material_generator.py)
import os
import sys
import json
import argparse
from typing import Dict, Any

# 加入專案 src 目錄到路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.retriever import TaigiRetriever
from tailo.validator import convert_sentence_numeric_to_diacritic

class MaterialGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.retriever = TaigiRetriever()

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def generate_all(self, case_path: str, output_dir: str = "output"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 1. 讀取輸入測試案例
        with open(case_path, "r", encoding="utf-8") as f:
            case_data = json.load(f)

        print(f"[*] 讀取測試案例: {case_data.get('title', '未命名')}")

        # 2. 透過 RAG 豐富課綱與詞彙庫資料
        print("[*] 執行 RAG 知識庫檢索與欄位豐富化...")
        enriched_data = self.retriever.enrich_lesson_json(case_data)

        # 3. 處理台羅拼音轉換 (數值調 -> 調符式)
        print("[*] 處理台羅拼音數值調至調符式之自動轉換...")
        for vocab in enriched_data.get("vocabulary", []):
            if vocab.get("tailo_numeric") and vocab.get("tailo_numeric") != "pending":
                vocab["tailo_diacritic"] = convert_sentence_numeric_to_diacritic(vocab["tailo_numeric"])
                
        for dia in enriched_data.get("dialogues", []):
            if dia.get("tailo_numeric"):
                dia["tailo_diacritic"] = convert_sentence_numeric_to_diacritic(dia["tailo_numeric"])

        # 保存豐富化後的教材結構資料
        json_output = os.path.join(output_dir, "lesson_structure.json")
        with open(json_output, "w", encoding="utf-8") as f:
            json.dump(enriched_data, f, ensure_ascii=False, indent=2)
        print(f"  [+] 已產生教材結構 JSON: {json_output}")

        # 4. 產生講義 (Word DOCX)
        self._generate_docx(enriched_data, output_dir)

        # 5. 產生互動網站 (離線單一 HTML)
        self._generate_html(enriched_data, output_dir)

        # 6. 產生教師審核報告
        self._generate_review_report(enriched_data, output_dir)

    def _generate_docx(self, data: Dict[str, Any], output_dir: str):
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml import parse_xml
            from docx.oxml.ns import nsdecls
            
            def set_cell_shading(cell, color_hex):
                shading_xml = f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>'
                cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))
                
            def style_run(run, font_name="Arial", size_pt=11, bold=False, color_rgb=None):
                run.font.name = font_name
                run.font.size = Pt(size_pt)
                run.bold = bold
                if color_rgb:
                    run.font.color.rgb = color_rgb

            # ==================== 學生版講義 ====================
            doc_student = Document()
            title_p = doc_student.add_paragraph()
            title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title_p.add_run(f"臺語學習講義：{data.get('title')}")
            style_run(run, "微軟正黑體", 18, True, RGBColor(11, 60, 48))
            
            meta_p = doc_student.add_paragraph()
            meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = meta_p.add_run(f"適用年級：{data.get('grade')} | 課程時間：{data.get('duration_minutes')} 分鐘 | 姓名：___________ 座號：_____")
            style_run(run, "微軟正黑體", 10, False, RGBColor(82, 100, 95))
            
            # 1. 課綱指標
            h1 = doc_student.add_paragraph()
            style_run(h1.add_run("一、學習目標與課綱指標對照"), "微軟正黑體", 14, True, RGBColor(11, 60, 48))
            for perf in data.get("curriculum", {}).get("learning_performance", []):
                p = doc_student.add_paragraph()
                style_run(p.add_run(f"• 學習表現：{perf}"), "新細明體", 10, False)
            for cont in data.get("curriculum", {}).get("learning_content", []):
                p = doc_student.add_paragraph()
                style_run(p.add_run(f"• 學習內容：{cont}"), "新細明體", 10, False)
                
            # 2. 詞彙表 (美化斑馬紋表格)
            h2 = doc_student.add_paragraph()
            style_run(h2.add_run("二、核心詞彙認讀與手寫練習"), "微軟正黑體", 14, True, RGBColor(11, 60, 48))
            
            table = doc_student.add_table(rows=1, cols=4)
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = '臺語漢字'
            hdr_cells[1].text = '教育部臺羅拼音'
            hdr_cells[2].text = '華語翻譯'
            hdr_cells[3].text = '手寫練習 (漢字與拼音)'
            
            # 設定表頭顏色 (主題墨綠)
            for cell in hdr_cells:
                set_cell_shading(cell, "0B3C30")
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for r in p.runs:
                        style_run(r, "微軟正黑體", 10, True, RGBColor(255, 255, 255))
            
            row_count = 0
            for vocab in data.get("vocabulary", []):
                row_cells = table.add_row().cells
                row_cells[0].text = vocab.get("hanji", "")
                row_cells[1].text = vocab.get("tailo_diacritic", "")
                row_cells[2].text = vocab.get("zh_tw", "")
                row_cells[3].text = "__________________"
                
                # 斑馬紋底色
                row_color = "F6F8F6" if row_count % 2 == 1 else "FFFFFF"
                for i, cell in enumerate(row_cells):
                    set_cell_shading(cell, row_color)
                    p = cell.paragraphs[0]
                    # 前三欄置中，手寫欄靠左
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i < 3 else WD_ALIGN_PARAGRAPH.LEFT
                    for r in p.runs:
                        style_run(r, "新細明體" if i != 1 else "Arial", 10, False, RGBColor(47, 62, 70))
                row_count += 1
                
            # 3. 情境對話
            doc_student.add_paragraph() # 空行
            h3 = doc_student.add_paragraph()
            style_run(h3.add_run("三、情境會話認讀 (口說與聆聽)"), "微軟正黑體", 14, True, RGBColor(11, 60, 48))
            for dia in data.get("dialogues", []):
                p = doc_student.add_paragraph()
                r_role = p.add_run(f"🗣️ {dia.get('role')}：")
                style_run(r_role, "微軟正黑體", 11, True, RGBColor(184, 134, 11))
                r_text = p.add_run(dia.get('hanji'))
                style_run(r_text, "新細明體", 11, False)
                
                p_py = doc_student.add_paragraph()
                r_py = p_py.add_run(f"   [{dia.get('tailo_diacritic')}]")
                style_run(r_py, "Arial", 10, False, RGBColor(82, 100, 95))
                
                p_zh = doc_student.add_paragraph()
                r_zh = p_zh.add_run(f"   (請寫出此句華語意譯：__________________________________)")
                style_run(r_zh, "新細明體", 10, False, RGBColor(127, 140, 141))
                
            # 4. 評量題目
            doc_student.add_paragraph()
            h4 = doc_student.add_paragraph()
            style_run(h4.add_run("四、課堂自我檢測 (隨堂測驗)"), "微軟正黑體", 14, True, RGBColor(11, 60, 48))
            q_count = 1
            for q in data.get("questions", []):
                p = doc_student.add_paragraph()
                style_run(p.add_run(f"({q_count}) {q.get('question')}"), "微軟正黑體", 11, True)
                for idx, opt in enumerate(q.get("options", [])):
                    p_opt = doc_student.add_paragraph()
                    style_run(p_opt.add_run(f"    [  ] {opt}"), "新細明體", 10, False)
                q_count += 1
                
            student_path = os.path.join(output_dir, "student_worksheet.docx")
            doc_student.save(student_path)
            print(f"  [+] 已產生學生版講義 Word: {student_path}")
            
            # ==================== 教師解答版講義 ====================
            doc_teacher = Document()
            title_p = doc_teacher.add_paragraph()
            title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title_p.add_run(f"臺語學習講義 (教師解答指導版)：{data.get('title')}")
            style_run(run, "微軟正黑體", 18, True, RGBColor(184, 134, 11))
            
            h1 = doc_teacher.add_paragraph()
            style_run(h1.add_run("一、核心對話與翻譯解答"), "微軟正黑體", 14, True, RGBColor(11, 60, 48))
            for dia in data.get("dialogues", []):
                p = doc_teacher.add_paragraph()
                style_run(p.add_run(f"🗣️ {dia.get('role')}：{dia.get('hanji')}"), "微軟正黑體", 11, True)
                p_ans = doc_teacher.add_paragraph()
                r_ans = p_ans.add_run(f"   [翻譯解答] {dia.get('zh_tw')}")
                style_run(r_ans, "微軟正黑體", 10, True, RGBColor(180, 40, 40))
                
            h2 = doc_teacher.add_paragraph()
            style_run(h2.add_run("二、評量測驗答案與解析"), "微軟正黑體", 14, True, RGBColor(11, 60, 48))
            q_count = 1
            for q in data.get("questions", []):
                p = doc_teacher.add_paragraph()
                style_run(p.add_run(f"({q_count}) {q.get('question')}"), "微軟正黑體", 11, True)
                
                ans_text = q.get("options")[q.get("answer_index")]
                p_ans = doc_teacher.add_paragraph()
                r_ans = p_ans.add_run(f"   ★ 正確答案: {ans_text}")
                style_run(r_ans, "微軟正黑體", 10, True, RGBColor(180, 40, 40))
                
                p_exp = doc_teacher.add_paragraph()
                r_exp = p_exp.add_run(f"   [解析說明] {q.get('explanation')}")
                style_run(r_exp, "新細明體", 10, False, RGBColor(120, 120, 120))
                q_count += 1
                
            teacher_path = os.path.join(output_dir, "teacher_guide.docx")
            doc_teacher.save(teacher_path)
            print(f"  [+] 已產生教師版講義 Word: {teacher_path}")
            
        except ImportError:
            print("  [-] 警告: 找不到 python-docx 模組，跳過 Word 檔案生成。")

    def _generate_html(self, data: Dict[str, Any], output_dir: str):
        # 製作帶有 Flashcard, Dialogue translation toggle, Interactive quiz, Timer, Randomizer 的高級 HTML
        
        # 1. 建立單字卡 HTML (支援 CSS 3D 翻轉)
        vocab_cards_html = ""
        for idx, vocab in enumerate(data.get("vocabulary", [])):
            vocab_cards_html += f"""
            <div class="card-container" onclick="flipCard({idx})">
              <div class="card-inner" id="card-{idx}">
                <!-- 正面 -->
                <div class="card-front">
                  <div class="card-header">
                    <span class="badge">詞彙 {idx+1}</span>
                    <button class="speaker-btn" onclick="speakText(event, '{vocab.get('hanji')}')">🔊</button>
                  </div>
                  <div class="hanji-display">{vocab.get('hanji')}</div>
                  <div class="tailo-display">{vocab.get('tailo_diacritic')}</div>
                  <div class="hint-text">點擊翻面看翻譯</div>
                </div>
                <!-- 反面 -->
                <div class="card-back">
                  <div class="back-title">華語翻譯</div>
                  <div class="translation-display">{vocab.get('zh_tw')}</div>
                  <div class="back-hint">點擊翻回正面</div>
                </div>
              </div>
            </div>
            """
            
        # 2. 建立情境對話 HTML
        dialogue_html = ""
        for idx, dia in enumerate(data.get("dialogues", [])):
            dialogue_html += f"""
            <div class="dialogue-row">
              <div class="speaker-avatar">{dia.get('role')[0]}</div>
              <div class="dialogue-bubble" onclick="toggleTranslation({idx})">
                <div class="speaker-name">{dia.get('role')}</div>
                <div class="dialogue-sentence">{dia.get('hanji')}</div>
                <div class="dialogue-tailo">{dia.get('tailo_diacritic')}</div>
                <div class="dialogue-zh" id="diag-zh-{idx}">{dia.get('zh_tw')}</div>
                <div class="dialogue-hint">點擊切換中文翻譯</div>
              </div>
            </div>
            """
            
        # 3. 建立互動測驗 HTML
        quiz_html = ""
        for idx, q in enumerate(data.get("questions", [])):
            options_buttons = ""
            for o_idx, opt in enumerate(q.get("options", [])):
                options_buttons += f"""
                <button class="option-btn" id="q-{idx}-opt-{o_idx}" onclick="checkAnswer({idx}, {o_idx}, {q.get('answer_index')})">
                  {opt}
                </button>
                """
            quiz_html += f"""
            <div class="quiz-card" id="quiz-{idx}">
              <div class="quiz-question">【問題 {idx+1}】{q.get('question')}</div>
              <div class="options-container">
                {options_buttons}
              </div>
              <div class="quiz-feedback" id="feedback-{idx}"></div>
              <div class="quiz-explanation" id="explanation-{idx}">{q.get('explanation')}</div>
            </div>
            """

        html_template = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('title')} - 臺語互動教材</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --primary: #0b3c30;
      --primary-light: #edf6f2;
      --accent: #c69214;
      --bg: #fdfbf7;
      --text: #2f3e46;
      --card-bg: #ffffff;
      --correct: #2e7d32;
      --correct-bg: #e8f5e9;
      --wrong: #c62828;
      --wrong-bg: #ffebee;
      --border: #d9e2dc;
    }}
    
    * {{
      box-sizing: border-box;
      font-family: 'Noto Sans TC', sans-serif;
    }}
    
    body {{
      margin: 0;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 0 0 100px 0;
    }}
    
    .hero-banner {{
      background: linear-gradient(135deg, var(--primary) 0%, #155e4b 100%);
      color: white;
      padding: 50px 20px;
      text-align: center;
      box-shadow: 0 4px 20px rgba(11, 60, 48, 0.15);
    }}
    
    .hero-banner h1 {{
      margin: 0;
      font-size: 2.5rem;
      font-weight: 900;
      letter-spacing: -0.02em;
    }}
    
    .hero-meta {{
      margin-top: 15px;
      font-size: 1.1rem;
      color: #a3c4bc;
    }}
    
    .tag {{
      display: inline-block;
      background-color: rgba(255,255,255,0.15);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.9rem;
      margin: 5px;
    }}
    
    .main-content {{
      max-width: 900px;
      margin: 40px auto;
      padding: 0 20px;
    }}
    
    h2 {{
      color: var(--primary);
      font-size: 1.8rem;
      border-left: 5px solid var(--accent);
      padding-left: 15px;
      margin-top: 40px;
      margin-bottom: 20px;
    }}
    
    /* 課綱對照 CSS */
    .curriculum-box {{
      background-color: white;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 30px;
    }}
    .curriculum-list {{
      list-style-type: none;
      padding: 0;
      margin: 0;
    }}
    .curriculum-list li {{
      padding: 8px 0;
      border-bottom: 1px dashed var(--border);
    }}
    .curriculum-list li:last-child {{ border: none; }}
    
    /* 3D 翻轉單字卡 CSS */
    .vocab-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 20px;
    }}
    
    .card-container {{
      perspective: 1000px;
      height: 250px;
      cursor: pointer;
    }}
    
    .card-inner {{
      position: relative;
      width: 100%;
      height: 100%;
      text-align: center;
      transition: transform 0.6s cubic-bezier(0.4, 0.0, 0.2, 1);
      transform-style: preserve-3d;
    }}
    
    .card-front, .card-back {{
      position: absolute;
      width: 100%;
      height: 100%;
      backface-visibility: hidden;
      border-radius: 16px;
      box-shadow: 0 8px 16px rgba(0,0,0,0.04);
      border: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 20px;
    }}
    
    .card-front {{
      background-color: var(--card-bg);
      border-top: 6px solid var(--primary);
    }}
    
    .card-back {{
      background-color: var(--primary-light);
      border-top: 6px solid var(--accent);
      transform: rotateY(180deg);
      justify-content: center;
    }}
    
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    
    .badge {{
      background-color: var(--primary-light);
      color: var(--primary);
      font-size: 0.8rem;
      font-weight: bold;
      padding: 3px 8px;
      border-radius: 12px;
    }}
    
    .speaker-btn {{
      background: none;
      border: none;
      font-size: 1.2rem;
      cursor: pointer;
      padding: 0;
      transition: transform 0.2s;
    }}
    
    .speaker-btn:hover {{
      transform: scale(1.2);
    }}
    
    .hanji-display {{
      font-size: 2.2rem;
      font-weight: bold;
      color: var(--primary);
      margin: 15px 0;
    }}
    
    .tailo-display {{
      font-size: 1.05rem;
      color: var(--accent);
      font-weight: 600;
    }}
    
    .hint-text, .back-hint {{
      font-size: 0.75rem;
      color: #999;
    }}
    
    .back-title {{
      font-size: 0.85rem;
      color: var(--primary);
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    
    .translation-display {{
      font-size: 1.8rem;
      font-weight: bold;
      color: var(--primary);
      margin: 20px 0;
    }}
    
    /* 對話聊天 CSS */
    .dialogue-container {{
      display: flex;
      flex-direction: column;
      gap: 20px;
      background-color: white;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 25px;
    }}
    
    .dialogue-row {{
      display: flex;
      gap: 15px;
      align-items: flex-start;
    }}
    
    .speaker-avatar {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background-color: var(--accent);
      color: white;
      display: grid;
      place-items: center;
      font-weight: bold;
      font-size: 1.2rem;
      box-shadow: 0 4px 8px rgba(198,146,20,0.2);
    }}
    
    .dialogue-bubble {{
      background-color: var(--primary-light);
      border: 1px solid var(--border);
      border-radius: 4px 16px 16px 16px;
      padding: 15px 20px;
      max-width: 80%;
      cursor: pointer;
      position: relative;
      transition: all 0.3s;
    }}
    
    .dialogue-bubble:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 12px rgba(0,0,0,0.04);
    }}
    
    .speaker-name {{
      font-size: 0.85rem;
      color: var(--accent);
      font-weight: bold;
      margin-bottom: 5px;
    }}
    
    .dialogue-sentence {{
      font-size: 1.2rem;
      font-weight: bold;
      color: var(--primary);
    }}
    
    .dialogue-tailo {{
      font-size: 0.95rem;
      color: var(--text);
      font-style: italic;
      margin-top: 5px;
    }}
    
    .dialogue-zh {{
      font-size: 0.95rem;
      color: var(--correct);
      font-weight: bold;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px dashed var(--border);
      display: none; /* 預設隱藏 */
    }}
    
    .dialogue-hint {{
      font-size: 0.7rem;
      color: #999;
      text-align: right;
      margin-top: 8px;
    }}
    
    /* 互動評量測驗 CSS */
    .quiz-container {{
      display: flex;
      flex-direction: column;
      gap: 25px;
    }}
    
    .quiz-card {{
      background-color: white;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 25px;
      box-shadow: 0 8px 16px rgba(0,0,0,0.03);
    }}
    
    .quiz-question {{
      font-size: 1.2rem;
      font-weight: bold;
      color: var(--primary);
      margin-bottom: 18px;
    }}
    
    .options-container {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    
    .option-btn {{
      background-color: white;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 18px;
      text-align: left;
      font-size: 1rem;
      cursor: pointer;
      transition: all 0.2s;
    }}
    
    .option-btn:hover {{
      background-color: var(--primary-light);
      border-color: var(--primary);
    }}
    
    .option-btn.correct {{
      background-color: var(--correct-bg) !important;
      border-color: var(--correct) !important;
      color: var(--correct) !important;
      font-weight: bold;
    }}
    
    .option-btn.wrong {{
      background-color: var(--wrong-bg) !important;
      border-color: var(--wrong) !important;
      color: var(--wrong) !important;
    }}
    
    .quiz-feedback {{
      margin-top: 15px;
      font-weight: bold;
      font-size: 1.05rem;
      display: none;
    }}
    
    .quiz-explanation {{
      margin-top: 8px;
      padding: 12px;
      background-color: #f7f9f7;
      border-radius: 8px;
      color: #666;
      font-size: 0.9rem;
      display: none;
    }}
    
    /* 課堂浮動小工具控制台 CSS */
    .widget-toggle-btn {{
      position: fixed;
      bottom: 25px;
      right: 25px;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background-color: var(--primary);
      color: white;
      border: none;
      font-size: 1.5rem;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(11,60,48,0.3);
      z-index: 1001;
      transition: transform 0.3s;
    }}
    
    .widget-toggle-btn:hover {{
      transform: scale(1.1);
    }}
    
    .widget-panel {{
      position: fixed;
      bottom: 95px;
      right: 25px;
      width: 320px;
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.3);
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.1);
      padding: 20px;
      z-index: 1000;
      display: none; /* 預設隱藏 */
    }}
    
    .widget-header {{
      font-weight: bold;
      color: var(--primary);
      border-bottom: 1px solid var(--border);
      padding-bottom: 8px;
      margin-bottom: 15px;
      display: flex;
      justify-content: space-between;
    }}
    
    .tool-section {{
      margin-bottom: 20px;
    }}
    .tool-section:last-child {{ margin-bottom: 0; }}
    
    .tool-title {{
      font-size: 0.9rem;
      color: var(--accent);
      font-weight: bold;
      margin-bottom: 8px;
    }}
    
    /* 計時器樣式 */
    .timer-display {{
      font-size: 1.8rem;
      font-weight: 800;
      text-align: center;
      margin: 10px 0;
      color: var(--primary);
    }}
    .timer-controls {{
      display: flex;
      gap: 8px;
    }}
    .timer-btn, .random-btn {{
      flex: 1;
      background-color: var(--primary);
      color: white;
      border: none;
      padding: 8px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: bold;
    }}
    .timer-btn.stop {{ background-color: var(--wrong); }}
    
    /* 抽籤器樣式 */
    .random-display {{
      font-size: 2.2rem;
      font-weight: 900;
      text-align: center;
      color: var(--accent);
      margin: 8px 0;
    }}
  </style>
</head>
<body>

  <!-- Top Hero Banner -->
  <div class="hero-banner">
    <h1>📐 {data.get('title')}</h1>
    <div class="hero-meta">
      <span class="tag">🏫 {data.get('grade')}</span>
      <span class="tag">⏱️ 課程長度：{data.get('duration_minutes')} 分鐘</span>
      <span class="tag">🗣️ 語言系統：教育部臺灣台語羅馬字</span>
    </div>
  </div>

  <div class="main-content">
  
    <!-- 課綱學習目標 -->
    <h2>一、學習指標與課綱對應</h2>
    <div class="curriculum-box">
      <ul class="curriculum-list">
        {"".join([f"<li>🎯 <strong>學習表現</strong>：{x}</li>" for x in data.get('curriculum', {}).get('learning_performance', [])])}
        {"".join([f"<li>📖 <strong>學習內容</strong>：{x}</li>" for x in data.get('curriculum', {}).get('learning_content', [])])}
      </ul>
    </div>

    <!-- 3D 翻轉詞彙卡 -->
    <h2>二、核心詞彙認讀與翻牌練習 (Flashcards)</h2>
    <div class="vocab-grid">
      {vocab_cards_html}
    </div>

    <!-- 情境生活對話 -->
    <h2>三、情境會話 (對話泡泡互動)</h2>
    <div class="dialogue-container">
      {dialogue_html}
    </div>

    <!-- 互動測驗 -->
    <h2>四、隨堂自我檢測 (測驗題)</h2>
    <div class="quiz-container">
      {quiz_html}
    </div>

  </div>

  <!-- 浮動小工具 -->
  <button class="widget-toggle-btn" onclick="toggleWidgetPanel()">🛠️</button>
  
  <div class="widget-panel" id="widget-panel">
    <div class="widget-header">
      <span>課堂輔助小工具</span>
      <span style="cursor:pointer;" onclick="toggleWidgetPanel()">✕</span>
    </div>
    
    <!-- 計時器 -->
    <div class="tool-section">
      <div class="tool-title">⏱️ 課堂計時器</div>
      <div class="timer-display" id="timer-display">05:00</div>
      <div class="timer-controls">
        <input type="number" id="timer-input" placeholder="分" style="width: 50px; text-align: center; border-radius: 4px; border:1px solid #ccc;" value="5">
        <button class="timer-btn" onclick="startTimer()">開始</button>
        <button class="timer-btn stop" onclick="resetTimer()">重置</button>
      </div>
    </div>
    
    <!-- 抽籤器 -->
    <div class="tool-section">
      <div class="tool-title">🎯 電子隨機抽籤 (座號 1-30)</div>
      <div class="random-display" id="random-display">??</div>
      <button class="random-btn" style="width: 100%;" onclick="drawNumber()">隨機抽取學生座號</button>
    </div>
  </div>

  <script>
    // 1. 單字卡翻轉邏輯
    function flipCard(idx) {{
      const card = document.getElementById("card-" + idx);
      if (card.style.transform === "rotateY(180deg)") {{
        card.style.transform = "rotateY(0deg)";
      }} else {{
        card.style.transform = "rotateY(180deg)";
      }}
    }}
    
    // 語音播放占位
    function speakText(event, text) {{
      event.stopPropagation(); // 防止翻轉卡片
      if ('speechSynthesis' in window) {{
        // 嘗試調用本地瀏覽器台語 TTS 朗讀，若無則警告
        const utterance = new SpeechSynthesisUtterance(text);
        // 設定偏好台語/閩南語語音
        utterance.lang = 'zh-HK'; // 部份系統暫用粵語或華語替代，專案後續將整合 RAG TTS 音訊
        window.speechSynthesis.speak(utterance);
      }} else {{
        alert("瀏覽器不支援 Speech Synthesis。");
      }}
    }}

    // 2. 對話中文切換
    function toggleTranslation(idx) {{
      const zhDiv = document.getElementById("diag-zh-" + idx);
      if (zhDiv.style.display === "block") {{
        zhDiv.style.display = "none";
      }} else {{
        zhDiv.style.display = "block";
      }}
    }}

    // 3. 互動測驗確認
    function checkAnswer(qIdx, selectedIdx, correctIdx) {{
      // 找到該題的所有按鈕
      const btns = document.querySelectorAll("#quiz-" + qIdx + " .option-btn");
      btns.forEach((btn, idx) => {{
        btn.disabled = true; // 作答後禁用所有選項
        if (idx === correctIdx) {{
          btn.classList.add('correct'); // 高亮正確答案
        }} else if (idx === selectedIdx) {{
          btn.classList.add('wrong'); // 高亮錯誤答案
        }}
      }});
      
      // 顯示回饋與解析
      const feedback = document.getElementById("feedback-" + qIdx);
      const explanation = document.getElementById("explanation-" + qIdx);
      feedback.style.display = "block";
      explanation.style.display = "block";
      
      if (selectedIdx === correctIdx) {{
        feedback.innerText = "🎯 恭喜答對了！";
        feedback.style.color = "var(--correct)";
      }} else {{
        feedback.innerText = "❌ 答錯囉，再接再厲！";
        feedback.style.color = "var(--wrong)";
      }}
    }}

    // 4. 浮動控制台切換
    function toggleWidgetPanel() {{
      const panel = document.getElementById("widget-panel");
      panel.style.display = panel.style.display === "block" ? "none" : "block";
    }}

    // 5. 計時器核心代碼
    let timerInterval = null;
    let timerSeconds = 300;
    
    function updateTimerDisplay() {{
      const m = Math.floor(timerSeconds / 60).toString().padStart(2, '0');
      const s = (timerSeconds % 60).toString().padStart(2, '0');
      document.getElementById("timer-display").innerText = m + ":" + s;
    }}
    
    function startTimer() {{
      if (timerInterval) return;
      const inputVal = parseInt(document.getElementById("timer-input").value) || 5;
      if (timerSeconds === 300) {{
        timerSeconds = inputVal * 60;
      }}
      timerInterval = setInterval(() => {{
        if (timerSeconds <= 0) {{
          clearInterval(timerInterval);
          timerInterval = null;
          alert("時間到！");
        }} else {{
          timerSeconds--;
          updateTimerDisplay();
        }}
      }}, 1000);
    }}
    
    function resetTimer() {{
      clearInterval(timerInterval);
      timerInterval = null;
      const inputVal = parseInt(document.getElementById("timer-input").value) || 5;
      timerSeconds = inputVal * 60;
      updateTimerDisplay();
    }}

    // 6. 電子隨機抽籤
    function drawNumber() {{
      const display = document.getElementById("random-display");
      let counter = 0;
      // 跑馬燈滾動動畫效果
      const interval = setInterval(() => {{
        display.innerText = Math.floor(Math.random() * 30 + 1);
        counter++;
        if (counter > 15) {{
          clearInterval(interval);
          display.innerText = Math.floor(Math.random() * 30 + 1);
        }}
      }}, 80);
    }}
  </script>
</body>
</html>
"""
        html_path = os.path.join(output_dir, "interactive_website.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"  [+] 已產生離線網頁 HTML: {html_path}")

    def _generate_review_report(self, data: Dict[str, Any], output_dir: str):
        report_lines = [
            f"# 臺語教師教學審核報告：{data.get('title')}",
            f"產出日期: 2026-06-14",
            "",
            "## 1. 課綱與教材檢核狀態",
            "本教材已串接 108 課綱與 seed 詞庫做字元比對，檢核結果如下：",
            ""
        ]
        
        report_lines.append("### 詞彙審查清單 (Vocabulary Review List)")
        for vocab in data.get("vocabulary", []):
            status = "✅ 已驗證" if vocab.get("review_status") == "teacher_verified" else "⚠️ 待教師確認"
            report_lines.append(f"- **{vocab.get('hanji')}** (`{vocab.get('tailo_diacritic')}`): {vocab.get('zh_tw')} -> **{status}**")
            
        report_lines.append("")
        report_lines.append("### 對話拼音聲調審查 (Dialogue Tone Review)")
        for dia in data.get("dialogues", []):
            report_lines.append(f"- **{dia.get('role')}**：{dia.get('hanji')} -> **待試聽音檔並校對**")
            
        report_path = os.path.join(output_dir, "teacher_review_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"  [+] 已產生教師審核報告 Markdown: {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    
    generator = MaterialGenerator(args.config)
    generator.generate_all(args.case)
