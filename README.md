# 臺語教材 AI Agent (taigi-teaching-agent)

本專案旨在依據臺灣 108 課綱與教育部規範，為本土語教師打造一個整合型的「臺語教材 AI Agent」。
教師輸入教學需求（年級、主題、學習目標等）後，Agent 能夠自動生成圖片、講義、測驗、離線互動網站、教學影片及聲音教材。

本專案目前的資料建置目標，是搜尋、下載、分類與整理臺灣中小學本土語（臺語）官方教材，並在整理完成後分析教材內容，作為自然語言生成臺語教材的知識基礎。

詳細目標見 [`docs/project-goals.md`](docs/project-goals.md)。

## 新使用者 5 分鐘上手

```powershell
git clone https://github.com/mathruffian-dot/taigi-teaching-agent.git
cd taigi-teaching-agent

# 1. 初始化環境（建立 .venv、安裝依賴）
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\setup.ps1

# 2. 建立自己的設定檔（config.json 不進 git）
Copy-Item config.example.json config.json

# 3. 開始使用
.venv\Scripts\python -m taigi --help
```

- **必要**：Python 3.10+、ffmpeg（語音合成轉檔用）
- **選配**：本機 Ollama＋`SARC-Taigi-LLM-12b`（AI 大綱生成用；缺模型會自動降級或改用 Mock）
- **建議**：`config.json` 的 `output.base_dir` 指向本機目錄（支援 `%USERPROFILE%`），大型音訊／影片產出不要放雲端同步資料夾
- 給 AI Agent 的完整操作手冊在 [`AGENTS.md`](AGENTS.md)——任何 agent 讀完即可操作本專案

## 快速使用（統一指令入口）

核心功能（標音、台語 TTS、內容檢核、教材生成）皆可透過 `python -m taigi` 使用，
任何 AI Agent 或使用者不必閱讀原始碼即可操作：

```powershell
.venv\Scripts\python -m taigi --help
.venv\Scripts\python -m taigi tts "逐家早起" -o out.wav   # 台語語音（意傳媠聲，免費）
.venv\Scripts\python -m taigi piau "今仔日天氣真好"        # 漢字→臺羅
```

完整指令手冊見 [`AGENTS.md`](AGENTS.md)「統一指令入口」章節；TTS 引擎選擇與審聽 SOP 見 [`docs/tts-ab-test.md`](docs/tts-ab-test.md)。

官方教材蒐集與分析流程見 [`docs/official-materials-workflow.md`](docs/official-materials-workflow.md)。

## 第三方資源授權聲明

本專案程式碼採 [MIT License](LICENSE)，但串接的外部資源各依其原條款，使用前請確認：

| 資源 | 用途 | 授權／使用條件 |
|------|------|----------------|
| 意傳科技「媠聲」（hapsing.ithuan.tw） | 整句台語語音合成 | 免費**展示服務**，限流 1 IP 每分鐘 3 句（程式已內建節流）。正式量產或商用前請洽[意傳科技](https://ithuan.tw/)，教材請標示語音來源 |
| 教育部《臺灣台語常用詞辭典》音檔（經萌典） | 單詞發音、接音合成 | 依教育部辭典使用條款，供教育用途；請勿將下載音檔重新散布 |
| `facebook/mms-tts-nan` | 本地備援 TTS | CC-BY-NC 4.0（**限非商業**） |
| 教育部官方教材（`data/official_materials/`） | 本地研究分析 | **僅本地保存，不隨本 repo 散布**（已由 .gitignore 排除）；來源清單見 `data/official_materials/sources.json`，請自行執行蒐集腳本下載 |
| 源石黑體（教學影片字體） | 影片字卡 | SIL OFL；不隨 repo 散布，可自 [ButTaiwan/genseki-font](https://github.com/ButTaiwan/genseki-font) 下載 |

**產出教材的發布規範**：須包含適用年級、學習目標與課綱依據；正式 TTS 音訊必須經本土語教師審聽（審聽 SOP 見 [`docs/tts-ab-test.md`](docs/tts-ab-test.md)）。

自然語言產出教材流程見 [`docs/natural-language-generation.md`](docs/natural-language-generation.md)。

官方教材資料倉庫健康檢查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit-official-repository.ps1
```

檢查結果位於 `data/official_materials/analysis/repository_audit.md`。

建立官方教材內文片段索引：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-snippet-index.ps1
```

片段索引位於 `data/official_materials/analysis/official_material_snippets.md`。

建立官方教材結構化素材庫：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-material-bank.ps1
```

素材庫摘要位於 `data/official_materials/analysis/official_material_bank.md`。

建立官方教材生成包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-generation-packs.ps1
```

生成包摘要位於 `data/official_materials/analysis/official_generation_packs.md`。

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
