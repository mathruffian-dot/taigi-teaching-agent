from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "official_materials"
CATALOG_PATH = DATA_DIR / "catalog.json"
SOURCES_PATH = DATA_DIR / "sources.json"
ANALYSIS_DIR = DATA_DIR / "analysis"
PDF_TEXT_INDEX_PATH = ANALYSIS_DIR / "pdf_text_index.json"
ERRORS_PATH = ANALYSIS_DIR / "mhi_collect_errors.jsonl"
JSON_OUTPUT = ANALYSIS_DIR / "repository_audit.json"
MD_OUTPUT = ANALYSIS_DIR / "repository_audit.md"

REQUIRED_FIELDS = (
    "source_id",
    "resource_id",
    "title",
    "page_url",
    "language",
    "learning_stage",
    "material_type",
    "license_note",
)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def rel_path_exists(root: Path, value: str | None) -> bool:
    if not value:
        return False
    return (root / value).exists()


def rel_path_size(root: Path, value: str | None) -> int:
    if not value:
        return 0
    path = root / value
    return path.stat().st_size if path.exists() else 0


def is_page_index(item: dict[str, Any]) -> bool:
    attachment_url = item.get("attachment_url")
    if not attachment_url:
        return True
    return attachment_url == item.get("page_url")


def is_intentionally_not_downloaded(item: dict[str, Any]) -> bool:
    material_type = str(item.get("material_type") or "")
    license_note = str(item.get("license_note") or "")
    return "大型壓縮檔" in material_type or "大型" in license_note


def is_confirmed_unavailable(item: dict[str, Any]) -> bool:
    return str(item.get("download_status") or "") == "confirmed_unavailable"


def build_pdf_text_keys(pdf_text_index: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for item in pdf_text_index:
        keys.add((
            str(item.get("resource_id") or ""),
            str(item.get("attachment_url") or ""),
            str(item.get("local_path") or ""),
        ))
    return keys


def audit_repository(
    catalog: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    pdf_text_index: list[dict[str, Any]],
    download_errors: list[dict[str, Any]],
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    by_source = Counter(str(item.get("source_id") or "unknown") for item in catalog)
    by_material_type = Counter(str(item.get("material_type") or "未標示") for item in catalog)
    by_resource_kind = Counter(str(item.get("resource_kind") or "未分類") for item in catalog)
    pdf_text_keys = build_pdf_text_keys(pdf_text_index)

    missing_required_fields: list[dict[str, Any]] = []
    missing_local_files: list[dict[str, Any]] = []
    zero_byte_local_files: list[dict[str, Any]] = []
    downloadable_without_local: list[dict[str, Any]] = []
    confirmed_unavailable: list[dict[str, Any]] = []
    pdf_without_text: list[dict[str, Any]] = []
    duplicate_keys: list[dict[str, Any]] = []

    seen_keys: Counter = Counter()
    local_file_count = 0
    local_pdf_count = 0
    local_total_bytes = 0
    page_index_only_count = 0
    intentionally_not_downloaded_count = 0
    confirmed_unavailable_count = 0
    downloadable_attachment_count = 0
    pdf_text_covered_count = 0

    for item in catalog:
        item_key = (
            str(item.get("source_id") or ""),
            str(item.get("resource_id") or ""),
            str(item.get("attachment_url") or item.get("page_url") or ""),
        )
        seen_keys[item_key] += 1

        missing_fields = [field for field in REQUIRED_FIELDS if not item.get(field)]
        if missing_fields:
            missing_required_fields.append({
                "resource_id": item.get("resource_id"),
                "title": item.get("title"),
                "missing_fields": missing_fields,
            })

        local_path = item.get("local_path")
        attachment_url = item.get("attachment_url")
        has_downloadable_attachment = bool(attachment_url and attachment_url != item.get("page_url"))
        if has_downloadable_attachment:
            downloadable_attachment_count += 1

        if local_path:
            local_file_count += 1
            size = rel_path_size(project_root, local_path)
            local_total_bytes += size
            if not rel_path_exists(project_root, local_path):
                missing_local_files.append({
                    "resource_id": item.get("resource_id"),
                    "title": item.get("title"),
                    "local_path": local_path,
                })
            elif size == 0:
                zero_byte_local_files.append({
                    "resource_id": item.get("resource_id"),
                    "title": item.get("title"),
                    "local_path": local_path,
                })

            if str(local_path).lower().endswith(".pdf"):
                local_pdf_count += 1
                pdf_key = (
                    str(item.get("resource_id") or ""),
                    str(item.get("attachment_url") or ""),
                    str(item.get("local_path") or ""),
                )
                if pdf_key in pdf_text_keys:
                    pdf_text_covered_count += 1
                else:
                    pdf_without_text.append({
                        "resource_id": item.get("resource_id"),
                        "title": item.get("title"),
                        "local_path": local_path,
                    })
        else:
            if is_page_index(item):
                page_index_only_count += 1
            elif is_intentionally_not_downloaded(item):
                intentionally_not_downloaded_count += 1
            elif is_confirmed_unavailable(item):
                confirmed_unavailable_count += 1
                confirmed_unavailable.append({
                    "resource_id": item.get("resource_id"),
                    "title": item.get("title"),
                    "attachment_label": item.get("attachment_label"),
                    "attachment_url": attachment_url,
                    "download_error_note": item.get("download_error_note"),
                    "last_download_attempted_at": item.get("last_download_attempted_at"),
                })
            elif has_downloadable_attachment:
                downloadable_without_local.append({
                    "resource_id": item.get("resource_id"),
                    "title": item.get("title"),
                    "attachment_label": item.get("attachment_label"),
                    "attachment_url": attachment_url,
                    "license_note": item.get("license_note"),
                })

    for key, count in seen_keys.items():
        if count > 1:
            duplicate_keys.append({
                "source_id": key[0],
                "resource_id": key[1],
                "attachment_or_page_url": key[2],
                "count": count,
            })

    source_checks: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source.get("source_id") or "")
        expected_catalog_count = source.get("catalog_record_count")
        expected_downloaded_pdf_count = source.get("downloaded_pdf_count")
        actual_catalog_count = by_source[source_id]
        actual_downloaded_pdf_count = sum(
            1
            for item in catalog
            if item.get("source_id") == source_id
            and str(item.get("local_path") or "").lower().endswith(".pdf")
            and rel_path_exists(project_root, item.get("local_path"))
        )
        source_checks.append({
            "source_id": source_id,
            "name": source.get("name"),
            "status": source.get("status"),
            "catalog_record_count": actual_catalog_count,
            "expected_catalog_record_count": expected_catalog_count,
            "catalog_record_count_matches_source": (
                expected_catalog_count is None or expected_catalog_count == actual_catalog_count
            ),
            "downloaded_pdf_count": actual_downloaded_pdf_count,
            "expected_downloaded_pdf_count": expected_downloaded_pdf_count,
            "downloaded_pdf_count_matches_source": (
                expected_downloaded_pdf_count is None
                or expected_downloaded_pdf_count == actual_downloaded_pdf_count
            ),
            "last_checked": source.get("last_checked"),
        })

    issues = {
        "missing_required_fields": missing_required_fields,
        "missing_local_files": missing_local_files,
        "zero_byte_local_files": zero_byte_local_files,
        "downloadable_without_local": downloadable_without_local,
        "confirmed_unavailable": confirmed_unavailable,
        "pdf_without_text": pdf_without_text,
        "duplicate_catalog_keys": duplicate_keys,
        "download_errors": download_errors,
        "source_count_mismatches": [
            row for row in source_checks
            if not row["catalog_record_count_matches_source"]
            or not row["downloaded_pdf_count_matches_source"]
        ],
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "catalog_count": len(catalog),
        "source_count": len(sources),
        "local_file_count": local_file_count,
        "local_pdf_count": local_pdf_count,
        "local_total_bytes": local_total_bytes,
        "downloadable_attachment_count": downloadable_attachment_count,
        "page_index_only_count": page_index_only_count,
        "intentionally_not_downloaded_count": intentionally_not_downloaded_count,
        "confirmed_unavailable_count": confirmed_unavailable_count,
        "pdf_text_index_count": len(pdf_text_index),
        "pdf_text_covered_count": pdf_text_covered_count,
        "pdf_text_missing_count": len(pdf_without_text),
        "by_source": [{"name": name, "count": count} for name, count in by_source.most_common()],
        "by_material_type": [{"name": name, "count": count} for name, count in by_material_type.most_common()],
        "by_resource_kind": [{"name": name, "count": count} for name, count in by_resource_kind.most_common()],
        "source_checks": source_checks,
        "issue_counts": {key: len(value) for key, value in issues.items()},
        "issues": issues,
    }


def write_markdown(report: dict[str, Any]) -> None:
    mb = report["local_total_bytes"] / 1024 / 1024
    lines = [
        "# 官方教材資料倉庫稽核",
        "",
        f"產生時間：{report['generated_at']}",
        "",
        "## 整體狀態",
        "",
        f"- Catalog 筆數：{report['catalog_count']}",
        f"- 官方來源數：{report['source_count']}",
        f"- 本機檔案數：{report['local_file_count']}",
        f"- 本機 PDF 數：{report['local_pdf_count']}",
        f"- 本機檔案總量：約 {mb:.1f} MB",
        f"- 有附件網址的資源：{report['downloadable_attachment_count']}",
        f"- 僅頁面索引資源：{report['page_index_only_count']}",
        f"- 已登錄但刻意不下載的大型檔：{report['intentionally_not_downloaded_count']}",
        f"- 已確認附件不可取得：{report['confirmed_unavailable_count']}",
        f"- PDF 抽文字覆蓋：{report['pdf_text_covered_count']} / {report['local_pdf_count']}",
        "",
        "## 來源檢查",
        "",
    ]
    for row in report["source_checks"]:
        catalog_status = "一致" if row["catalog_record_count_matches_source"] else "不一致"
        pdf_status = "一致" if row["downloaded_pdf_count_matches_source"] else "不一致"
        lines.append(
            f"- {row['source_id']}：catalog {row['catalog_record_count']}（{catalog_status}），"
            f"PDF {row['downloaded_pdf_count']}（{pdf_status}），last_checked={row.get('last_checked')}"
        )

    lines.extend(["", "## 問題摘要", ""])
    labels = {
        "missing_required_fields": "缺必要欄位",
        "missing_local_files": "catalog 指到不存在的本機檔案",
        "zero_byte_local_files": "零位元組本機檔案",
        "downloadable_without_local": "有附件但尚未下載",
        "confirmed_unavailable": "已確認附件不可取得",
        "pdf_without_text": "本機 PDF 尚未抽文字",
        "duplicate_catalog_keys": "重複 catalog key",
        "download_errors": "下載錯誤紀錄",
        "source_count_mismatches": "sources.json 數量不一致",
    }
    for key, count in report["issue_counts"].items():
        lines.append(f"- {labels.get(key, key)}：{count}")

    for section_key in ("downloadable_without_local", "confirmed_unavailable", "download_errors", "pdf_without_text"):
        rows = report["issues"].get(section_key, [])
        if not rows:
            continue
        lines.extend(["", f"## {labels.get(section_key, section_key)}", ""])
        for row in rows[:10]:
            title = row.get("title") or row.get("resource_id") or row.get("url")
            detail = row.get("attachment_url") or row.get("url") or row.get("local_path") or row.get("message") or ""
            lines.append(f"- {title}：{detail}")
        if len(rows) > 10:
            lines.append(f"- 另有 {len(rows) - 10} 筆，詳見 repository_audit.json")

    lines.extend([
        "",
        "## 判讀",
        "",
        "- `missing_local_files`、`zero_byte_local_files`、`pdf_without_text` 應優先維持為 0。",
        "- `downloadable_without_local` 若是大型壓縮檔或外部影音，應在 catalog 中清楚標註不直接下載原因。",
        "- `confirmed_unavailable` 代表已重試並確認附件端不可取得，保留來源頁與錯誤原因供後續追查。",
        "- `download_errors` 可作為下一輪補抓附件的工作清單。",
    ])
    MD_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_json(CATALOG_PATH, [])
    sources = load_json(SOURCES_PATH, [])
    pdf_text_index = load_json(PDF_TEXT_INDEX_PATH, [])
    download_errors = load_jsonl(ERRORS_PATH)
    report = audit_repository(catalog, sources, pdf_text_index, download_errors)
    JSON_OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report)
    print(f"完成：{JSON_OUTPUT}")
    print(f"完成：{MD_OUTPUT}")


if __name__ == "__main__":
    main()
