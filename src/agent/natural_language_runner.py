# 臺語教材自然語言入口 (natural_language_runner.py)
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)
for path in (src_dir, project_root):
    if path not in sys.path:
        sys.path.append(path)

from agent.outline_generator import TaigiOutlineGenerator
from generators.material_generator import MaterialGenerator
from generators.video_generator import TaigiVideoGenerator
from scripts.validate_generation_output import validate_output_folder, write_reports
from utils import safe_print, resolve_output_base_dir

print = safe_print


OUTPUT_KEYWORDS = {
    "exam": ["考卷", "試卷", "紙本測驗", "評量"],
    "worksheet": ["講義", "學習單", "學習單"],
    "slides": ["簡報", "投影片", "ppt", "pptx", "powerpoint"],
    "video": ["影片", "教學影片", "mp4"],
    "interactive": ["互動網站", "互動網頁", "網站", "程式", "html"],
    "quiz": ["測驗", "小考", "練習題", "題目"],
}

GRADE_PATTERNS = [
    "國小一年級", "國小二年級", "國小三年級", "國小四年級", "國小五年級", "國小六年級",
    "國中七年級", "國中八年級", "國中九年級",
    "高一", "高二", "高三",
    "第一學習階段", "第二學習階段", "第三學習階段", "第四學習階段", "第五學習階段",
]


def parse_natural_language_request(text: str, default_grade: str = "國中七年級") -> Dict[str, Any]:
    request = (text or "").strip()
    grade = default_grade
    for pattern in GRADE_PATTERNS:
        if pattern.lower() in request.lower():
            grade = pattern
            break

    outputs = []
    lowered = request.lower()
    for output_type, keywords in OUTPUT_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            outputs.append(output_type)
    if not outputs:
        outputs = ["worksheet", "slides", "interactive", "quiz"]

    duration_match = re.search(r"(\d+)\s*分鐘", request)
    duration_minutes = int(duration_match.group(1)) if duration_match else 45

    topic = request
    cleanup_terms: List[str] = [
        "請", "幫我", "幫", "做", "製作", "產生", "生成", "設計", "一份", "一個",
        "臺語", "台語", "本土語", "教材", "的", "和", "與", "及", "、", "，", ",",
    ]
    for pattern in GRADE_PATTERNS:
        topic = topic.replace(pattern, " ")
    for keywords in OUTPUT_KEYWORDS.values():
        for keyword in keywords:
            topic = re.sub(keyword, " ", topic, flags=re.IGNORECASE)
    topic = re.sub(r"\d+\s*分鐘", " ", topic)
    for term in cleanup_terms:
        topic = topic.replace(term, " ")
    topic = re.sub(r"\s+", " ", topic).strip()
    if not topic:
        topic = request or "臺語生活情境"

    return {
        "request": request,
        "topic": topic,
        "grade": grade,
        "duration_minutes": duration_minutes,
        "outputs": outputs,
    }


def _safe_folder_name(text: str) -> str:
    name = "".join(ch for ch in text if ch.isalnum() or ch in "-_")
    return name[:32] or "taigi_material"


def run_natural_language_request(
    request: str,
    config_path: str = "config.json",
    output_dir: str = None,
    include_video: bool = None,
    skip_media: bool = False,
    validate_output: bool = True,
) -> Dict[str, Any]:
    parsed = parse_natural_language_request(request)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_dir is None:
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
        base_dir = resolve_output_base_dir(config)
        output_dir = os.path.join(base_dir, "natural_language", f"{timestamp}_{_safe_folder_name(parsed['topic'])}")
    os.makedirs(output_dir, exist_ok=True)

    print(f"[*] 自然語言需求: {parsed['request']}")
    print(f"[*] 解析主題: {parsed['topic']}")
    print(f"[*] 適用年級: {parsed['grade']}")
    print(f"[*] 產出類型: {', '.join(parsed['outputs'])}")
    if skip_media:
        print("[*] 快速模式：本次跳過音訊與圖片生成。")
    print(f"[*] 輸出資料夾: {output_dir}")

    outline_generator = TaigiOutlineGenerator(config_path)
    outline = outline_generator.generate_outline(
        parsed["topic"],
        parsed["grade"],
        duration_minutes=parsed["duration_minutes"],
    )
    outline["natural_language_request"] = parsed
    outline["generation_options"] = {"skip_media": skip_media}
    outline["official_material_recommendations"] = outline_generator.retriever.recommend_official_materials(
        parsed["topic"],
        outputs=parsed["outputs"],
        limit_per_output=3,
    )
    if hasattr(outline_generator.retriever, "recommend_official_generation_assets"):
        outline["official_generation_assets"] = outline_generator.retriever.recommend_official_generation_assets(
            parsed["topic"],
            outputs=parsed["outputs"],
            limit_per_output=3,
        )

    outline_path = os.path.join(output_dir, "outline.json")
    with open(outline_path, "w", encoding="utf-8") as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    print(f"  [+] 已產生自然語言大綱 JSON: {outline_path}")

    material_generator = MaterialGenerator(config_path)
    material_output_dir = material_generator.generate_all(outline_path, output_dir=output_dir, skip_media=skip_media)

    should_make_video = include_video if include_video is not None else ("video" in parsed["outputs"])
    video_status = {
        "requested_in_text": "video" in parsed["outputs"],
        "forced": include_video is True,
        "attempted": bool(should_make_video),
        "success": False,
        "path": None,
        "skipped_reason": None,
    }
    video_path = None
    if should_make_video:
        print("\n[*] 自然語言需求包含影片，開始產生教學影片...")
        lesson_structure_path = os.path.join(material_output_dir, "lesson_structure.json")
        expected_video_path = os.path.join(material_output_dir, "lesson_video.mp4")
        video_generator = TaigiVideoGenerator(config_path)
        if video_generator.generate_video(lesson_structure_path, expected_video_path) and os.path.exists(expected_video_path):
            video_path = expected_video_path
            video_status["success"] = True
            video_status["path"] = video_path
            print(f"  [+] 已產生教學影片: {video_path}")
        else:
            video_status["skipped_reason"] = "generation_failed"
            print("  [-] 教學影片產生失敗，請查看前面訊息。")
    elif "video" in parsed["outputs"]:
        video_status["skipped_reason"] = "disabled_by_option"

    manifest = {
        "request": parsed,
        "generation_options": {"skip_media": skip_media, "include_video": bool(should_make_video)},
        "outline_path": outline_path,
        "output_dir": material_output_dir,
        "official_material_recommendations": outline.get("official_material_recommendations", {}),
        "official_generation_assets": outline.get("official_generation_assets", {}),
        "video_generation": video_status,
        "outputs": {
            "lesson_structure": os.path.join(material_output_dir, "lesson_structure.json"),
            "student_worksheet": os.path.join(material_output_dir, "student_worksheet.docx"),
            "teacher_guide": os.path.join(material_output_dir, "teacher_guide.docx"),
            "exam_paper": os.path.join(material_output_dir, "exam_paper.docx"),
            "exam_answer_key": os.path.join(material_output_dir, "exam_answer_key.docx"),
            "quiz_bank": os.path.join(material_output_dir, "quiz_bank.json"),
            "quiz_teacher_key": os.path.join(material_output_dir, "quiz_teacher_key.md"),
            "slides": os.path.join(material_output_dir, "teaching_slides.pptx"),
            "interactive_website": os.path.join(material_output_dir, "interactive_website.html"),
            "teacher_review_report": os.path.join(material_output_dir, "teacher_review_report.md"),
            "video": video_path,
        },
    }
    manifest_path = os.path.join(material_output_dir, "generation_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  [+] 已產生輸出清單: {manifest_path}")

    if validate_output:
        validation = validate_output_folder(material_output_dir)
        write_reports(validation, Path(material_output_dir))
        manifest["validation"] = validation
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(f"  [+] 已產生驗證報告: {os.path.join(material_output_dir, 'generation_validation.md')}")

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("request", help="自然語言教材需求，例如：幫我做國中七年級有機菜蔬的簡報和互動測驗")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default=None, help="輸出資料夾；未指定時使用 config.output.base_dir")
    parser.add_argument("--video", action="store_true", help="強制產生教學影片")
    parser.add_argument("--no-video", action="store_true", help="即使需求提到影片也先不產生影片")
    parser.add_argument("--no-media", action="store_true", help="跳過音訊與圖片生成，快速輸出文字類教材")
    parser.add_argument("--no-validate", action="store_true", help="產出後不執行資料夾驗證")
    args = parser.parse_args()

    include_video = None
    if args.video:
        include_video = True
    if args.no_video:
        include_video = False

    run_natural_language_request(
        args.request,
        config_path=args.config,
        output_dir=args.output,
        include_video=include_video,
        skip_media=args.no_media,
        validate_output=not args.no_validate,
    )
