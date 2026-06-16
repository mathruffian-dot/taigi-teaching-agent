# 臺語教材生成器主程式 (material_generator.py)
import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any

# 加入專案 src 目錄到路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import safe_print
print = safe_print

from rag.retriever import TaigiRetriever
from tailo.validator import convert_sentence_numeric_to_diacritic
from tts.generator import TaigiTTS
from generators.image_generator import FreeImageGenerator

class MaterialGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.retriever = TaigiRetriever()
        self.tts = TaigiTTS(config_path)

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

        # 3.5. 產生語音音訊檔 (詞彙下載與對話合成)
        print("[*] 執行語音生成與下載...")
        audio_dir = os.path.join(output_dir, "audio")
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
            
        for vocab in enriched_data.get("vocabulary", []):
            hanji = vocab.get("hanji", "")
            if hanji:
                # 預設儲存為 ogg，若失敗則合成 wav 佔位符
                ogg_filename = f"vocab_{hanji}.ogg"
                ogg_path = os.path.join(audio_dir, ogg_filename)
                
                # 嘗試從萌典下載
                success = self.tts.fetch_vocab_audio(hanji, ogg_path)
                if success:
                    vocab["audio_file"] = f"audio/{ogg_filename}"
                else:
                    # 降級：使用 dummy/yating 合成 wav 檔
                    wav_filename = f"vocab_{hanji}.wav"
                    wav_path = os.path.join(audio_dir, wav_filename)
                    self.tts.synthesize_sentence(hanji, wav_path, vocab.get("tailo_numeric", ""))
                    vocab["audio_file"] = f"audio/{wav_filename}"
                    
        for idx, dia in enumerate(enriched_data.get("dialogues", [])):
            hanji = dia.get("hanji", "")
            if hanji:
                # 對話句子進行語音合成
                wav_filename = f"dialogue_{idx}.wav"
                wav_path = os.path.join(audio_dir, wav_filename)
                self.tts.synthesize_sentence(hanji, wav_path, dia.get("tailo_numeric", ""))
                dia["audio_file"] = f"audio/{wav_filename}"

        # 3.6. 產生詞彙插圖 (免費生圖 API Option B)
        print("[*] 執行免費 AI 詞彙生圖...")
        image_dir = os.path.join(output_dir, "images")
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
            
        img_gen = FreeImageGenerator(self.config_path)
        
        for vocab in enriched_data.get("vocabulary", []):
            hanji = vocab.get("hanji", "")
            zh_tw = vocab.get("zh_tw", "")
            if not zh_tw or zh_tw == "pending":
                zh_tw = hanji
                
            if zh_tw:
                img_filename = f"vocab_{hanji}.jpg"
                img_path = os.path.join(image_dir, img_filename)
                success = img_gen.generate_image(zh_tw, img_path)
                if success:
                    vocab["image_file"] = f"images/{img_filename}"
                else:
                    vocab["image_file"] = ""

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
        except ImportError:
            print("  [-] 警告: 找不到 python-docx 模組，跳過 Word 檔案生成。")
            return
            
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
        
        table = doc_student.add_table(rows=1, cols=5)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = '圖示'
        hdr_cells[1].text = '臺語漢字'
        hdr_cells[2].text = '教育部臺羅拼音'
        hdr_cells[3].text = '華語翻譯'
        hdr_cells[4].text = '手寫練習 (漢字與拼音)'
        
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
            
            # 1. 置入圖片
            from docx.shared import Inches
            img_rel_path = vocab.get("image_file")
            if img_rel_path:
                full_img_path = os.path.join(output_dir, img_rel_path)
                if os.path.exists(full_img_path):
                    p_img = row_cells[0].paragraphs[0]
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run_img = p_img.add_run()
                    try:
                        run_img.add_picture(full_img_path, width=Inches(0.9))
                    except Exception as e:
                        p_img.text = "[圖片損毀]"
                else:
                    row_cells[0].text = "無圖片"
            else:
                row_cells[0].text = "無圖片"
                
            row_cells[1].text = vocab.get("hanji", "")
            row_cells[2].text = vocab.get("tailo_diacritic", "")
            row_cells[3].text = vocab.get("zh_tw", "")
            row_cells[4].text = "__________________"
            
            # 斑馬紋底色
            row_color = "F6F8F6" if row_count % 2 == 1 else "FFFFFF"
            for i, cell in enumerate(row_cells):
                set_cell_shading(cell, row_color)
                p = cell.paragraphs[0]
                # 前四欄置中，手寫欄靠左
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i < 4 else WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    style_run(r, "新細明體" if i != 2 else "Arial", 10, False, RGBColor(47, 62, 70))
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
        
    def _generate_html(self, data: Dict[str, Any], output_dir: str):
        # 使用 Jinja2 樣板渲染離線互動網頁（樣板：templates/interactive_website.html.j2）
        from jinja2 import Environment, FileSystemLoader

        def js_str(s: Any) -> str:
            # 轉義字串以安全嵌入單引號 JS 字串字面值（避免漢字／翻譯內含單引號或反斜線破壞 onclick）
            return (str(s or "")
                    .replace(chr(92), chr(92)*2)
                    .replace("'", chr(92)+"'")
                    .replace(chr(10), " ")
                    .replace(chr(13), " "))

        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False,          # 內容含 JS 樣板字串與 HTML 片段，沿用原本不做 HTML escape 的行為
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters["js"] = js_str

        template = env.get_template("interactive_website.html.j2")
        curriculum = data.get("curriculum", {}) or {}
        html_output = template.render(
            title=data.get("title", ""),
            grade=data.get("grade", ""),
            duration_minutes=data.get("duration_minutes", ""),
            curriculum={
                "learning_performance": curriculum.get("learning_performance", []),
                "learning_content": curriculum.get("learning_content", []),
            },
            vocabulary=data.get("vocabulary", []),
            dialogues=data.get("dialogues", []),
            questions=data.get("questions", []),
        )

        html_path = os.path.join(output_dir, "interactive_website.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_output)
        print(f"  [+] 已產生離線網頁 HTML: {html_path}")

    def _generate_review_report(self, data: Dict[str, Any], output_dir: str):
        report_lines = [
            f"# 臺語教師教學審核報告：{data.get('title')}",
            f"產出日期: {datetime.now().strftime('%Y-%m-%d')}",
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
