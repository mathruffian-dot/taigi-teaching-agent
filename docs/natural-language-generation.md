# 自然語言產出臺語教材流程

本流程用來推進專案核心目標：使用者只需在專案資料夾中用自然語言描述需求，即可產出臺語教材素材。

## PowerShell 入口

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\new-taigi-material.ps1 "幫我做國中七年級有機菜蔬的簡報、互動網站和測驗" -NoVideo -NoMedia
```

若需要同時產生教學影片：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\new-taigi-material.ps1 "幫我做國中七年級有機菜蔬的簡報、互動網站、測驗和影片" -Video
```

影片流程會使用 Node.js、Playwright 與 FFmpeg，在 `%TEMP%\taigi-video-render\` 建立暫存錄影環境，避免把 `node_modules` 與錄影暫存檔放進 Google Drive。Windows 下會優先使用 `npm.cmd` / `npx.cmd`，避開 PowerShell 執行原則造成的 `npm.ps1` 阻擋。

## 目前會產生的檔案

自然語言入口會先產生教材大綱，再交給教材生成器輸出：

- `outline.json`：自然語言解析後的大綱。
- `lesson_structure.json`：已經過 RAG、課綱、詞彙、官方教材索引與官方生成素材補強的教材結構。
- `student_worksheet.docx`：學生版講義，可作為考卷或學習單基礎。
- `teacher_guide.docx`：教師解答版。
- `exam_paper.docx`：獨立學生考卷。
- `exam_answer_key.docx`：獨立考卷解答。
- `quiz_bank.json`：獨立測驗題庫，可供程式、互動網站或後續匯入流程使用。
- `quiz_teacher_key.md`：測驗教師答案與官方延伸題確認清單。
- `teaching_slides.pptx`：PowerPoint 簡報。
- `interactive_website.html`：離線互動網站，內含測驗互動。
- `teacher_review_report.md`：教師審核報告。
- `generation_manifest.json`：本次自然語言需求、解析結果、依產出類型分組的官方素材推薦、官方生成素材，以及所有輸出檔路徑。
- `generation_validation.json`：產出資料夾驗證結果。
- `generation_validation.md`：給教師或接手 Agent 閱讀的驗證摘要。
- `lesson_video.mp4`：只有需求包含影片或使用 `-Video` 時才產生。

若需求包含影片但本次用 `-NoVideo` 跳過，`generation_manifest.json` 會在 `video_generation` 記錄 `disabled_by_option`，`generation_validation.md` 也會標示「影片生成：已用選項跳過」。若實際嘗試產生影片但失敗，驗證器會將本次產出判為未通過，避免只有影片路徑卻沒有 MP4 檔。

## 輸出位置

未指定 `-Output` 時，輸出位置依 `config.json` 的 `output.base_dir` 決定，並自動放在：

```text
<output.base_dir>\natural_language\<日期時間>_<主題>\
```

可用 `-Output` 指定固定資料夾：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\new-taigi-material.ps1 "幫我做國中七年級菜市仔買物件的講義和測驗" -Output "C:\Users\user\2026本土語\output\demo-market" -NoVideo
```

## 快速模式

建議先用 `-NoMedia` 產出文字類教材，確認內容後再產生音訊、圖片或影片：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\new-taigi-material.ps1 "幫我做國中七年級身體五官的考卷、簡報、互動網站和測驗" -NoVideo -NoMedia
```

`-NoMedia` 會跳過：

- 詞彙音檔下載或語音合成。
- 對話音檔合成。
- 詞彙圖片生成。

未使用 `-NoMedia` 時，詞彙圖片會先嘗試 AI Horde 免費匿名生圖；若排隊或連線超過 `config.json` 的 `image.max_wait_sec`，會自動改用本機 fallback 插圖，避免正式教材缺圖。

仍會產出：

- 考卷、講義、教師版、簡報、互動網頁、教師審核報告與 manifest。
- 獨立測驗題庫 `quiz_bank.json` 與教師答案 `quiz_teacher_key.md`。
- 官方教材推薦與課綱、詞彙、臺羅資料。
- 官方教材文字片段索引中的具體內文參考。
- 官方教材結構化素材庫中的教案、學習單、評量、詞彙、句型與課綱對應素材。
- 官方教材生成包中的選擇題、詞彙卡、投影片素材與互動反思活動。

## 目前解析規則

- 年級：會抓 `國小一年級` 到 `國中九年級`、`高一` 到 `高三`，以及第一到第五學習階段；未指定時預設 `國中七年級`。
- 類型：會辨識考卷、講義、簡報、影片、互動網站、測驗等關鍵字。
- 主題：會移除年級、產出類型與常見動詞後，保留核心主題，例如「有機菜蔬」。

## 官方素材推薦

自然語言入口會依輸出類型挑選官方素材：

- 考卷、講義：優先教案、學習單、文字參考或已下載 PDF。
- 簡報：優先可作課堂展示或導入的學習資源、影片與互動素材。
- 影片：優先教育部索引中的影音、電視節目、YouTube 資源。
- 互動網站、測驗：優先 Wordwall、線上遊戲、網站工具與可轉成題目的學習資源。

推薦結果會寫入 `outline.json`、`lesson_structure.json`、`teacher_review_report.md` 與 `generation_manifest.json`。

自然語言大綱生成會優先檢索 `data/official_materials/analysis/official_material_bank.json`，把已下載官方 PDF 中已分類的教案、學習單、評量、詞彙、句型與課綱素材提供給模型；若素材庫查無結果，才退回文字片段索引與整份教材索引。

產出清單 `generation_manifest.json` 會另外保存 `official_generation_assets`，依考卷、簡報、互動網站與測驗分組列出可直接轉用的官方素材。這些素材會同步寫入 `lesson_structure.json`，並進入學生講義、考卷、簡報與互動網站的官方延伸區塊；若選擇題沒有官方答案，會標記「需教師確認正確答案」，不會混入自動判分題庫。

## 產出後驗證

自然語言入口預設會在產出完成後驗證資料夾，確認 manifest、Word、PowerPoint、HTML、教材結構 JSON 都存在且可開啟。

也可以手動驗證任一輸出資料夾：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-generation-output.ps1 "output\smoke_no_media"
```

如果只想產出、不驗證，可加上 `-NoValidate`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\new-taigi-material.ps1 "幫我做國中七年級身體五官的考卷、簡報、互動網站和測驗" -NoVideo -NoMedia -NoValidate
```

## 注意

- 正式上課前仍需教師審核台語漢字、臺羅、音訊與官方教材引用是否適合。
- 大型輸出、音訊與影片建議放在本機 `C:\Users\user\2026本土語\output`，避免 Google Drive 同步大量檔案。
- 目前正式端到端範例位於 `C:\Users\user\2026本土語\output\formal_full_goal_demo`，已使用真實 TTS、圖片 fallback 與影片生成。
- 正式輸出前可先跑 readiness 稽核：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit-formal-output-readiness.ps1 -LiveNetwork -AttemptTtsSample
```
