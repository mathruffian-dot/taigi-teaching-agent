# 臺語教材 AI Agent (taigi-teaching-agent)

本專案旨在依據臺灣 108 課綱與教育部規範，為本土語教師打造一個整合型的「臺語教材 AI Agent」。
教師輸入教學需求（年級、主題、學習目標等）後，Agent 能夠自動生成圖片、講義、測驗、離線互動網站、教學影片及聲音教材。

---

## 專案結構

- `docs/`：設計與架構文件。
- `knowledge/`：檔案型知識庫，包含課綱對照、台語漢字/臺羅詞彙及對話範例。
- `drafts/`：AI 產生的教材草稿。
- `verified/`：經教師審核並校對通過的正式教材與音檔。
- `templates/`：各種教材輸出格式模板（講義、網頁、測驗）。
- `assets/`：圖片、音訊等媒體素材。
- `src/`：Agent、RAG 檢索、TTS/STT 與教材生成的核心程式碼。
- `tests/`：測試案例與評估腳本。
- `output/`：最終打包輸出區。

---

## 工作模式與規範

本專案遵循 `CLAUDE.md` 定義之 AI 協作規則：
1. **開工**：對 AI 說「**開工**」，自動拉取上次進度、確認 Git 狀態並建議下一步。
2. **收工**：工作結束時對 AI 說「**收工**」，自動更新 Obsidian 專案駕駛艙筆記並自動 commit、push。
3. **專案規格**：
   - 漢字與臺羅拼音以教育部《臺灣台語常用詞辭典》與拼音方案為準。
   - 所有生成內容在進入 `verified/` 前，必須經過教師的人工審核與確認。

---

## 開發啟動指南

1. **環境需求**：
   - Windows 10/11, PowerShell, Git, GitHub CLI (`gh`), Node.js/npm.
2. **文字模型**：
   - 安裝 Ollama，並下載 `SARC-Taigi-LLM-12b-GGUF`。
3. **語音模型**：
   - 評估並部署 `Breeze-ASR-26` 或 `Whisper-Taiwanese-model-v0.5` 進行 STT。
