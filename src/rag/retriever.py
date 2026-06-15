# 檔案型 RAG 檢索器 (retriever.py)
import os
import sys
import json
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
        
        self.vocabulary_db = self._load_json(self.vocab_path)
        self.syllabus_db = self._load_json(self.syllabus_path)

    def _load_json(self, filepath: str) -> List[Dict[str, Any]]:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
        return []

    def retrieve_vocabulary(self, query: str) -> List[Dict[str, Any]]:
        """
        以漢字、台羅、或華語翻譯檢索詞彙。
        """
        results = []
        q = query.lower().strip()
        for item in self.vocabulary_db:
            if (q in item.get("hanji", "").lower() or
                q in item.get("tailo_diacritic", "").lower() or
                q in item.get("tailo_numeric", "").lower() or
                q in item.get("zh_tw", "").lower()):
                results.append(item)
        return results

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
