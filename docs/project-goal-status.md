# 專案目標完成度與驗證證據

更新日期：2026-07-04

本文件用來追蹤 `docs/project-goals.md` 中專案目標的目前完成度。這不是每日流水帳，而是給接手 Agent 與教師快速確認「哪些已可驗證、哪些仍需補強」的狀態表。

## 1. 官方教材蒐集、下載、分類與分析

目前狀態：核心資料倉庫可用；可取得的本機 PDF 已下載並抽文字，另有 2 筆官方附件已確認目前不可取得。

已驗證證據：

- 官方教材 catalog：`data/official_materials/catalog.json`
- 官方教材來源清單：`data/official_materials/sources.json`
- 資料倉庫稽核：`data/official_materials/analysis/repository_audit.md`
- 官方教材文字片段索引：`data/official_materials/analysis/official_material_snippets.md`
- 官方教材結構化素材庫：`data/official_materials/analysis/official_material_bank.md`
- 官方教材生成包：`data/official_materials/analysis/official_generation_packs.md`
- 已確認不可取得附件：`data/official_materials/analysis/unavailable_attachments.md`
- 專案總目標稽核：`docs/project-goal-audit.md`

截至最近稽核：

- Catalog 筆數：868
- 官方來源數：3
- 本機 PDF：50 份
- PDF 抽文字覆蓋：50 / 50
- 缺必要欄位：0
- catalog 指到不存在的本機檔案：0
- 零位元組本機檔案：0
- 本機 PDF 尚未抽文字：0
- 有附件但尚未下載：0
- 已確認附件不可取得：2

仍需補強：

1. 定期重新檢查 2 筆目前已確認不可取得的附件；若官方恢復服務或出現替代官方來源，再補抓：
   - `https://acdm.tcssh.tc.edu.tw/teach/parent_%20language/parent/book/book_2.pdf`
   - `https://cirn.moe.edu.tw/Upload/NEWS/638362678533318547.pdf`
2. 若新增官方來源，需重新執行蒐集、分類、抽文字、素材庫與生成包流程。
3. 若官方網站內容更新，需重新跑 catalog 與稽核，避免現有索引過期。

## 2. 自然語言產出五類教材

目前狀態：核心端到端流程已可用，已用同一句自然語言同時產出五類成品並通過驗證。

驗證需求：

```text
幫我做國中七年級有機菜蔬的考卷、簡報、影片、互動網站和測驗
```

驗證輸出資料夾：

```text
output/smoke_full_goal_all_outputs/
```

已產出並驗證的核心檔案：

- 考卷：`output/smoke_full_goal_all_outputs/exam_paper.docx`
- 考卷解答：`output/smoke_full_goal_all_outputs/exam_answer_key.docx`
- 簡報：`output/smoke_full_goal_all_outputs/teaching_slides.pptx`
- 影片：`output/smoke_full_goal_all_outputs/lesson_video.mp4`
- 互動網站及程式：`output/smoke_full_goal_all_outputs/interactive_website.html`
- 測驗題庫：`output/smoke_full_goal_all_outputs/quiz_bank.json`
- 測驗教師答案：`output/smoke_full_goal_all_outputs/quiz_teacher_key.md`
- 產出清單：`output/smoke_full_goal_all_outputs/generation_manifest.json`
- 驗證報告：`output/smoke_full_goal_all_outputs/generation_validation.md`

最近驗證摘要：

- 產出類型：`exam, slides, video, interactive, quiz`
- 驗證結果：通過
- 主題貼合：通過
- 測驗題庫：3 題自動計分，3 題官方延伸
- 影片生成：成功
- 影片長度：52 秒

## 3. 正式輸出模式 Readiness

目前狀態：正式輸出必要環境已通過 readiness 稽核，包含本機輸出目錄、真實 TTS、標音、生圖端點、影片工具鏈與官方素材。

驗證指令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit-formal-output-readiness.ps1 -LiveNetwork -AttemptTtsSample
```

驗證證據：

- Readiness 報告：`docs/formal-output-readiness.md`
- Readiness JSON：`docs/formal-output-readiness.json`
- 輸出目錄：`C:\Users\user\2026本土語\output`
- TTS provider：`voxcpm`
- 真實 TTS 樣本：已直接呼叫 VoxCPM2 產生，未接受 dummy 降級。
- 標音樣本：`菜市仔` → `Tshài-tshī-á`
- 生圖端點：AI Horde heartbeat HTTP 200。
- 影片工具鏈：Node.js、npm、npx、FFmpeg、FFprobe 與 Temp Playwright cache 均通過。

## 4. 正式上課包端到端證據

目前狀態：已不用 `-NoMedia` 產出一份完整正式包，包含真實 TTS 音檔、詞彙圖片、影片、考卷、簡報、互動網站與測驗。

驗證需求：

```text
幫我做國中七年級有機菜蔬的考卷、簡報、影片、互動網站和測驗
```

正式包輸出資料夾：

```text
C:\Users\user\2026本土語\output\formal_full_goal_demo
```

最近驗證摘要：

- 驗證結果：通過
- 快速模式：`skip_media=false`
- TTS 音檔：7 個
- 詞彙圖片：4 張（AI Horde 排隊逾時後，自動改用本機 fallback 圖）
- 影片生成：成功
- 核心輸出：考卷、簡報、影片、互動網站、測驗皆已產生。

## 5. 後續仍需持續維護的項目

目前可驗證的專案目標已由 `docs/project-goal-audit.md` 通過；下列不是阻擋完成的程式缺口，而是長期維護與正式上課前審核事項：

1. 官方教材資料倉庫有 2 筆附件已確認目前不可取得，需日後監測是否恢復或出現替代官方來源。
2. 「所有官方教材」會隨官方網站更新而變動，需定期重新搜尋與稽核。
3. 正式上課音訊仍需教師審聽，確認語氣、斷句與發音符合課堂需求。
4. 官方生成包中的官方延伸題仍有部分答案需教師依官方教材確認，已避免自動計分，但可逐步校定以降低審核負擔。

## 6. 下一步建議

可用下列指令重新產生總目標稽核：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit-project-goal.ps1
```

後續建議：

1. 定期重試 2 筆已確認不可取得附件；若官方連結恢復，補抓並重新抽文字。
2. 審聽 `C:\Users\user\2026本土語\output\formal_full_goal_demo` 的音訊與影片。
3. 建立定期稽核流程：重新搜尋官方來源、比對 catalog、更新素材庫與生成包。
4. 逐步校定官方延伸題答案，降低教師審核負擔。
