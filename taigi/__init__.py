# taigi — 臺語教材 AI Agent 統一指令入口套件
#
# 用法（於專案根目錄執行）：
#   python -m taigi --help
#
# 設計目的：讓任何 Agent（Claude Code / Codex / OpenCode…）或使用者不必閱讀
# src/ 原始碼，就能以一致的指令使用本專案的標音、語音合成、內容檢核與教材生成。
# 各子指令皆為現有模組的薄封裝，正確用法（如意傳 TTS 須餵臺羅、限流節流）
# 已內建於底層模組，不依賴呼叫端自覺。
__version__ = "0.1.0"
