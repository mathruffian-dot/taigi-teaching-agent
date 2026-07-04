from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
CONFIG_PATH = PROJECT_ROOT / "config.json"
DEFAULT_GENERATION_OUTPUT = PROJECT_ROOT / "output" / "smoke_full_goal_all_outputs"
OFFICIAL_AUDIT_PATH = PROJECT_ROOT / "data" / "official_materials" / "analysis" / "repository_audit.json"
FORMAL_READINESS_PATH = DOCS_DIR / "formal-output-readiness.json"

REQUIRED_ANALYSIS_ARTIFACTS = [
    PROJECT_ROOT / "data" / "official_materials" / "analysis" / "official_material_snippets.json",
    PROJECT_ROOT / "data" / "official_materials" / "analysis" / "official_material_bank.json",
    PROJECT_ROOT / "data" / "official_materials" / "analysis" / "official_generation_packs.json",
]

REQUIRED_NATURAL_OUTPUTS = ["exam", "slides", "video", "interactive", "quiz"]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def default_formal_output_dir() -> Path:
    if CONFIG_PATH.exists():
        try:
            config = load_json(CONFIG_PATH)
            base_dir = (config.get("output") or {}).get("base_dir")
            if base_dir:
                # base_dir 可含 %USERPROFILE% 等環境變數（config.json 跨電腦同步，路徑勿寫死）
                return Path(os.path.expandvars(os.path.expanduser(base_dir))) / "formal_full_goal_demo"
        except Exception:
            pass
    return PROJECT_ROOT / "output" / "formal_full_goal_demo"


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, message: str, details: dict[str, Any] | None = None) -> None:
    checks.append({
        "name": name,
        "ok": ok,
        "message": message,
        "details": details or {},
    })


def audit_official_repository(checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not OFFICIAL_AUDIT_PATH.exists():
        add_check(checks, "official_repository_audit_exists", False, f"找不到 {OFFICIAL_AUDIT_PATH}")
        return {}

    audit = load_json(OFFICIAL_AUDIT_PATH)
    issue_counts = audit.get("issue_counts", {}) or {}
    add_check(
        checks,
        "official_repository_core_integrity",
        all((issue_counts.get(key, 0) == 0) for key in (
            "missing_required_fields",
            "missing_local_files",
            "zero_byte_local_files",
            "downloadable_without_local",
            "pdf_without_text",
            "duplicate_catalog_keys",
            "source_count_mismatches",
        )),
        "官方教材 catalog、本機檔案、PDF 抽文字與來源數量一致性檢查。",
        issue_counts,
    )
    add_check(
        checks,
        "official_pdf_text_coverage",
        audit.get("local_pdf_count", 0) > 0
        and audit.get("pdf_text_covered_count") == audit.get("local_pdf_count"),
        "本機 PDF 必須全部完成抽文字。",
        {
            "local_pdf_count": audit.get("local_pdf_count", 0),
            "pdf_text_covered_count": audit.get("pdf_text_covered_count", 0),
        },
    )
    missing_artifacts = [str(path.relative_to(PROJECT_ROOT)) for path in REQUIRED_ANALYSIS_ARTIFACTS if not path.exists()]
    add_check(
        checks,
        "official_analysis_artifacts",
        not missing_artifacts,
        "官方教材片段索引、素材庫與生成包必須存在。",
        {"missing": missing_artifacts},
    )
    return audit


def audit_generation_output(checks: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    src_dir = PROJECT_ROOT / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from scripts.validate_generation_output import validate_output_folder

    validation = validate_output_folder(str(output_dir))
    add_check(
        checks,
        "natural_language_output_validation",
        bool(validation.get("ok")),
        "自然語言教材產出資料夾必須通過既有驗證器。",
        {"output_dir": str(output_dir), "issues": validation.get("issues", [])},
    )

    manifest_path = output_dir / "generation_manifest.json"
    if not manifest_path.exists():
        add_check(checks, "natural_language_manifest_exists", False, f"找不到 {manifest_path}")
        return validation

    manifest = load_json(manifest_path)
    outputs = (manifest.get("request") or {}).get("outputs", []) or []
    missing_requested = [item for item in REQUIRED_NATURAL_OUTPUTS if item not in outputs]
    add_check(
        checks,
        "natural_language_requested_all_core_outputs",
        not missing_requested,
        "煙霧產出需求必須同時包含考卷、簡報、影片、互動網站與測驗。",
        {"requested_outputs": outputs, "missing": missing_requested},
    )

    manifest_outputs = manifest.get("outputs", {}) or {}
    required_files = {
        "exam_paper": manifest_outputs.get("exam_paper"),
        "slides": manifest_outputs.get("slides"),
        "video": manifest_outputs.get("video"),
        "interactive_website": manifest_outputs.get("interactive_website"),
        "quiz_bank": manifest_outputs.get("quiz_bank"),
    }
    missing_files = []
    for key, value in required_files.items():
        path = Path(value) if value else None
        if path and not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path or not path.exists() or path.stat().st_size <= 0:
            missing_files.append(key)
    add_check(
        checks,
        "natural_language_core_files_exist",
        not missing_files,
        "五類核心產物檔案必須存在且非空。",
        {"missing_or_empty": missing_files},
    )

    video_generation = manifest.get("video_generation", {}) or {}
    add_check(
        checks,
        "natural_language_video_success",
        bool(video_generation.get("attempted")) and bool(video_generation.get("success")),
        "影片必須實際嘗試並成功產生。",
        video_generation,
    )
    return validation


def audit_formal_output_readiness(checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not FORMAL_READINESS_PATH.exists():
        add_check(checks, "formal_output_readiness_exists", False, f"找不到 {FORMAL_READINESS_PATH}")
        return {}

    readiness = load_json(FORMAL_READINESS_PATH)
    failed_required = [
        check.get("name")
        for check in readiness.get("checks", [])
        if check.get("severity") == "error" and not check.get("ok")
    ]
    add_check(
        checks,
        "formal_output_readiness",
        bool(readiness.get("ok")) and not failed_required,
        "正式輸出模式必須通過必要項目：真實 TTS、標音、生圖端點、影片工具鏈與本機輸出目錄。",
        {
            "live_network": readiness.get("live_network"),
            "attempt_tts_sample": readiness.get("attempt_tts_sample"),
            "failed_required": failed_required,
        },
    )
    add_check(
        checks,
        "formal_output_live_evidence",
        bool(readiness.get("live_network")) and bool(readiness.get("attempt_tts_sample")),
        "正式輸出 readiness 必須包含外部連線與真實 TTS 樣本證據。",
        {
            "live_network": readiness.get("live_network"),
            "attempt_tts_sample": readiness.get("attempt_tts_sample"),
        },
    )
    return readiness


def audit_formal_generation_output(checks: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    if not output_dir.exists():
        add_check(checks, "formal_generation_output_exists", False, f"找不到正式上課包 {output_dir}")
        return {}

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    src_dir = PROJECT_ROOT / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from scripts.validate_generation_output import validate_output_folder

    validation = validate_output_folder(str(output_dir))
    add_check(
        checks,
        "formal_generation_output_validation",
        bool(validation.get("ok")),
        "正式上課包必須通過產出資料夾驗證器。",
        {"output_dir": str(output_dir), "issues": validation.get("issues", [])},
    )

    manifest_path = output_dir / "generation_manifest.json"
    lesson_path = output_dir / "lesson_structure.json"
    if not manifest_path.exists() or not lesson_path.exists():
        add_check(
            checks,
            "formal_generation_manifest_and_lesson",
            False,
            "正式上課包必須包含 generation_manifest.json 與 lesson_structure.json。",
            {"manifest": str(manifest_path), "lesson": str(lesson_path)},
        )
        return validation

    manifest = load_json(manifest_path)
    lesson = load_json(lesson_path)
    add_check(
        checks,
        "formal_generation_not_no_media",
        (manifest.get("generation_options") or {}).get("skip_media") is False,
        "正式上課包不可使用 NoMedia 快速模式。",
        {"skip_media": (manifest.get("generation_options") or {}).get("skip_media")},
    )
    video_generation = manifest.get("video_generation", {}) or {}
    add_check(
        checks,
        "formal_generation_video_success",
        bool(video_generation.get("attempted")) and bool(video_generation.get("success")),
        "正式上課包必須實際產生影片。",
        video_generation,
    )
    vocab = lesson.get("vocabulary", []) or []
    dialogues = lesson.get("dialogues", []) or []
    audio_count = sum(1 for item in [*vocab, *dialogues] if item.get("audio_file"))
    image_count = sum(1 for item in vocab if item.get("image_file"))
    add_check(
        checks,
        "formal_generation_audio_files",
        audio_count > 0,
        "正式上課包必須包含 TTS 音檔。",
        {"audio_file_count": audio_count},
    )
    add_check(
        checks,
        "formal_generation_image_files",
        image_count > 0,
        "正式上課包必須包含詞彙圖片；外部生圖失敗時可用本機 fallback 圖。",
        {"image_file_count": image_count},
    )
    validation["formal_media"] = {
        "audio_file_count": audio_count,
        "image_file_count": image_count,
        "skip_media": (manifest.get("generation_options") or {}).get("skip_media"),
        "video_generation": video_generation,
    }
    return validation


def write_reports(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 專案總目標稽核",
        "",
        f"產生時間：{report['generated_at']}",
        f"結果：{'通過' if report['ok'] else '未通過'}",
        "",
        "## 檢查項目",
        "",
    ]
    for check in report["checks"]:
        mark = "通過" if check["ok"] else "未通過"
        lines.append(f"- [{mark}] {check['name']}：{check['message']}")

    official = report.get("official_repository", {}) or {}
    if official:
        lines.extend([
            "",
            "## 官方教材摘要",
            "",
            f"- Catalog：{official.get('catalog_count', 0)}",
            f"- 本機 PDF：{official.get('local_pdf_count', 0)}",
            f"- PDF 抽文字覆蓋：{official.get('pdf_text_covered_count', 0)} / {official.get('local_pdf_count', 0)}",
            f"- 有附件但尚未下載：{(official.get('issue_counts') or {}).get('downloadable_without_local', 0)}",
            f"- 已確認附件不可取得：{(official.get('issue_counts') or {}).get('confirmed_unavailable', 0)}",
        ])

    generation = report.get("generation_validation", {}) or {}
    manifest = ((generation.get("details") or {}).get("manifest") or {})
    if manifest:
        lines.extend([
            "",
            "## 自然語言產出摘要",
            "",
            f"- 輸出資料夾：`{generation.get('output_dir', '')}`",
            f"- 產出類型：{', '.join(manifest.get('outputs', []))}",
            f"- 驗證結果：{'通過' if generation.get('ok') else '未通過'}",
        ])
        quiz = (generation.get("details") or {}).get("quiz_bank", {})
        if quiz:
            lines.append(f"- 測驗題庫：{quiz.get('question_count', 0)} 題自動計分，{quiz.get('official_extension_count', 0)} 題官方延伸")
        video = (generation.get("details") or {}).get("video_generation", {})
        if video:
            lines.append(f"- 影片生成：{'成功' if video.get('success') else '未成功'}")

    readiness = report.get("formal_output_readiness", {}) or {}
    if readiness:
        lines.extend([
            "",
            "## 正式輸出 Readiness 摘要",
            "",
            f"- 必要項目：{'通過' if readiness.get('ok') else '未通過'}",
            f"- 外部連線樣本：{'已執行' if readiness.get('live_network') else '未執行'}",
            f"- 真實 TTS 樣本：{'已執行' if readiness.get('attempt_tts_sample') else '未執行'}",
        ])

    formal_output = report.get("formal_generation_validation", {}) or {}
    if formal_output:
        media = formal_output.get("formal_media", {}) or {}
        lines.extend([
            "",
            "## 正式上課包摘要",
            "",
            f"- 輸出資料夾：`{formal_output.get('output_dir', '')}`",
            f"- 驗證結果：{'通過' if formal_output.get('ok') else '未通過'}",
            f"- 快速模式：{media.get('skip_media')}",
            f"- TTS 音檔數：{media.get('audio_file_count', 0)}",
            f"- 圖片數：{media.get('image_file_count', 0)}",
            f"- 影片生成：{'成功' if (media.get('video_generation') or {}).get('success') else '未成功'}",
        ])

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_project_goal(output_dir: Path = DEFAULT_GENERATION_OUTPUT, formal_output_dir: Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    official_audit = audit_official_repository(checks)
    generation_validation = audit_generation_output(checks, output_dir)
    readiness = audit_formal_output_readiness(checks)
    formal_generation_validation = audit_formal_generation_output(checks, formal_output_dir or default_formal_output_dir())
    ok = all(check["ok"] for check in checks)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "checks": checks,
        "official_repository": official_audit,
        "generation_validation": generation_validation,
        "formal_output_readiness": readiness,
        "formal_generation_validation": formal_generation_validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="稽核 2026本土語專案總目標完成度。")
    parser.add_argument("--generation-output", default=str(DEFAULT_GENERATION_OUTPUT), help="五類自然語言煙霧產出資料夾")
    parser.add_argument("--formal-output", default=str(default_formal_output_dir()), help="正式上課包產出資料夾")
    parser.add_argument("--json", default=str(DOCS_DIR / "project-goal-audit.json"))
    parser.add_argument("--markdown", default=str(DOCS_DIR / "project-goal-audit.md"))
    args = parser.parse_args()

    report = audit_project_goal(Path(args.generation_output), Path(args.formal_output))
    write_reports(report, Path(args.json), Path(args.markdown))
    print(json.dumps({"ok": report["ok"], "checks": report["checks"]}, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
