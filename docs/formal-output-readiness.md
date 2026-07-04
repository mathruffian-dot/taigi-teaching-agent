# 正式輸出模式 Readiness 稽核

產生時間：2026-07-04T16:48:31
結果：必要項目通過

## 必要項目

- [通過] config_exists：正式輸出需能讀取專案 config.json。
- [通過] config_json_valid：config.json 必須是可解析的 JSON。
- [通過] output_base_dir_configured：正式影音與圖片輸出需設定 output.base_dir。
- [通過] output_base_dir_local：大型輸出應放在本機目錄，避免 Google Drive 同步大量影音與圖片。
- [通過] output_base_dir_writable：正式輸出目錄必須可寫入。
- [通過] tts_provider_not_dummy：正式上課版本不能只使用靜音 dummy TTS。
- [通過] voxcpm_python_exists：VoxCPM2 provider 需要可執行的語音專案 Python。
- [通過] voxcpm_script_exists：VoxCPM2 provider 需要 clone_batch.py 腳本。
- [通過] voxcpm_voice_configured：VoxCPM2 provider 需要指定三師爸台語聲音。
- [通過] voxcpm_python_runs：語音專案 Python 必須可執行。
- [通過] tts_sample_generation：VoxCPM2 必須直接產生真實非空音檔，不可降級為 dummy。
- [通過] piauim_provider_enabled：正式輸出應啟用漢字轉臺羅標音，降低 LLM 拼音錯誤。
- [通過] piauim_live_sample：標音服務需能替樣本文字產生臺羅。
- [通過] image_generation_endpoint_reachable：AI Horde 免費匿名生圖端點需可連線。
- [通過] video_tool_node：教學影片生成需要 node 可執行。
- [通過] video_tool_npm：教學影片生成需要 npm 可執行。
- [通過] video_tool_npx：教學影片生成需要 npx 可執行。
- [通過] video_tool_ffmpeg：教學影片生成需要 ffmpeg 可執行。
- [通過] video_tool_ffprobe：教學影片生成需要 ffprobe 可執行。
- [通過] official_assets_ready_for_generation：正式輸出需能引用已整理官方教材與生成素材。

## 提醒項目

- [通過] playwright_cached_in_temp：Playwright 應安裝於系統暫存目錄，避免 node_modules 進入 Google Drive。

## 使用方式

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit-formal-output-readiness.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\audit-formal-output-readiness.ps1 -LiveNetwork
powershell -ExecutionPolicy Bypass -File .\scripts\audit-formal-output-readiness.ps1 -AttemptTtsSample
powershell -ExecutionPolicy Bypass -File .\scripts\audit-formal-output-readiness.ps1 -LiveNetwork -AttemptTtsSample
```
