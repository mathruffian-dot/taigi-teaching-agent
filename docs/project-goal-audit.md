# 專案總目標稽核

產生時間：2026-07-04T16:48:44
結果：通過

## 檢查項目

- [通過] official_repository_core_integrity：官方教材 catalog、本機檔案、PDF 抽文字與來源數量一致性檢查。
- [通過] official_pdf_text_coverage：本機 PDF 必須全部完成抽文字。
- [通過] official_analysis_artifacts：官方教材片段索引、素材庫與生成包必須存在。
- [通過] natural_language_output_validation：自然語言教材產出資料夾必須通過既有驗證器。
- [通過] natural_language_requested_all_core_outputs：煙霧產出需求必須同時包含考卷、簡報、影片、互動網站與測驗。
- [通過] natural_language_core_files_exist：五類核心產物檔案必須存在且非空。
- [通過] natural_language_video_success：影片必須實際嘗試並成功產生。
- [通過] formal_output_readiness：正式輸出模式必須通過必要項目：真實 TTS、標音、生圖端點、影片工具鏈與本機輸出目錄。
- [通過] formal_output_live_evidence：正式輸出 readiness 必須包含外部連線與真實 TTS 樣本證據。
- [通過] formal_generation_output_validation：正式上課包必須通過產出資料夾驗證器。
- [通過] formal_generation_not_no_media：正式上課包不可使用 NoMedia 快速模式。
- [通過] formal_generation_video_success：正式上課包必須實際產生影片。
- [通過] formal_generation_audio_files：正式上課包必須包含 TTS 音檔。
- [通過] formal_generation_image_files：正式上課包必須包含詞彙圖片；外部生圖失敗時可用本機 fallback 圖。

## 官方教材摘要

- Catalog：868
- 本機 PDF：50
- PDF 抽文字覆蓋：50 / 50
- 有附件但尚未下載：0
- 已確認附件不可取得：2

## 自然語言產出摘要

- 輸出資料夾：`output\smoke_full_goal_all_outputs`
- 產出類型：exam, slides, video, interactive, quiz
- 驗證結果：通過
- 測驗題庫：3 題自動計分，3 題官方延伸
- 影片生成：成功

## 正式輸出 Readiness 摘要

- 必要項目：通過
- 外部連線樣本：已執行
- 真實 TTS 樣本：已執行

## 正式上課包摘要

- 輸出資料夾：`C:\Users\user\2026本土語\output\formal_full_goal_demo`
- 驗證結果：通過
- 快速模式：False
- TTS 音檔數：7
- 圖片數：4
- 影片生成：成功
