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
BANK_PATH = ANALYSIS_DIR / "official_material_bank.json"
PACK_OUTPUT = ANALYSIS_DIR / "official_generation_packs.json"
PACK_MD_OUTPUT = ANALYSIS_DIR / "official_generation_packs.md"


OUTPUT_TO_KINDS = {
    "exam": ["assessment", "worksheet", "curriculum"],
    "worksheet": ["worksheet", "vocabulary", "sentence_pattern", "lesson_plan"],
    "slides": ["lesson_plan", "vocabulary", "curriculum", "culture"],
    "video": ["lesson_plan", "media_activity", "sentence_pattern", "culture"],
    "interactive": ["worksheet", "assessment", "media_activity", "vocabulary"],
    "quiz": ["assessment", "worksheet", "vocabulary", "sentence_pattern"],
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def make_id(*parts: str) -> str:
    joined = "|".join(parts)
    return sha1(joined.encode("utf-8")).hexdigest()[:12]


def short_title(title: str, fallback: str = "官方教材素材") -> str:
    title = clean_text(title)
    return title[:60] if title else fallback


def extract_multiple_choice_items(item: dict[str, Any]) -> list[dict[str, Any]]:
    text = item.get("snippet", "")
    pattern = re.compile(
        r"[（(]\s*[）)]\s*(\d+)[.．、]?\s*(.*?)\s*"
        r"\(A\)\s*(.*?)\s*"
        r"\(B\)\s*(.*?)\s*"
        r"\(C\)\s*(.*?)\s*"
        r"\(D\)\s*(.*?)(?=(?:[（(]\s*[）)]\s*\d+[.．、]?)|(?:第二部份)|(?:第三部份)|$)",
        re.DOTALL,
    )
    results = []
    for match in pattern.finditer(text):
        number, question, a, b, c, d = match.groups()
        options = [clean_text(value) for value in (a, b, c, d)]
        if len([opt for opt in options if opt]) < 4:
            continue
        results.append({
            "asset_id": make_id(item.get("bank_id", ""), "mcq", number, question),
            "asset_type": "multiple_choice",
            "source_bank_id": item.get("bank_id"),
            "title": item.get("title"),
            "learning_stage": item.get("learning_stage"),
            "topics": item.get("topics", []),
            "material_kinds": item.get("material_kinds", []),
            "question": clean_text(question),
            "options": options,
            "answer_index": None,
            "teacher_answer_required": True,
            "source_url": item.get("page_url") or item.get("attachment_url"),
            "local_path": item.get("local_path"),
        })
    return results


def extract_reflection_prompts(item: dict[str, Any]) -> list[dict[str, Any]]:
    text = item.get("snippet", "")
    prompts = []
    if "4F" in text or "Fact" in text or "Feeling" in text:
        labels = ["Fact", "Feeling", "Finding", "Future"]
        for label in labels:
            match = re.search(rf"{label}（[^）]+）：(.*?)(?=(?:Fact|Feeling|Finding|Future)（|$)", text, re.DOTALL)
            if match:
                prompts.append(clean_text(match.group(1)))
        if prompts:
            return [{
                "asset_id": make_id(item.get("bank_id", ""), "reflection_4f"),
                "asset_type": "reflection_4f",
                "source_bank_id": item.get("bank_id"),
                "title": item.get("title"),
                "learning_stage": item.get("learning_stage"),
                "topics": item.get("topics", []),
                "material_kinds": item.get("material_kinds", []),
                "prompts": prompts,
                "source_url": item.get("page_url") or item.get("attachment_url"),
                "local_path": item.get("local_path"),
            }]
    return []


def extract_vocabulary_cards(item: dict[str, Any]) -> list[dict[str, Any]]:
    text = item.get("snippet", "")
    if "語詞" not in text and "詞彙" not in text and "臺羅拼音" not in text:
        return []

    cards = []
    row_pattern = re.compile(
        r"(?:^|\s)(\d{1,2})\s+([\u4e00-\u9fff𠊎-𫝛A-Za-zêÊôÔáàâāéèíìóòúùûūńǹ\-]+)\s+"
        r"([A-Za-záàâāéèêēíìîīóòôōúùûūńǹ]+(?:[- ][A-Za-záàâāéèêēíìîīóòôōúùûūńǹ]+)+)\s+"
        r"([^0-9]{1,40}?)(?=(?:\s\d{1,2}\s+)|$)"
    )
    for match in row_pattern.finditer(text):
        _, hanji, tailo, meaning = match.groups()
        hanji = clean_text(hanji)
        tailo = clean_text(tailo)
        meaning = clean_text(meaning)
        if len(hanji) > 12 or len(tailo) > 40 or not meaning:
            continue
        cards.append({
            "asset_id": make_id(item.get("bank_id", ""), "vocab", hanji, tailo),
            "asset_type": "vocabulary_card",
            "source_bank_id": item.get("bank_id"),
            "title": item.get("title"),
            "learning_stage": item.get("learning_stage"),
            "topics": item.get("topics", []),
            "material_kinds": item.get("material_kinds", []),
            "hanji": hanji,
            "tailo": tailo,
            "meaning": meaning,
            "source_url": item.get("page_url") or item.get("attachment_url"),
            "local_path": item.get("local_path"),
        })
    return cards


def extract_slide_seed(item: dict[str, Any]) -> dict[str, Any] | None:
    text = clean_text(item.get("snippet", ""))
    if not text:
        return None
    sentences = re.split(r"(?<=[。！？])\s*", text)
    bullets = [clean_text(sentence) for sentence in sentences if 18 <= len(clean_text(sentence)) <= 120]
    if len(bullets) < 2:
        phrases = re.split(r"[；;。]\s*", text)
        bullets = [clean_text(phrase) for phrase in phrases if 18 <= len(clean_text(phrase)) <= 120]
    if not bullets:
        return None
    heading = short_title(item.get("title", ""))
    if item.get("topics"):
        heading = f"{item['topics'][0]}：{heading}"
    return {
        "asset_id": make_id(item.get("bank_id", ""), "slide"),
        "asset_type": "slide_seed",
        "source_bank_id": item.get("bank_id"),
        "title": item.get("title"),
        "heading": heading,
        "learning_stage": item.get("learning_stage"),
        "topics": item.get("topics", []),
        "material_kinds": item.get("material_kinds", []),
        "bullets": bullets[:5],
        "source_url": item.get("page_url") or item.get("attachment_url"),
        "local_path": item.get("local_path"),
    }


def output_tags_for_item(item: dict[str, Any], asset_type: str) -> list[str]:
    kinds = set(item.get("material_kinds", []))
    tags = []
    for output, wanted in OUTPUT_TO_KINDS.items():
        if kinds.intersection(wanted):
            tags.append(output)
    if asset_type == "multiple_choice":
        tags.extend(["exam", "quiz", "interactive"])
    elif asset_type == "reflection_4f":
        tags.extend(["worksheet", "interactive", "slides"])
    elif asset_type == "vocabulary_card":
        tags.extend(["worksheet", "slides", "interactive", "quiz"])
    elif asset_type == "slide_seed":
        tags.extend(["slides", "video"])
    unique = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
    return unique


def build_generation_packs(material_bank: dict[str, Any]) -> dict[str, Any]:
    bank_items = material_bank.get("items", []) if isinstance(material_bank, dict) else []
    assets: list[dict[str, Any]] = []

    for item in bank_items:
        extracted = []
        extracted.extend(extract_multiple_choice_items(item))
        extracted.extend(extract_reflection_prompts(item))
        extracted.extend(extract_vocabulary_cards(item))
        slide_seed = extract_slide_seed(item)
        if slide_seed:
            extracted.append(slide_seed)

        for asset in extracted:
            asset["output_tags"] = output_tags_for_item(item, asset["asset_type"])
            assets.append(asset)

    by_type: Counter[str] = Counter(asset["asset_type"] for asset in assets)
    by_output: Counter[str] = Counter()
    by_topic: Counter[str] = Counter()
    for asset in assets:
        by_output.update(asset.get("output_tags", []))
        by_topic.update(asset.get("topics", []))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_bank_item_count": len(bank_items),
        "asset_count": len(assets),
        "by_asset_type": [{"name": name, "count": count} for name, count in by_type.most_common()],
        "by_output": [{"name": name, "count": count} for name, count in by_output.most_common()],
        "by_topic": [{"name": name, "count": count} for name, count in by_topic.most_common()],
        "assets": assets,
    }


def write_markdown(packs: dict[str, Any]) -> None:
    lines = [
        "# 官方教材生成包",
        "",
        f"產生時間：{packs['generated_at']}",
        "",
        "## 整體狀態",
        "",
        f"- 來源素材項目：{packs['source_bank_item_count']}",
        f"- 可生成資產：{packs['asset_count']}",
        "",
        "## 資產類型",
        "",
    ]
    lines += [f"- {row['name']}：{row['count']}" for row in packs["by_asset_type"]]
    lines += ["", "## 可支援產出", ""]
    lines += [f"- {row['name']}：{row['count']}" for row in packs["by_output"]]
    lines += ["", "## 主題分布", ""]
    lines += [f"- {row['name']}：{row['count']}" for row in packs["by_topic"][:12]]
    lines += ["", "## 範例", ""]
    for asset in packs["assets"][:8]:
        if asset["asset_type"] == "multiple_choice":
            preview = asset["question"]
        elif asset["asset_type"] == "vocabulary_card":
            preview = f"{asset['hanji']}｜{asset['tailo']}｜{asset['meaning']}"
        elif asset["asset_type"] == "reflection_4f":
            preview = "；".join(asset["prompts"][:2])
        else:
            preview = "；".join(asset.get("bullets", [])[:2])
        lines.append(f"- {asset['asset_type']}｜{asset.get('title', '')}｜{preview}")
    PACK_MD_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    material_bank = load_json(BANK_PATH, {})
    packs = build_generation_packs(material_bank)
    PACK_OUTPUT.write_text(json.dumps(packs, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(packs)
    print(f"完成：{PACK_OUTPUT}")
    print(f"完成：{PACK_MD_OUTPUT}")


if __name__ == "__main__":
    main()
