from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "official_materials"
ANALYSIS_DIR = DATA_DIR / "analysis"
PDF_TEXT_INDEX_PATH = ANALYSIS_DIR / "pdf_text_index.json"
SNIPPET_OUTPUT = ANALYSIS_DIR / "official_material_snippets.json"
SNIPPET_MD_OUTPUT = ANALYSIS_DIR / "official_material_snippets.md"

TOPIC_KEYWORDS = {
    "身體五官": ["身體", "身軀", "五官", "頭", "手", "跤", "目睭", "喙"],
    "食物與市場": ["菜蔬", "菜市", "食物", "夜市", "點心", "飯", "麵", "茶", "果子", "買"],
    "臺羅拼音": ["臺羅", "台羅", "羅馬字", "拼音", "聲調", "入聲", "韻母", "聲母"],
    "字音字形": ["字音字形", "漢字", "正字", "書寫", "台文", "臺文"],
    "生活對話": ["問路", "時間", "天氣", "交通", "公園", "圖書館", "自我介紹"],
    "情緒與品德": ["情緒", "心情", "品德", "人權", "分享", "朋友"],
    "自然與環境": ["自然", "環境", "動物", "昆蟲", "鳥", "海", "颱風", "有機"],
    "文化與地方": ["媽祖", "歌仔戲", "布袋戲", "鹿港", "台南", "臺南", "高雄", "基隆"],
    "遊戲互動": ["wordwall", "遊戲", "互動", "賓果", "輪盤", "測驗"],
    "聽說朗讀": ["朗讀", "聽", "有聲", "廣播", "口說", "配音", "故事"],
    "課綱與評量": ["學習表現", "學習內容", "核心素養", "評量", "學習目標"],
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_long_text(text: str, max_chars: int = 850, overlap: int = 80) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        window = text[start:end]
        if end < len(text):
            split_at = max(window.rfind("。"), window.rfind("；"), window.rfind("\n"))
            if split_at >= max_chars * 0.45:
                end = start + split_at + 1
                window = text[start:end]
        chunks.append(window.strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def paragraph_chunks(text: str, min_chars: int = 80, max_chars: int = 850) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_len = 0

    for paragraph in paragraphs:
        paragraph = re.sub(r"\s*\n\s*", " ", paragraph).strip()
        if len(paragraph) > max_chars:
            if buffer:
                chunks.append(" ".join(buffer).strip())
                buffer = []
                buffer_len = 0
            chunks.extend(split_long_text(paragraph, max_chars=max_chars))
            continue

        if buffer and buffer_len + len(paragraph) + 1 > max_chars:
            chunks.append(" ".join(buffer).strip())
            buffer = []
            buffer_len = 0

        buffer.append(paragraph)
        buffer_len += len(paragraph) + 1

        if buffer_len >= min_chars:
            chunks.append(" ".join(buffer).strip())
            buffer = []
            buffer_len = 0

    if buffer:
        chunks.append(" ".join(buffer).strip())

    return [chunk for chunk in chunks if len(chunk) >= min_chars]


def detect_topics(text: str) -> list[str]:
    lowered = text.lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            topics.append(topic)
    return topics


def keyword_counts(text: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for keywords in TOPIC_KEYWORDS.values():
        for keyword in keywords:
            count = text.count(keyword)
            if count:
                counts[keyword] += count
    return dict(counts.most_common(12))


def build_snippet_index(pdf_text_index: list[dict[str, Any]], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    snippets: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for item in pdf_text_index:
        text_path_value = item.get("text_path")
        if not text_path_value:
            skipped.append({"resource_id": item.get("resource_id"), "reason": "missing_text_path"})
            continue

        text_path = project_root / text_path_value
        if not text_path.exists():
            skipped.append({
                "resource_id": item.get("resource_id"),
                "reason": "text_path_not_found",
                "text_path": text_path_value,
            })
            continue

        text = normalize_text(text_path.read_text(encoding="utf-8-sig"))
        chunks = paragraph_chunks(text)
        for index, chunk in enumerate(chunks, start=1):
            source_key = "|".join([
                str(item.get("resource_id") or ""),
                str(item.get("attachment_url") or ""),
                str(index),
                chunk[:80],
            ])
            snippets.append({
                "snippet_id": sha1(source_key.encode("utf-8")).hexdigest()[:12],
                "chunk_index": index,
                "source_id": item.get("source_id"),
                "resource_id": item.get("resource_id"),
                "title": item.get("title"),
                "attachment_label": item.get("attachment_label"),
                "learning_stage": item.get("learning_stage"),
                "material_type": item.get("material_type"),
                "page_url": item.get("page_url"),
                "attachment_url": item.get("attachment_url"),
                "local_path": item.get("local_path"),
                "text_path": item.get("text_path"),
                "char_count": len(chunk),
                "topics": detect_topics(chunk),
                "keyword_counts": keyword_counts(chunk),
                "snippet": chunk,
            })

    by_source = Counter(snippet["source_id"] for snippet in snippets)
    by_topic: Counter[str] = Counter()
    for snippet in snippets:
        by_topic.update(snippet["topics"])

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_pdf_count": len(pdf_text_index),
        "snippet_count": len(snippets),
        "skipped_count": len(skipped),
        "by_source": [{"name": name, "count": count} for name, count in by_source.most_common()],
        "by_topic": [{"name": name, "count": count} for name, count in by_topic.most_common()],
        "skipped": skipped,
        "snippets": snippets,
    }


def write_markdown(index: dict[str, Any]) -> None:
    lines = [
        "# 官方教材文字片段索引",
        "",
        f"產生時間：{index['generated_at']}",
        "",
        "## 整體狀態",
        "",
        f"- 來源 PDF：{index['source_pdf_count']}",
        f"- 片段數：{index['snippet_count']}",
        f"- 跳過項目：{index['skipped_count']}",
        "",
        "## 來源分布",
        "",
    ]
    lines += [f"- {row['name']}：{row['count']}" for row in index["by_source"]]
    lines += ["", "## 主題分布", ""]
    lines += [f"- {row['name']}：{row['count']}" for row in index["by_topic"]]
    lines += [
        "",
        "## 用途",
        "",
        "- 供 RAG 直接檢索官方教材內文片段。",
        "- 支援自然語言產出教材時引用更具體的官方教材內容。",
        "- 後續可依 `topics`、`learning_stage`、`material_type` 建立更細的教案、學習單與評量素材庫。",
    ]
    SNIPPET_MD_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_text_index = load_json(PDF_TEXT_INDEX_PATH, [])
    index = build_snippet_index(pdf_text_index)
    SNIPPET_OUTPUT.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(index)
    print(f"完成：{SNIPPET_OUTPUT}")
    print(f"完成：{SNIPPET_MD_OUTPUT}")


if __name__ == "__main__":
    main()
