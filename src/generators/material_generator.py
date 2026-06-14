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
            # 建立學生版講義
            doc_student = Document()
            doc_student.add_heading(f"臺語學習講義：{data.get('title')}", 0)
            doc_student.add_paragraph(f"適用年級：{data.get('grade')} | 課程時間：{data.get('duration_minutes')} 分鐘")
            
            doc_student.add_heading("一、學習目標與課綱對照", 1)
            for perf in data.get("curriculum", {}).get("learning_performance", []):
                doc_student.add_paragraph(f"• 學習表現：{perf}")
            for cont in data.get("curriculum", {}).get("learning_content", []):
                doc_student.add_paragraph(f"• 學習內容：{cont}")
                
            doc_student.add_heading("二、核心詞彙表", 1)
            table = doc_student.add_table(rows=1, cols=3)
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = '臺語漢字'
            hdr_cells[1].text = '教育部臺羅拼音'
            hdr_cells[2].text = '華語翻譯'
            for vocab in data.get("vocabulary", []):
                row_cells = table.add_row().cells
                row_cells[0].text = vocab.get("hanji", "")
                row_cells[1].text = vocab.get("tailo_diacritic", "")
                row_cells[2].text = vocab.get("zh_tw", "")
                
            doc_student.add_heading("三、情境會話", 1)
            for dia in data.get("dialogues", []):
                doc_student.add_paragraph(f"🗣️ {dia.get('role', '')}：{dia.get('hanji', '')}")
                doc_student.add_paragraph(f"   [{dia.get('tailo_diacritic', '')}]")
                doc_student.add_paragraph(f"   (華語：{dia.get('zh_tw', '')})")
                
            student_path = os.path.join(output_dir, "student_worksheet.docx")
            doc_student.save(student_path)
            print(f"  [+] 已產生學生版講義 Word: {student_path}")
            
            # 建立教師解答版講義
            doc_teacher = Document()
            doc_teacher.add_heading(f"臺語學習講義 (教師解答版)：{data.get('title')}", 0)
            doc_teacher.add_paragraph("【本講義內含教學提示與參考解答】")
            # 複製基本內容
            doc_teacher.add_heading("二、核心詞彙表 (含教學提示)", 1)
            for vocab in data.get("vocabulary", []):
                doc_teacher.add_paragraph(f"• {vocab.get('hanji')} ({vocab.get('tailo_diacritic')}): {vocab.get('zh_tw')} [狀態: {vocab.get('review_status')}]")
                
            teacher_path = os.path.join(output_dir, "teacher_guide.docx")
            doc_teacher.save(teacher_path)
            print(f"  [+] 已產生教師版講義 Word: {teacher_path}")
            
        except ImportError:
            print("  [-] 警告: 找不到 python-docx 模組，跳過 Word 檔案生成。")

    def _generate_html(self, data: Dict[str, Any], output_dir: str):
        # 建立簡約美觀的 HTML 模板
        vocab_rows = ""
        for vocab in data.get("vocabulary", []):
            vocab_rows += f"""
            <div class="vocab-card">
              <span class="hanji">{vocab.get('hanji')}</span>
              <span class="tailo">{vocab.get('tailo_diacritic')}</span>
              <span class="zhtw">{vocab.get('zh_tw')}</span>
            </div>
            """
            
        dialogue_html = ""
        for dia in data.get("dialogues", []):
            dialogue_html += f"""
            <div class="dialogue-bubble">
              <strong class="role">{dia.get('role')}</strong>: 
              <span class="sentence">{dia.get('hanji')}</span>
              <div class="pronunciation">{dia.get('tailo_diacritic')}</div>
              <div class="translation">({dia.get('zh_tw')})</div>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('title')} - 臺語互動教材</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background-color: #f5f8f7;
      color: #2c3e50;
    }}
    .container {{
      max-width: 800px;
      margin: 0 auto;
      background: white;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }}
    h1 {{ color: #176b55; border-bottom: 2px solid #176b55; padding-bottom: 8px; }}
    h2 {{ color: #d99b32; margin-top: 30px; }}
    .vocab-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 15px;
      margin-top: 15px;
    }}
    .vocab-card {{
      background: #edf6f0;
      padding: 15px;
      border-radius: 8px;
      border-left: 4px solid #176b55;
      display: flex;
      flex-direction: column;
    }}
    .hanji {{ font-size: 1.25rem; font-weight: bold; color: #0d4638; }}
    .tailo {{ font-size: 0.95rem; color: #52645f; margin: 4px 0; }}
    .zhtw {{ font-size: 0.9rem; color: #7f8c8d; }}
    .dialogue-bubble {{
      background: #fffdf7;
      border: 1px solid #d9e2dc;
      padding: 15px;
      border-radius: 8px;
      margin-bottom: 12px;
    }}
    .role {{ color: #d99b32; }}
    .pronunciation {{ font-size: 0.9rem; color: #7f8c8d; font-style: italic; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>📐 臺語數位教材：{data.get('title')}</h1>
    <p><strong>年級：</strong>{data.get('grade')} | <strong>長度：</strong>{data.get('duration_minutes')} 分鐘</p>
    
    <h2>📘 核心學習表現/內容</h2>
    <ul>
      {"".join([f"<li>{x}</li>" for x in data.get('curriculum', {}).get('learning_performance', [])])}
      {"".join([f"<li>{x}</li>" for x in data.get('curriculum', {}).get('learning_content', [])])}
    </ul>

    <h2>🍎 核心詞彙庫</h2>
    <div class="vocab-grid">
      {vocab_rows}
    </div>

    <h2>🗣️ 情境生活對話</h2>
    <div class="dialogue-list">
      {dialogue_html}
    </div>
  </div>
</body>
</html>
"""
        html_path = os.path.join(output_dir, "interactive_website.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
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
