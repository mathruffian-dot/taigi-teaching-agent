# 2026本土語 — CLAUDE.md (專案藍圖)

## 對話開始時請先讀
進度與最近更動都在 Obsidian：`C:\Users\mathr\OneDrive\文件\Secondbrain\專案\2026本土語\專案工作流程.md`
（可以使用 `mcp__obsidian__read_note` 讀取）

---

## 專案入口

- **專案名稱**：`taigi-teaching-agent` (2026本土語)
- **專案用途**：依據臺灣 108 課綱與教育部規範，為本土語教師打造的「臺語教材 AI Agent」，能自動生成圖片、講義、測驗、離線互動網站、教學影片及聲音教材。
- **主要工作目錄**：`g:\我的雲端硬碟\2026本土語\`
- **GitHub repo**：`https://github.com/mathruffian-dot/taigi-teaching-agent`
- **預設 branch**：`main`

---

## Obsidian 對應筆記

- **Obsidian vault**：`C:\Users\mathr\OneDrive\文件\Secondbrain`
- **專案駕駛艙**：`專案/2026本土語/專案工作流程.md`
- **收工時優先更新**：同上

> 💡 **注意**：專案駕駛艙是 Obsidian vault 裡的一篇筆記，不是工作資料夾裡的 Markdown 檔。

---

## 工作桌 + 三個家

- **📋 GDrive 工作桌**：`g:\我的雲端硬碟\2026本土語\`（自動跨電腦同步工作檔與程式碼）
- **🐙 GitHub repo**：`https://github.com/mathruffian-dot/taigi-teaching-agent`（私有，備份與版本控制）
- **📘 Obsidian 駕駛艙**：`C:\Users\mathr\OneDrive\文件\Secondbrain\專案\2026本土語\專案工作流程.md`（想法、日誌、踩坑與規劃的家）
- **🔥 Firebase 專案**：未使用

---

## 主要模型與工具選型

1. **臺語文字模型**：`SARC-Taigi-LLM-12b-GGUF` (Ollama/llama.cpp)
2. **語音辨識模型 (STT)**：
   - `Breeze-ASR-26` (日常口語辨識)
   - `Whisper-Taiwanese-model-v0.5` (中小學教材跟讀/朗讀)
   - `Taiwan-Tongues-ASR-CE` (多語混合)
3. **語音合成 (TTS)**：串接 Taigi AI Labs 或 ATEN AI Voice 等展示服務進行第一階段驗證。
4. **漢字/臺羅檢核**：結合教育部常用詞辭典進行 Unicode 正規化、拼音檢查。

---

## 環境初始化與執行指令

- **環境初始化** (其他 Agent 接手)：
  ```powershell
  # 允許執行腳本並初始化環境
  Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
  .\setup.ps1
  ```
- **單元測試**：
  ```powershell
  # 執行拼音與檢索模組測試
  .venv\Scripts\pytest tests/
  ```
- **執行教材生成**：
  ```powershell
  # 執行教材生成主程式 (需提供測試案例路徑)
  .venv\Scripts\python src/generators/material_generator.py --case <測試案例路徑>
  ```

---

## 主要檔案結構

- `setup.ps1`：環境初始化與模型在線驗證腳本。
- `requirements.txt`：Python 套件依賴定義。
- `config.json` / `config.example.json`：設定檔（設定本機 Ollama、Obsidian 與 GitHub 參數）。
- `knowledge/`：辭典與 108 課綱資料庫。
  - `dictionaries/vocabulary_db.json` (常用詞 seed)
  - `curriculum/syllabus_108.json` (108 課綱 seed)
- `src/`：核心模組原始碼。
  - `tailo/validator.py` (臺羅拼音轉換與檢核)
  - `rag/retriever.py` (檔案型 RAG 檢索器)
  - `generators/material_generator.py` (教材 Word 與 HTML 生成主程式)
- `docs/`：日誌與引導手冊。
  - `testing-playbook.md` (測試 SOP)
  - `test-logs/` (教材測試日誌存檔區)

---

## 同步規則

- **開工時**：
  1. 使用 `startup` 流程。
  2. 讀取本檔 (`CLAUDE.md`)。
  3. 讀取 Obsidian 專案駕駛艙。
  4. 檢查 Git 狀態（不自動 pull/commit/push）。
- **收工時**：
  1. 使用 `shutdown` 流程。
  2. 檢查是否有敏感 API key 流出。
  3. 更新 Obsidian 專案駕駛艙的「⏯️ 上次做到哪」、「🗓️ 最近更動紀錄」與「🕳️ 踩坑筆記」。
  4. 只有規則、固定路徑或專案邊界改變時，才更新本檔 (`CLAUDE.md`)。
  5. 將本輪更動進行 `git commit` 與 `git push`（不包含 `.claude/` 暫存檔，且 commit 訊息需具備具體資訊）。

---

## 工作注意事項 (Do / Don't)

- **Do**：回應一律使用繁體中文。
- **Do**：臺語漢字以教育部《臺灣台語常用詞辭典》為依據，羅馬字採教育部《臺灣台語羅馬字拼音方案》（同時保存調符式與數字調）。
- **Do**：教材發布必須包含適用年級、學習目標與課綱依據，且正式 TTS 音訊必須經過教師審聽。
- **Don't**：不要把每日流水帳進度寫入本檔 (`CLAUDE.md`)，流水帳應寫進 Obsidian。
- **Don't**：不要 commit API key、token、Firebase Admin 憑證，且絕不可 commit `.claude/` 目錄。
- **Don't**：不要儲存學生真實姓名，正式資料一律以班級代號與座號代表。
- **Don't**：圖片生成模型不直接生成臺語文字，文字一律後製疊加。
