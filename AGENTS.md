# 2026本土語 — AGENTS.md (專案藍圖)

> 📖 **外部使用者／Agent 請從這裡開始**：先看下方「🤖 統一指令入口」章節與 README 的
> 「新使用者 5 分鐘上手」。標註〔維護者專用〕的段落是原作者的個人同步流程
> （Obsidian／多機同步），與使用本專案無關，可略過。

## 對話開始時請先讀〔維護者專用〕
進度與最近更動都在 Obsidian：`C:\Users\mathr\OneDrive\文件\Secondbrain\專案\2026本土語\專案工作流程.md`
（可以使用 `mcp__obsidian__read_note` 讀取）

---

## 專案入口

- **專案名稱**：`taigi-teaching-agent` (2026本土語)
- **專案用途**：依據臺灣 108 課綱與教育部規範，為本土語教師打造的「臺語教材 AI Agent」，能自動生成圖片、講義、測驗、離線互動網站、教學影片及聲音教材。
- **核心目標文件**：`docs/project-goals.md`
- **官方教材蒐集流程**：`docs/official-materials-workflow.md`
- **主要工作目錄**：`g:\我的雲端硬碟\2026本土語\`
- **GitHub repo**：`https://github.com/mathruffian-dot/taigi-teaching-agent`
- **預設 branch**：`main`

## 專案核心目標

1. 上網搜尋臺灣中小學本土語（臺語）的官方教材。
2. 將可公開取得、可合法保存的官方教材下載到本專案中。
3. 依來源、學習階段、年級、主題、教材類型與使用情境分類整理。
4. 整理完成後，針對教材進行課綱、詞彙、句型、臺羅、教學活動與評量題型分析。
5. 最終讓使用者只需在專案資料夾中使用自然語言，即可產出臺語考卷、簡報、影片、數位互動網站及程式、測驗。

> AI 接手時，若任務涉及教材蒐集、分類、分析或生成，請先參照 `docs/project-goals.md`。
---

## Obsidian 對應筆記〔維護者專用〕

- **Obsidian vault**：`C:\Users\mathr\OneDrive\文件\Secondbrain`
- **專案駕駛艙**：`專案/2026本土語/專案工作流程.md`
- **收工時優先更新**：同上

> 💡 **注意**：專案駕駛艙是 Obsidian vault 裡的一篇筆記，不是工作資料夾裡的 Markdown 檔。

---

## 工作桌 + 三個家〔維護者專用〕

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
3. **語音合成 (TTS)**（2026-07-04 定案）：**單詞／跟讀用 concat**（教育部官方音檔接音）、**整句旁白用意傳媠聲**（`ithuan` provider，免費展示服務、輸入臺羅 KIP、限流 3 句/分鐘已內建節流；量產前洽意傳科技）。中期追蹤 BreezyVoice-Taigi（聯發科，權重未釋出）；雅婷 TTS（付費）已寫好備用。審聽 SOP 見 `docs/tts-ab-test.md`。
4. **漢字/臺羅檢核**：結合教育部常用詞辭典進行 Unicode 正規化、拼音檢查。
5. **教學影片**：一律採 **Hyperframe（HyperFrames）方式**製作（HTML 動畫 → Playwright 錄影 → ffmpeg 合成 mp4，旁白用 Edge-TTS），**不使用** `teaching-cockpit` / `lesson-prep` 的 NotebookLM 影片技能。規範來源：<https://github.com/mathruffian-dot/Codex-video-specs-lite>；專案落地說明見 `docs/教學影片-hyperframe.md`。

---

## 🤖 統一指令入口（給任何 Agent）

**不必閱讀 `src/` 原始碼**：本專案的核心功能都可透過 `python -m taigi` 使用（於專案根目錄、以 `.venv` 的 Python 執行）。正確用法與護欄（意傳 TTS 須餵臺羅、限流節流、失敗降級）已內建於底層模組。

```powershell
.venv\Scripts\python -m taigi --help                                  # 指令總覽
.venv\Scripts\python -m taigi tts "逐家早起" -o out.wav               # 語音合成（預設意傳媠聲）
.venv\Scripts\python -m taigi tts "食飯" -o out.wav --provider concat # 官方接音（單詞/跟讀）
.venv\Scripts\python -m taigi piau "今仔日天氣真好"                    # 漢字→臺羅（KIP）
.venv\Scripts\python -m taigi check <教材.json>                       # 內容檢核（exit 2=有警告）
.venv\Scripts\python -m taigi generate --case <案例.json>             # 教材生成
.venv\Scripts\python -m taigi abtest --engines concat,ithuan          # TTS 審聽測試
```

- 各子指令支援 `--json` 輸出機器可讀 JSON（UTF-8 不轉義）。
- Exit code：`0` 成功、`1` 失敗、`check` 專用 `2`＝有檢核警告。
- **TTS 引擎選擇**：整句旁白 → `ithuan`（免費，限流 1 IP 每分鐘 3 句，程式已自動節流，**請勿繞過模組直接打 API**）；單詞／跟讀 → `concat`（教育部官方音檔，發音零錯誤）。細節與踩坑見 `docs/tts-ab-test.md`。
- **正式發布的 TTS 音訊必須經本土語教師審聽**（用 `abtest` 產出的 review.html 評分）。

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
- **安裝臺語文字模型**（Ollama；首次或換電腦時）：
  ```powershell
  # 下載官方 GGUF 後別名為 config 指定的模型名
  ollama pull hf.co/Speech-AI-Research-Center/SARC-Taigi-LLM-12b-GGUF:Q4_K_M
  ollama cp hf.co/Speech-AI-Research-Center/SARC-Taigi-LLM-12b-GGUF:Q4_K_M SARC-Taigi-LLM-12b:latest
  ```
  > 模型存於本機 `~/.ollama/models`（非雲端）。找不到時程式會自動退用 gemma/qwen。

### ⚠️ 大型產出存放位置（雲端硬碟限制）
- 音訊／影片／圖片等大檔**不存雲端硬碟**，改存本機目錄，避免 Google Drive 同步上萬大檔失敗。
- 路徑由 `config.json` 的 `output.base_dir` 指定（預設本機 `C:\Users\<你>\2026本土語\output`）。
- 未設定時退回專案內 `output/`（已被 `.gitignore` 排除）。
- 亦可用 `--output <目錄>` 於執行時覆寫。

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
  - `project-goals.md` (專案核心目標與教材整理原則)
  - `official-materials-workflow.md` (官方教材蒐集、下載與分析流程)
  - `testing-playbook.md` (測試 SOP)
  - `test-logs/` (教材測試日誌存檔區)

---

## 同步規則〔維護者專用〕

- **開工時**：
  1. 使用 `startup` 流程。
  2. 讀取本檔 (`AGENTS.md`)。
  3. 讀取 Obsidian 專案駕駛艙。
  4. 檢查 Git 狀態（不自動 pull/commit/push）。
- **收工時**：
  1. 使用 `shutdown` 流程。
  2. 檢查是否有敏感 API key 流出。
  3. 更新 Obsidian 專案駕駛艙的「⏯️ 上次做到哪」、「🗓️ 最近更動紀錄」與「🕳️ 踩坑筆記」。
  4. 只有規則、固定路徑或專案邊界改變時，才更新本檔 (`AGENTS.md`)。
  5. 將本輪更動進行 `git commit` 與 `git push`（不包含 `.Codex/` 暫存檔，且 commit 訊息需具備具體資訊）。

---

## 工作注意事項 (Do / Don't)

- **Do**：回應一律使用繁體中文。
- **Do**：臺語漢字以教育部《臺灣台語常用詞辭典》為依據，羅馬字採教育部《臺灣台語羅馬字拼音方案》（同時保存調符式與數字調）。
- **Do**：教材發布必須包含適用年級、學習目標與課綱依據，且正式 TTS 音訊必須經過教師審聽。
- **Don't**：不要把每日流水帳進度寫入本檔 (`AGENTS.md`)，流水帳應寫進 Obsidian。
- **Don't**：不要 commit API key、token、Firebase Admin 憑證，且絕不可 commit `.Codex/` 目錄。
- **Don't**：不要儲存學生真實姓名，正式資料一律以班級代號與座號代表。
- **Don't**：圖片生成模型不直接生成臺語文字，文字一律後製疊加。
