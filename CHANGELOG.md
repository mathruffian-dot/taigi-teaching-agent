# Changelog

本專案版本紀錄。日期為臺灣時間。

## v0.1.0（2026-07-05）— 首個公開版本

**核心能力**
- 教材生成管線：課程案例 JSON → 講義（Word）／考卷＋解答／簡報／離線互動網站／測驗題庫／教師審核報告
- 台語 TTS 定案：單詞用教育部官方音檔（concat 接音）、整句用意傳「媠聲」
  （`ithuan` provider：臺羅 KIP 輸入、限流 3 句/分鐘內建節流、失敗自動降級）
- 漢字→臺羅標音：意傳 `/tau`（上下文斷詞）＋萌典備援；內容自動檢核
  （華語用字、漢字↔臺羅音節一致，支援數字調與調符式）
- 教學影片管線（Hyperframe）：HTML 動畫 → Playwright 錄影 → ffmpeg 合成，
  旁白發音精準版（官方音＋意傳）、loudnorm 響度調和、錄影 lead 實測對齊
- 互動遊戲網站：`games` 一鍵生成離線遊戲包
  （拖拉配對／聽音配對／翻牌記持（防亂翻機制）／組句練習（意傳自動斷詞）），
  作答紀錄介面已預埋（localStorage 佇列，待接 GAS＋Google Sheet）
- TTS A/B 審聽機制：20 句測試組（入聲/濁聲母/鼻化/變調/華台陷阱）＋教師評分頁

**統一入口**
- `python -m taigi`：doctor／tts／piau／check／generate／games／abtest（皆支援 `--json`）
- `AGENTS.md`：給任何 AI Agent 的操作手冊

**授權與範圍**
- 程式碼 MIT；意傳／教育部／mms 等第三方資源依其原條款（見 README）
- repo 不含官方教材下載檔與生成成品（版權與體積考量），由使用者自行蒐集／生成
