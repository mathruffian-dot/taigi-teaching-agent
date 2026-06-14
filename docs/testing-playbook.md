# 臺語數位教材測試指南與日誌紀錄 Playbook (testing-playbook.md)

本文件定義本專案進行教材生成測試的標準流程與紀錄規範。所有測試結果必須完整紀錄，以便其他教師的 Agent 能夠查閱並重現。

---

## 1. 測試工作流程 (SOP)

### 步驟 1：定義教材需求
在 `tests/test_materials/` 中建立一個 `.json` 測試需求檔（例如 `test_case_market_001.json`）。範例內容：
```json
{
  "grade": "國中七年級",
  "theme": "菜市場買物件",
  "duration_minutes": 45,
  "learning_objectives": ["學會數量詞、詢價、日常對話"],
  "format": ["worksheet", "website"]
}
```

### 步驟 2：執行生成程式
啟動專案的教材生成程式：
```powershell
python src/generators/material_generator.py --config config.json --case tests/test_materials/test_case_market_001.json
```

### 步驟 3：人工與工具校對
1. **拼音檢核**：執行 `validator.py` 檢查生成內容之臺羅聲調符號是否正確。
2. **教師審核**：檢視產出的 `output/` 講義與離線網頁 HTML，確保漢字與臺羅符合教育部常用詞辭典標準。

### 步驟 4：錄入測試日誌
在 `docs/test-logs/` 下建立以日期與案例命名的日誌檔（如 `docs/test-logs/2026-06-14_case_market_001.md`）。

---

## 2. 測試日誌範本 (Test Log Template)

每次測試完成後，必須填寫並新增一篇測試日誌，其 Markdown 格式如下：

```markdown
# 測試日誌：[案例名稱] (YYYY-MM-DD)

## 1. 測試輸入參數
- **年級**：
- **主題**：
- **輸出格式**：

## 2. RAG 知識庫檢索結果
- 命中的課綱代碼：
- 命中的常用詞彙：

## 3. 產出檔案清單
- 講義路徑：
- 網頁路徑：

## 4. 驗證結果與品質評估
- [ ] 臺羅拼音格式驗證 (數字調與調符式對照相符)
- [ ] 漢字字體無亂碼
- [ ] 離線互動網頁點擊正常且無外部加載阻礙
- **教師審聽與修訂紀錄**：(記錄不正確的發音或標記)

## 5. 執行指令與耗時
- 執行指令：
- 總執行耗時 (秒)：
```

---

## 3. 測試目錄位置
- 測試案例定義：`tests/test_materials/`
- 測試輸出結果：`output/`
- 測試日誌歸檔：`docs/test-logs/`
