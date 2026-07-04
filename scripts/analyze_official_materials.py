from __future__ import annotations

import json
import re
from hashlib import sha1
from collections import Counter, defaultdict
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "official_materials"
CATALOG_PATH = DATA_ROOT / "catalog.json"
TEXT_ROOT = DATA_ROOT / "processed" / "pdf_text"
ANALYSIS_ROOT = DATA_ROOT / "analysis"

KEYWORDS = [
    "學習目標",
    "學習表現",
    "學習內容",
    "核心素養",
    "教學活動",
    "評量",
    "學習單",
    "教案",
    "語詞",
    "句型",
    "臺羅",
    "羅馬拼音",
    "漢字",
    "文化",
]


def safe_name(value: str, limit: int = 80) -> str:
    value = re.sub(r'[\\/:*?"<>|]', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit].strip()


def load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))


def extract_pdf_text(path: Path) -> tuple[str, int]:
    with fitz.open(path) as doc:
        text = "\n\n".join(page.get_text("text") for page in doc)
        return text, doc.page_count


def analyze_text(text: str) -> dict:
    keyword_counts = {keyword: text.count(keyword) for keyword in KEYWORDS}
    romanized_tokens = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*(?:[0-9])?", text)
    han_chars = re.findall(r"[\u4e00-\u9fff]", text)
    return {
        "char_count": len(text),
        "han_char_count": len(han_chars),
        "romanized_token_count": len(romanized_tokens),
        "keyword_counts": keyword_counts,
    }


def main() -> None:
    TEXT_ROOT.mkdir(parents=True, exist_ok=True)
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    for old_text in TEXT_ROOT.rglob("*.txt"):
        old_text.unlink()

    catalog = load_catalog()
    analyzed: list[dict] = []
    skipped: list[dict] = []

    for item in catalog:
        local_path = item.get("local_path")
        if not local_path or not str(local_path).lower().endswith(".pdf"):
            skipped.append(
                {
                    "resource_id": item.get("resource_id"),
                    "title": item.get("title"),
                    "reason": "no_local_pdf",
                }
            )
            continue

        pdf_path = ROOT / local_path
        if not pdf_path.exists():
            skipped.append(
                {
                    "resource_id": item.get("resource_id"),
                    "title": item.get("title"),
                    "reason": "missing_file",
                    "local_path": local_path,
                }
            )
            continue

        text, page_count = extract_pdf_text(pdf_path)
        stats = analyze_text(text)
        text_dir = TEXT_ROOT / item.get("source_id", "unknown")
        text_dir.mkdir(parents=True, exist_ok=True)
        attachment_key = sha1((item.get("attachment_url") or "").encode("utf-8")).hexdigest()[:8]
        text_name = (
            f"{item.get('resource_id', 'unknown')}__"
            f"{safe_name(item.get('attachment_label', 'attachment'), 30)}__"
            f"{safe_name(item.get('title', 'untitled'))}__"
            f"{attachment_key}.txt"
        )
        text_path = text_dir / text_name
        text_path.write_text(text, encoding="utf-8")

        analyzed.append(
            {
                **item,
                "page_count": page_count,
                "text_path": str(text_path.relative_to(ROOT)),
                **stats,
            }
        )

    (ANALYSIS_ROOT / "pdf_text_index.json").write_text(
        json.dumps(analyzed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ANALYSIS_ROOT / "skipped_items.json").write_text(
        json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    by_source = Counter(item["source_id"] for item in analyzed)
    by_stage = Counter(item.get("learning_stage") or "未標示" for item in analyzed)
    by_type = Counter(item.get("material_type") or "未標示" for item in analyzed)
    total_pages = sum(item["page_count"] for item in analyzed)
    total_chars = sum(item["char_count"] for item in analyzed)

    keyword_totals: Counter[str] = Counter()
    for item in analyzed:
        keyword_totals.update(item["keyword_counts"])

    lines = [
        "# 官方臺語教材初步分析",
        "",
        f"- 已分析 PDF：{len(analyzed)}",
        f"- 跳過項目：{len(skipped)}",
        f"- 總頁數：{total_pages}",
        f"- 抽取文字總字元數：{total_chars}",
        "",
        "## 來源分布",
        "",
    ]
    lines += [f"- {key}：{value}" for key, value in by_source.most_common()]
    lines += ["", "## 學習階段分布", ""]
    lines += [f"- {key}：{value}" for key, value in by_stage.most_common()]
    lines += ["", "## 教材類型分布", ""]
    lines += [f"- {key}：{value}" for key, value in by_type.most_common()]
    lines += ["", "## 教學欄位關鍵詞出現次數", ""]
    lines += [f"- {key}：{value}" for key, value in keyword_totals.most_common()]
    lines += [
        "",
        "## 後續分析方向",
        "",
        "- 從 `processed/pdf_text/` 抽出的文字建立 RAG 索引。",
        "- 依學習階段與教材類型拆出教案、學習單、評量規準與詞彙表。",
        "- 將學習表現、學習內容與核心素養對應到 108 課綱資料。",
        "- 將常見語詞、句型、臺羅與文化主題整理成可供自然語言生成教材的素材庫。",
    ]
    (ANALYSIS_ROOT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"已分析 {len(analyzed)} 個 PDF，摘要位於 {ANALYSIS_ROOT / 'summary.md'}")


if __name__ == "__main__":
    main()
