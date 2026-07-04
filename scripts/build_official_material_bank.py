from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "official_materials"
ANALYSIS_DIR = DATA_DIR / "analysis"
SNIPPET_INDEX_PATH = ANALYSIS_DIR / "official_material_snippets.json"
BANK_OUTPUT = ANALYSIS_DIR / "official_material_bank.json"
BANK_MD_OUTPUT = ANALYSIS_DIR / "official_material_bank.md"

MATERIAL_KIND_RULES = {
    "lesson_plan": ["教案", "教學活動", "單元名稱", "教學節次", "教學流程", "活動設計"],
    "worksheet": ["學習單", "選擇題", "填充題", "問答題", "第一部份", "第二部份"],
    "assessment": ["評量", "評量規準", "測驗", "前測", "形成性評量", "總結性評量", "rubric"],
    "vocabulary": ["語詞", "詞彙", "推薦用字", "華台語對照", "詞彙學習", "字詞"],
    "sentence_pattern": ["句型", "例句", "語句", "對話", "口語", "文法學習"],
    "curriculum": ["學習表現", "學習內容", "核心素養", "課綱", "學習目標"],
    "culture": ["文化", "地方", "民俗", "祭典", "歷史", "臺灣好食物", "臺灣文史"],
    "media_activity": ["影片", "影音", "音檔", "配音", "朗讀", "互動", "遊戲"],
}

KIND_LABELS = {
    "lesson_plan": "教案",
    "worksheet": "學習單",
    "assessment": "評量",
    "vocabulary": "詞彙",
    "sentence_pattern": "句型／對話",
    "curriculum": "課綱對應",
    "culture": "文化素材",
    "media_activity": "影音互動",
}

CURRICULUM_CODE_PATTERN = re.compile(
    r"(?:[1-4]-[ⅠⅡⅢⅣⅤ]-\d|[A-D][a-z]-[ⅠⅡⅢⅣⅤ]-\d|閩-[EJUV]-[ABC]\d)"
)
TAILO_TOKEN_PATTERN = re.compile(
    r"\b(?:[ptkbdgmnlhsj]|ph|th|kh|ng|ts|tsh)[a-záàâāéèêēíìîīóòôōúùûūńǹ]+(?:[-'][a-záàâāéèêēíìîīóòôōúùûūńǹ]+)*(?:[1-9])?\b",
    re.IGNORECASE,
)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def classify_material_kinds(text: str, title: str = "", material_type: str = "") -> list[str]:
    haystack = "\n".join([title or "", material_type or "", text or ""]).lower()
    kinds = []
    for kind, keywords in MATERIAL_KIND_RULES.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            kinds.append(kind)
    return kinds or ["reference"]


def extract_curriculum_codes(text: str) -> list[str]:
    codes = CURRICULUM_CODE_PATTERN.findall(text or "")
    unique = []
    for code in codes:
        if code not in unique:
            unique.append(code)
    return unique[:20]


def extract_tailo_tokens(text: str) -> list[str]:
    tokens = TAILO_TOKEN_PATTERN.findall(text or "")
    blocked = {"http", "https", "www", "pdf", "doc", "com", "moe", "edu"}
    unique = []
    for token in tokens:
        cleaned = token.strip("-'").lower()
        if len(cleaned) < 3 or cleaned in blocked:
            continue
        if cleaned not in unique:
            unique.append(cleaned)
    return unique[:20]


def text_preview(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def build_material_bank(snippet_index: dict[str, Any]) -> dict[str, Any]:
    snippets = snippet_index.get("snippets", []) if isinstance(snippet_index, dict) else []
    items: list[dict[str, Any]] = []

    for snippet in snippets:
        text = snippet.get("snippet", "")
        kinds = classify_material_kinds(
            text,
            title=snippet.get("title", ""),
            material_type=snippet.get("material_type", ""),
        )
        curriculum_codes = extract_curriculum_codes(text)
        tailo_tokens = extract_tailo_tokens(text)
        source_id = snippet.get("source_id")
        resource_id = snippet.get("resource_id")
        snippet_id = snippet.get("snippet_id")

        items.append({
            "bank_id": f"{resource_id or source_id}-{snippet_id}",
            "source_id": source_id,
            "resource_id": resource_id,
            "snippet_id": snippet_id,
            "title": snippet.get("title"),
            "attachment_label": snippet.get("attachment_label"),
            "learning_stage": snippet.get("learning_stage"),
            "material_type": snippet.get("material_type"),
            "material_kinds": kinds,
            "topics": snippet.get("topics", []),
            "curriculum_codes": curriculum_codes,
            "tailo_tokens": tailo_tokens,
            "page_url": snippet.get("page_url"),
            "attachment_url": snippet.get("attachment_url"),
            "local_path": snippet.get("local_path"),
            "text_path": snippet.get("text_path"),
            "char_count": snippet.get("char_count", len(text)),
            "snippet": text,
            "preview": text_preview(text),
        })

    by_kind: Counter[str] = Counter()
    by_topic: Counter[str] = Counter()
    by_stage: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    curriculum_item_count = 0
    tailo_item_count = 0
    for item in items:
        by_kind.update(item["material_kinds"])
        by_topic.update(item.get("topics", []))
        by_stage[item.get("learning_stage") or "未標示"] += 1
        by_source[item.get("source_id") or "unknown"] += 1
        if item["curriculum_codes"]:
            curriculum_item_count += 1
        if item["tailo_tokens"]:
            tailo_item_count += 1

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_snippet_count": len(snippets),
        "bank_item_count": len(items),
        "curriculum_item_count": curriculum_item_count,
        "tailo_item_count": tailo_item_count,
        "by_material_kind": [{"name": name, "label": KIND_LABELS.get(name, name), "count": count} for name, count in by_kind.most_common()],
        "by_topic": [{"name": name, "count": count} for name, count in by_topic.most_common()],
        "by_learning_stage": [{"name": name, "count": count} for name, count in by_stage.most_common()],
        "by_source": [{"name": name, "count": count} for name, count in by_source.most_common()],
        "items": items,
    }


def write_markdown(bank: dict[str, Any]) -> None:
    lines = [
        "# 官方教材結構化素材庫",
        "",
        f"產生時間：{bank['generated_at']}",
        "",
        "## 整體狀態",
        "",
        f"- 來源文字片段：{bank['source_snippet_count']}",
        f"- 素材項目：{bank['bank_item_count']}",
        f"- 含課綱代碼項目：{bank['curriculum_item_count']}",
        f"- 含臺羅線索項目：{bank['tailo_item_count']}",
        "",
        "## 素材類型分布",
        "",
    ]
    lines += [f"- {row['label']}（{row['name']}）：{row['count']}" for row in bank["by_material_kind"]]
    lines += ["", "## 主題分布", ""]
    lines += [f"- {row['name']}：{row['count']}" for row in bank["by_topic"][:12]]
    lines += ["", "## 學習階段分布", ""]
    lines += [f"- {row['name']}：{row['count']}" for row in bank["by_learning_stage"][:12]]
    lines += [
        "",
        "## 用途",
        "",
        "- 讓 RAG 能依教案、學習單、評量、詞彙、句型與課綱對應檢索官方教材素材。",
        "- 供自然語言生成考卷、簡報、影片、互動網站與測驗時引用更精準的官方教材依據。",
        "- 後續可把 `material_kinds` 與 `topics` 當作篩選條件，建立分年級、分主題的教材模板。",
        "",
        "## 範例素材",
        "",
    ]
    for item in bank["items"][:8]:
        labels = "、".join(KIND_LABELS.get(kind, kind) for kind in item["material_kinds"])
        topics = "、".join(item.get("topics", []) or ["未標示"])
        lines.append(f"- {item['title']}｜{item['learning_stage']}｜{labels}｜{topics}：{item['preview']}")
    BANK_MD_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    snippet_index = load_json(SNIPPET_INDEX_PATH, {})
    bank = build_material_bank(snippet_index)
    BANK_OUTPUT.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(bank)
    print(f"完成：{BANK_OUTPUT}")
    print(f"完成：{BANK_MD_OUTPUT}")


if __name__ == "__main__":
    main()
