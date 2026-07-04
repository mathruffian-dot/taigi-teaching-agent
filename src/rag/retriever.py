# 檔案型 RAG 檢索器 (retriever.py)
import os
import sys
import json
import re
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print
print = safe_print

class TaigiRetriever:
    def __init__(self, database_dir: str = None):
        if database_dir is None:
            # 預設為專案根目錄的 knowledge 目錄
            current_dir = os.path.dirname(os.path.abspath(__file__))
            database_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "knowledge"))
            
        self.vocab_path = os.path.join(database_dir, "dictionaries", "vocabulary_db.json")
        self.syllabus_path = os.path.join(database_dir, "curriculum", "syllabus_108.json")
        project_root = os.path.abspath(os.path.join(database_dir, ".."))
        self.official_materials_index_path = os.path.join(
            project_root, "data", "official_materials", "analysis", "pdf_text_index.json"
        )
        self.official_materials_snippets_path = os.path.join(
            project_root, "data", "official_materials", "analysis", "official_material_snippets.json"
        )
        self.official_material_bank_path = os.path.join(
            project_root, "data", "official_materials", "analysis", "official_material_bank.json"
        )
        self.official_generation_packs_path = os.path.join(
            project_root, "data", "official_materials", "analysis", "official_generation_packs.json"
        )
        self.official_materials_catalog_path = os.path.join(
            project_root, "data", "official_materials", "catalog.json"
        )
        
        self.vocabulary_db = self._load_json(self.vocab_path)
        self.syllabus_db = self._load_json(self.syllabus_path)
        self.official_materials_index = self._load_json(self.official_materials_index_path)
        self.official_materials_snippets = self._load_json(self.official_materials_snippets_path)
        self.official_material_bank = self._load_json(self.official_material_bank_path)
        self.official_generation_packs = self._load_json(self.official_generation_packs_path)
        self.official_materials_catalog = self._load_json(self.official_materials_catalog_path)

    def _load_json(self, filepath: str) -> List[Dict[str, Any]]:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
        return []

    def _flatten_text_values(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            parts = []
            for item in value:
                parts.extend(self._flatten_text_values(item))
            return parts
        if isinstance(value, dict):
            parts = []
            for item in value.values():
                parts.extend(self._flatten_text_values(item))
            return parts
        return [str(value)]

    def _official_catalog_parts(self, item: Dict[str, Any]) -> List[str]:
        fields = [
            "title",
            "attachment_label",
            "learning_stage",
            "material_type",
            "level",
            "resource_content",
            "resource_kind",
            "provider",
            "description",
            "page_url",
            "attachment_url",
        ]
        parts = []
        for field in fields:
            parts.extend(self._flatten_text_values(item.get(field)))
        parts.extend(self._flatten_text_values(item.get("media_types", [])))
        parts.extend(self._flatten_text_values(item.get("related_links", [])))
        return [part for part in parts if part]

    def _official_catalog_snippet(self, item: Dict[str, Any]) -> str:
        snippet_parts = [
            item.get("title", ""),
            item.get("learning_stage", ""),
            item.get("material_type", ""),
            item.get("resource_kind", ""),
            "、".join(item.get("media_types", []) or []),
            item.get("provider", ""),
            item.get("description", ""),
        ]
        links = item.get("related_links", []) or []
        if links:
            link = links[0]
            label = link.get("label") or link.get("domain") or link.get("url", "")
            domain = link.get("domain", "")
            snippet_parts.append(f"{label} ({domain})" if domain else label)
        return "；".join(part for part in snippet_parts if part)

    def _query_terms(self, query: str) -> List[str]:
        q = (query or "").strip().lower()
        if not q:
            return []

        terms = [q]
        terms.extend(re.findall(r"[a-z0-9._-]+", q))
        for chunk in re.findall(r"[\u4e00-\u9fff]+", q):
            if len(chunk) <= 4:
                terms.append(chunk)
            else:
                for size in (4, 3, 2):
                    terms.extend(chunk[idx:idx + size] for idx in range(0, len(chunk) - size + 1))

        unique_terms = []
        for term in terms:
            term = term.strip()
            if len(term) < 2 and not term.isdigit():
                continue
            if term not in unique_terms:
                unique_terms.append(term)
        return unique_terms

    def _score_official_match(self, query: str, parts: List[str], body_text: str = "") -> int:
        q = (query or "").strip().lower()
        if not q:
            return 0

        fields = "\n".join(part for part in parts if part).lower()
        body = (body_text or "").lower()
        full_text = fields + "\n" + body
        if not full_text.strip():
            return 0

        score = 0
        if q in fields:
            score += 80 + fields.count(q) * 10
        elif q in body:
            score += 35 + min(body.count(q), 5)

        terms = [term for term in self._query_terms(q) if term != q]
        matched_terms = 0
        for term in terms:
            if term in fields:
                matched_terms += 1
                score += 8 + min(len(term), 6) + min(fields.count(term), 4)
            elif term in body:
                matched_terms += 1
                score += 2 + min(body.count(term), 3)

        if score == 0:
            return 0
        if q not in full_text and terms:
            required_matches = 1 if len(terms) <= 2 else 2
            if matched_terms < required_matches:
                return 0
        return score

    def _best_snippet_from_text(self, query: str, text: str) -> str:
        if not text:
            return ""
        text_lower = text.lower()
        terms = self._query_terms(query)
        positions = [text_lower.find(term) for term in terms if text_lower.find(term) >= 0]
        if not positions:
            return ""
        position = min(positions)
        start = max(0, position - 80)
        end = min(len(text), position + 180)
        return text[start:end].replace("\n", " ").strip()

    def retrieve_vocabulary(self, query: str) -> List[Dict[str, Any]]:
        """
        以漢字、台羅、或華語翻譯檢索詞彙。
        """
        q = query.lower().strip()
        if not q:
            return []

        exact_results = []
        partial_results = []
        for item in self.vocabulary_db:
            hanji = item.get("hanji", "").lower()
            tailo_diacritic = item.get("tailo_diacritic", "").lower()
            tailo_numeric = item.get("tailo_numeric", "").lower()
            zh_tw = item.get("zh_tw", "").lower()
            if q in {hanji, tailo_diacritic, tailo_numeric, zh_tw}:
                exact_results.append(item)
            elif len(q) >= 2 and (
                q in hanji or
                q in tailo_diacritic or
                q in tailo_numeric or
                q in zh_tw
            ):
                partial_results.append(item)
        return exact_results + partial_results

    def retrieve_syllabus_by_grade(self, grade_level: str) -> List[Dict[str, Any]]:
        """
        檢索符合年級的 108 課綱條目。
        """
        results = []
        # 例如 "國中七年級" 對照 "國中七至九年級"
        is_junior_high = "國中" in grade_level
        is_elementary = "國小" in grade_level
        
        for item in self.syllabus_db:
            item_grade = item.get("grade_level", "")
            if is_junior_high and "國中" in item_grade:
                results.append(item)
            elif is_elementary and "國小" in item_grade:
                results.append(item)
        return results

    def retrieve_official_materials(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        從官方教材 PDF 抽文字與頁面索引中找參考片段。
        """
        q = (query or "").strip().lower()
        if not q:
            return []

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        scored = []
        seen_urls = set()
        catalog_by_url = {
            item.get("attachment_url", ""): item
            for item in self.official_materials_catalog
            if item.get("attachment_url")
        }
        for item in self.official_materials_index:
            attachment_url = item.get("attachment_url", "")
            seen_urls.add(attachment_url)
            catalog_item = catalog_by_url.get(attachment_url, {})
            haystack_parts = [
                item.get("title", ""),
                item.get("attachment_label", ""),
                item.get("learning_stage", ""),
                item.get("material_type", ""),
            ] + self._official_catalog_parts(catalog_item)
            text_path = item.get("text_path")
            text = ""
            if text_path:
                full_text_path = os.path.join(project_root, text_path)
                if os.path.exists(full_text_path):
                    try:
                        with open(full_text_path, "r", encoding="utf-8") as f:
                            text = f.read()
                    except Exception:
                        text = ""
            score = self._score_official_match(q, haystack_parts, text)
            if score <= 0:
                continue

            text_snippet = self._best_snippet_from_text(q, text)
            if text_snippet:
                snippet = text_snippet
            elif catalog_item:
                snippet = self._official_catalog_snippet(catalog_item)
            else:
                snippet = "；".join(part for part in haystack_parts if part)
            scored.append({
                "title": item.get("title", ""),
                "attachment_label": item.get("attachment_label", ""),
                "learning_stage": item.get("learning_stage", ""),
                "material_type": item.get("material_type", ""),
                "page_url": item.get("page_url", ""),
                "local_path": item.get("local_path", ""),
                "resource_kind": catalog_item.get("resource_kind", ""),
                "media_types": catalog_item.get("media_types", []),
                "provider": catalog_item.get("provider", ""),
                "related_links": catalog_item.get("related_links", []),
                "snippet": snippet,
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        for item in self.official_materials_catalog:
            attachment_url = item.get("attachment_url", "")
            if attachment_url in seen_urls:
                continue

            haystack_parts = self._official_catalog_parts(item)
            score = self._score_official_match(q, haystack_parts)
            if score <= 0:
                continue

            scored.append({
                "title": item.get("title", ""),
                "attachment_label": item.get("attachment_label", ""),
                "learning_stage": item.get("learning_stage", ""),
                "material_type": item.get("material_type", ""),
                "page_url": item.get("page_url", ""),
                "local_path": item.get("local_path", ""),
                "resource_kind": item.get("resource_kind", ""),
                "media_types": item.get("media_types", []),
                "provider": item.get("provider", ""),
                "related_links": item.get("related_links", []),
                "snippet": self._official_catalog_snippet(item),
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def retrieve_official_material_snippets(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        從預先建立的官方教材文字片段索引中找具體內文。
        """
        q = (query or "").strip().lower()
        if not q:
            return []

        if isinstance(self.official_materials_snippets, dict):
            snippets = self.official_materials_snippets.get("snippets", [])
        else:
            snippets = self.official_materials_snippets or []

        scored = []
        for item in snippets:
            haystack_parts = [
                item.get("title", ""),
                item.get("attachment_label", ""),
                item.get("learning_stage", ""),
                item.get("material_type", ""),
                "、".join(item.get("topics", []) or []),
            ]
            score = self._score_official_match(q, haystack_parts, item.get("snippet", ""))
            if score <= 0:
                continue
            scored.append({
                "snippet_id": item.get("snippet_id", ""),
                "title": item.get("title", ""),
                "attachment_label": item.get("attachment_label", ""),
                "learning_stage": item.get("learning_stage", ""),
                "material_type": item.get("material_type", ""),
                "page_url": item.get("page_url", ""),
                "attachment_url": item.get("attachment_url", ""),
                "local_path": item.get("local_path", ""),
                "text_path": item.get("text_path", ""),
                "resource_kind": "text_snippet",
                "topics": item.get("topics", []),
                "snippet": item.get("snippet", ""),
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def retrieve_official_material_bank(
        self,
        query: str,
        material_kinds: List[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        從官方教材結構化素材庫依主題與用途找素材。
        """
        q = (query or "").strip().lower()
        if not q:
            return []

        wanted_kinds = set(material_kinds or [])
        if isinstance(self.official_material_bank, dict):
            items = self.official_material_bank.get("items", [])
        else:
            items = self.official_material_bank or []

        scored = []
        for item in items:
            item_kinds = item.get("material_kinds", []) or []
            if wanted_kinds and not wanted_kinds.intersection(item_kinds):
                continue

            haystack_parts = [
                item.get("title", ""),
                item.get("attachment_label", ""),
                item.get("learning_stage", ""),
                item.get("material_type", ""),
                "、".join(item_kinds),
                "、".join(item.get("topics", []) or []),
                "、".join(item.get("curriculum_codes", []) or []),
                "、".join(item.get("tailo_tokens", []) or []),
            ]
            score = self._score_official_match(q, haystack_parts, item.get("snippet", ""))
            if score <= 0:
                continue
            if wanted_kinds:
                score += 18
            if item.get("curriculum_codes"):
                score += 4

            scored.append({
                "bank_id": item.get("bank_id", ""),
                "snippet_id": item.get("snippet_id", ""),
                "title": item.get("title", ""),
                "attachment_label": item.get("attachment_label", ""),
                "learning_stage": item.get("learning_stage", ""),
                "material_type": item.get("material_type", ""),
                "material_kinds": item_kinds,
                "topics": item.get("topics", []),
                "curriculum_codes": item.get("curriculum_codes", []),
                "tailo_tokens": item.get("tailo_tokens", []),
                "page_url": item.get("page_url", ""),
                "attachment_url": item.get("attachment_url", ""),
                "local_path": item.get("local_path", ""),
                "text_path": item.get("text_path", ""),
                "resource_kind": "material_bank",
                "snippet": item.get("snippet", ""),
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def retrieve_official_generation_assets(
        self,
        query: str,
        output_tags: List[str] = None,
        asset_types: List[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        從官方教材生成包檢索可直接轉為考卷、簡報、互動網站或測驗的資產。
        """
        q = (query or "").strip().lower()
        if not q:
            return []

        wanted_outputs = set(output_tags or [])
        wanted_types = set(asset_types or [])
        if isinstance(self.official_generation_packs, dict):
            assets = self.official_generation_packs.get("assets", [])
        else:
            assets = self.official_generation_packs or []

        scored = []
        for asset in assets:
            asset_outputs = set(asset.get("output_tags", []) or [])
            asset_type = asset.get("asset_type", "")
            if wanted_outputs and not wanted_outputs.intersection(asset_outputs):
                continue
            if wanted_types and asset_type not in wanted_types:
                continue

            body_parts = [
                asset.get("question", ""),
                " ".join(asset.get("options", []) or []),
                " ".join(asset.get("prompts", []) or []),
                " ".join(asset.get("bullets", []) or []),
                asset.get("hanji", ""),
                asset.get("tailo", ""),
                asset.get("meaning", ""),
            ]
            haystack_parts = [
                asset.get("title", ""),
                asset.get("learning_stage", ""),
                asset_type,
                "、".join(asset_outputs),
                "、".join(asset.get("topics", []) or []),
                "、".join(asset.get("material_kinds", []) or []),
            ]
            score = self._score_official_match(q, haystack_parts, "\n".join(body_parts))
            if score <= 0:
                continue
            if wanted_outputs:
                score += 15
            if wanted_types:
                score += 10

            scored.append({
                **asset,
                "resource_kind": "generation_asset",
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def recommend_official_generation_assets(
        self,
        query: str,
        outputs: List[str] = None,
        limit_per_output: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        依產出類型推薦可直接轉用的官方生成資產。
        """
        outputs = outputs or ["worksheet", "slides", "interactive", "quiz"]
        recommendations: Dict[str, List[Dict[str, Any]]] = {}
        preferred_types = {
            "exam": ["multiple_choice", "vocabulary_card", "reflection_4f"],
            "worksheet": ["vocabulary_card", "reflection_4f", "multiple_choice", "slide_seed"],
            "slides": ["slide_seed", "vocabulary_card", "reflection_4f"],
            "video": ["slide_seed", "reflection_4f", "vocabulary_card"],
            "interactive": ["multiple_choice", "reflection_4f", "vocabulary_card"],
            "quiz": ["multiple_choice", "vocabulary_card"],
        }

        for output in outputs:
            candidates = self.retrieve_official_generation_assets(query, output_tags=[output], limit=30)
            ranked = []
            preferred = preferred_types.get(output, [])
            for asset in candidates:
                asset_type = asset.get("asset_type", "")
                type_rank = preferred.index(asset_type) if asset_type in preferred else len(preferred)
                score = asset.get("score", 0) - type_rank * 5
                if type_rank == 0:
                    score += 12
                ranked.append((score, asset))
            ranked.sort(key=lambda pair: pair[0], reverse=True)

            selected = []
            seen = set()
            for _, asset in ranked:
                key = asset.get("asset_id")
                if key in seen:
                    continue
                seen.add(key)
                selected.append(asset)
                if len(selected) >= limit_per_output:
                    break
            recommendations[output] = selected

        return recommendations

    def recommend_official_materials(
        self,
        query: str,
        outputs: List[str] = None,
        limit_per_output: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        依自然語言產出類型推薦官方素材。
        """
        outputs = outputs or ["worksheet", "slides", "interactive", "quiz"]
        candidates = self.retrieve_official_materials(query, limit=30)

        preference = {
            "exam": ["learning_resource", "text_reference", "website_tool", "interactive", "video"],
            "worksheet": ["learning_resource", "text_reference", "website_tool", "interactive", "video"],
            "slides": ["learning_resource", "video", "interactive", "website_tool", "text_reference"],
            "video": ["video", "audio", "learning_resource", "website_tool", "interactive"],
            "interactive": ["interactive", "website_tool", "learning_resource", "video", "text_reference"],
            "quiz": ["interactive", "learning_resource", "website_tool", "text_reference", "video"],
        }

        def local_bonus(item: Dict[str, Any]) -> int:
            if item.get("local_path"):
                return 10
            if item.get("attachment_label") and "PDF" in item.get("attachment_label", "").upper():
                return 8
            return 0

        recommendations: Dict[str, List[Dict[str, Any]]] = {}
        for output in outputs:
            preferred_kinds = preference.get(output, [])
            ranked = []
            for item in candidates:
                kind = item.get("resource_kind") or item.get("material_type", "")
                kind_rank = preferred_kinds.index(kind) if kind in preferred_kinds else len(preferred_kinds)
                score = item.get("score", 0) + local_bonus(item) - kind_rank * 4
                if kind_rank == 0:
                    score += 12
                ranked.append((score, item))
            ranked.sort(key=lambda pair: pair[0], reverse=True)

            selected = []
            seen = set()
            for _, item in ranked:
                key = item.get("page_url") or item.get("title")
                if key in seen:
                    continue
                seen.add(key)
                selected.append(item)
                if len(selected) >= limit_per_output:
                    break
            recommendations[output] = selected

        return recommendations

    def enrich_lesson_json(self, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        依據教材大綱 JSON，自動檢索並豐富其詞彙庫與課綱對照資訊。
        """
        grade = lesson_data.get("grade", "")
        
        # 1. 豐富課綱對照
        if "curriculum" not in lesson_data:
            lesson_data["curriculum"] = {
                "learning_performance": [],
                "learning_content": [],
                "core_competencies": []
            }
            
        syllabus_items = self.retrieve_syllabus_by_grade(grade)
        for s in syllabus_items:
            desc = f"[{s['code']}] {s['description']}"
            if s["type"] == "performance" and desc not in lesson_data["curriculum"]["learning_performance"]:
                lesson_data["curriculum"]["learning_performance"].append(desc)
            elif s["type"] == "content" and desc not in lesson_data["curriculum"]["learning_content"]:
                lesson_data["curriculum"]["learning_content"].append(desc)

        # 2. 自動檢索詞彙庫
        enriched_vocab = []
        for word in lesson_data.get("vocabulary", []):
            # 如果單純是字串，嘗試去檢索資料庫
            word_query = word if isinstance(word, str) else word.get("hanji", "")
            db_matches = self.retrieve_vocabulary(word_query)
            
            if db_matches:
                # 採用資料庫中的完整資訊
                enriched_vocab.append(db_matches[0])
            else:
                # 保留原狀或包裝成基礎格式
                if isinstance(word, str):
                    enriched_vocab.append({
                        "hanji": word,
                        "tailo_diacritic": "pending",
                        "tailo_numeric": "pending",
                        "zh_tw": "pending",
                        "review_status": "draft"
                    })
                else:
                    enriched_vocab.append(word)
                    
        lesson_data["vocabulary"] = enriched_vocab
        return lesson_data

if __name__ == "__main__":
    retriever = TaigiRetriever()
    print("詞彙檢索測試 (食飯):", retriever.retrieve_vocabulary("食飯"))
    print("課綱檢索測試 (國中):", len(retriever.retrieve_syllabus_by_grade("國中七年級")))
