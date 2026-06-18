# 教學影片製作規範（Hyperframe 方式）

> 本專案的「教學影片」**一律採 Hyperframe（HyperFrames）方式製作**，
> **不使用** `teaching-cockpit` / `lesson-prep` 那類 NotebookLM 影片技能。
>
> 規範來源 repo：<https://github.com/mathruffian-dot/claude-video-specs-lite>
> （研習簡易版：全程免付費 API key；旁白用 Edge-TTS、圖片用 Unsplash 直連）

---

## 這是什麼

一條 **HTML 動畫 → Playwright 錄影 → ffmpeg 合成 mp4** 的影片管線，三層架構：

| Layer | 內容 |
|-------|------|
| 1 教學內容 | **SOIL 六引擎**（先想清楚教什麼，再做動畫）|
| 2 視覺呈現 | **HyperFrames 動畫**（單一 `index.html` 多頁切換 + CSS/SVG/JS 逐步揭露）+ KaTeX 數學 |
| 3 聲音 | **Edge-TTS** 旁白（免費、台灣腔 `zh-TW-YunJheNeural` / `zh-TW-HsiaoChenNeural`）|

規格細節（字級階、配色、動畫節奏、旁白規範、渲染管線指令）見 repo 的
`specs/02-教學影片.md`，開工前務必先讀 repo 的 `AGENTS.md`（5 階段流程）與 `GOTCHAS.md`（踩坑）。

---

## 本機環境現況（2026-06-18 盤點）

| 元件 | 狀態 |
|------|------|
| ffmpeg | ✅ 8.1 |
| Node.js | ✅ v24（⚠️ HyperFrames CLI 在 Node 24 會 crash，故**只用純 HTML 範本 + Playwright**，不走 HF CLI）|
| 源石黑體 GenSekiGothic2TW | ✅ H/B/M/L/R 全字重已裝於系統字體資料夾 |
| KaTeX | ✅ 走 CDN，免裝 |
| **edge-tts** | ✅ 已裝於 `.venv`（旁白生成）|
| **Playwright** | ⏳ **首次渲染時才裝**，依 HF 慣例裝在 `%TEMP%/cvs-render/`（不可裝在 GDrive，node_modules 會被同步弄壞）|

> 首支影片渲染前，跑 repo 的 `install/setup_playwright.sh`（或等 agent 自動處理）。

---

## 臺語專案的整合要點

1. **旁白語言分工**：
   - 講解/鷹架旁白（「我們來看……」）用 **Edge-TTS 華語**。
   - 課文中的**臺語例句發音**，改用本專案既有的臺語 TTS（`src/tts/generator.py` 的 concat / MMS provider，發音以教育部用字為準），再以 ffmpeg 併入該頁音軌。
2. **臺羅/漢字呈現**：影片字卡的臺語漢字與臺羅，必須先過 `src/tailo/validator.py` 一致性檢核（同本專案教材規範）。
3. **大型產出存放**：渲染出的 `.mp4`、`.mp3` 等大檔存到本機 `output.base_dir`（`config.json`，預設 `C:\Users\<你>\2026本土語\output`），**不存雲端硬碟**。
4. **數學正確性自檢**不適用於語言課，但「臺語正確性自檢」要做：用字、聲調符號、變調說明是否正確。

---

## 快速開始（做一支臺語教學影片）

對 agent 說「**做一支臺語教學影片**」並提供：**年級 / 單元主題 / 片長（預設 4–6 分鐘）**。
Agent 會依 repo `AGENTS.md` 5 階段流程：
1. 環境檢查（補裝 Playwright）
2. 跑 SOIL 引擎 1–3（概念定位 → 脈絡 → 頁面架構）→ 逐步給你確認
3. fork `examples/02-factors-multiples/` 範本改寫成臺語課
4. Edge-TTS 生旁白 + 臺語 TTS 生例句音 → ffmpeg 對齊
5. Playwright 錄影 → mux 成 mp4 → 預覽
