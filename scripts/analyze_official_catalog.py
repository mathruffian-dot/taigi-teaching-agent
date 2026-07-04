# 官方教材 catalog 結構分析
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "official_materials"
CATALOG_PATH = DATA_DIR / "catalog.json"
ANALYSIS_DIR = DATA_DIR / "analysis"
JSON_OUTPUT = ANALYSIS_DIR / "official_catalog_analysis.json"
MD_OUTPUT = ANALYSIS_DIR / "official_catalog_analysis.md"

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
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def count_values(items: Iterable[Dict[str, Any]], field: str) -> Counter:
    counter: Counter = Counter()
    for item in items:
        value = item.get(field)
        if isinstance(value, list):
            counter.update(str(v) for v in value if v)
        elif value:
            counter[str(value)] += 1
    return counter


def top(counter: Counter, limit: int = 20) -> List[Dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def item_text(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    for field in ("title", "attachment_label", "learning_stage", "material_type", "resource_kind", "provider", "description"):
        value = item.get(field)
        if value:
            parts.append(str(value))
    for media in item.get("media_types", []) or []:
        parts.append(str(media))
    for link in item.get("related_links", []) or []:
        if isinstance(link, dict):
            parts.extend(str(link.get(key, "")) for key in ("label", "domain", "url"))
    return "\n".join(parts).lower()


def analyze(catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_source = count_values(catalog, "source_id")
    by_stage = count_values(catalog, "learning_stage")
    by_material_type = count_values(catalog, "material_type")
    by_resource_kind = count_values(catalog, "resource_kind")
    by_media_type = count_values(catalog, "media_types")
    by_provider = count_values(catalog, "provider")

    domains: Counter = Counter()
    downloadable = 0
    local_files = 0
    for item in catalog:
        if item.get("local_path"):
            local_files += 1
        attachment_url = item.get("attachment_url") or ""
        if attachment_url and attachment_url != item.get("page_url"):
            downloadable += 1
        for link in item.get("related_links", []) or []:
            if isinstance(link, dict) and link.get("domain"):
                domains[str(link["domain"])] += 1

    topic_counter: Counter = Counter()
    topic_examples: Dict[str, List[Dict[str, str]]] = {topic: [] for topic in TOPIC_KEYWORDS}
    for item in catalog:
        text = item_text(item)
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword.lower() in text for keyword in keywords):
                topic_counter[topic] += 1
                if len(topic_examples[topic]) < 5:
                    topic_examples[topic].append({
                        "title": item.get("title", ""),
                        "learning_stage": item.get("learning_stage", ""),
                        "resource_kind": item.get("resource_kind") or item.get("material_type", ""),
                        "page_url": item.get("page_url", ""),
                    })

    pdf_items = [item for item in catalog if str(item.get("local_path") or "").lower().endswith(".pdf")]
    non_pdf_indexed = [item for item in catalog if not item.get("local_path")]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "catalog_count": len(catalog),
        "downloadable_attachment_count": downloadable,
        "local_file_count": local_files,
        "local_pdf_count": len(pdf_items),
        "page_index_only_count": len(non_pdf_indexed),
        "by_source": top(by_source),
        "by_learning_stage": top(by_stage),
        "by_material_type": top(by_material_type),
        "by_resource_kind": top(by_resource_kind),
        "by_media_type": top(by_media_type),
        "top_providers": top(by_provider),
        "top_domains": top(domains),
        "topic_coverage": top(topic_counter),
        "topic_examples": topic_examples,
    }


def write_markdown(analysis: Dict[str, Any]) -> None:
    lines = [
        "# 官方教材 Catalog 分析",
        "",
        f"產生時間：{analysis['generated_at']}",
        "",
        "## 整體狀態",
        "",
        f"- Catalog 筆數：{analysis['catalog_count']}",
        f"- 已下載本機檔案：{analysis['local_file_count']}",
        f"- 已下載 PDF：{analysis['local_pdf_count']}",
        f"- 僅頁面索引或外部連結：{analysis['page_index_only_count']}",
        f"- 有附件網址的資源：{analysis['downloadable_attachment_count']}",
        "",
    ]

    sections = [
        ("來源分布", "by_source"),
        ("學習階段分布", "by_learning_stage"),
        ("素材類型分布", "by_material_type"),
        ("頁面資源分類", "by_resource_kind"),
        ("媒體類型", "by_media_type"),
        ("主要提供者", "top_providers"),
        ("外部網域", "top_domains"),
        ("常見教學主題", "topic_coverage"),
    ]
    for title, key in sections:
        lines.extend([f"## {title}", ""])
        for row in analysis.get(key, [])[:15]:
            lines.append(f"- {row['name']}：{row['count']}")
        lines.append("")

    lines.extend(["## 主題範例", ""])
    for topic, examples in analysis.get("topic_examples", {}).items():
        if not examples:
            continue
        lines.append(f"### {topic}")
        for item in examples:
            lines.append(f"- {item['title']}（{item['learning_stage']}／{item['resource_kind']}）")
        lines.append("")

    MD_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_json(CATALOG_PATH)
    analysis = analyze(catalog)
    JSON_OUTPUT.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(analysis)
    print(f"完成：{JSON_OUTPUT}")
    print(f"完成：{MD_OUTPUT}")


if __name__ == "__main__":
    main()
