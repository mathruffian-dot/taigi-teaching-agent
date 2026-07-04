# 台語 TTS A/B 審聽測試 SOP

> 目的：比較各語音引擎的**台語發音準確度**，決定教材旁白（整句合成）要用哪個引擎。
> 依專案規範，正式 TTS 音訊必須經本土語教師審聽——本測試就是審聽的標準化流程。

## 背景

現況問題：生成式模型（VoxCPM2 零樣本克隆、mms-tts-nan）**不懂台語音韻**，發音不準；
concat 接音（教育部官方音檔）發音最權威，但節奏偏慢、只適合單詞與跟讀。
候選新引擎（依成本排序）：

1. **意傳媠聲（ithuan，免費）**：專業台語 TTS，輸入臺羅 KIP（發音可控），已整合為 provider。
   ⚠️ 展示服務限流「1 IP 每分鐘 3 句」（程式已自動節流）；教材屬非即時、少量生成，夠用。
   正式量產或對外發布前應洽意傳科技（ithuan.tw）談授權，並於教材標示語音來源。
2. **BreezyVoice-Taigi（免費開源，中期）**：聯發科 2026/03 發表，自然度 MOS 5.0，
   權重尚未上架 HuggingFace，先用 Breeze AI 的 LINE 官方帳號試聽、持續追蹤。
3. **雅婷 TTS 台語聲（付費）**：品質成熟但費用高，暫緩；provider 已寫好備用。

## 測試句組

- 檔案：`data/evaluations/tts_ab_test_sentences.json`（20 句，已通過 content_checker 檢核）
- 詞彙來源：教師已驗證詞庫（`knowledge/dictionaries/vocabulary_db.json`）＋《拍招呼》影片詞彙表
- 臺羅為教育部辭典**本調**——變調由引擎處理，審聽重點之一就是聽**連讀變調**對不對
- 涵蓋的發音難點：

| 類別 | 句數 | 聽什麼 |
|------|------|--------|
| baseline_word 對照單詞 | 5 | 入聲尾 -p/-t/-k/-h、送氣聲母（concat 必為官方音，當基準）|
| greeting 招呼語句 | 4 | 短句語調、停頓（與《拍招呼》舊旁白可直接對照）|
| checked_stop 入聲密集句 | 2 | 塞音尾是否被吃掉 |
| voiced_initial 濁聲母 | 2 | b-/g-/j-（華語沒有，最容易露餡）|
| nasal 鼻化韻 | 2 | -nn 鼻化、音節性鼻音 |
| prosody 變調與韻律 | 2 | 整句變調流暢度、對句節奏 |
| mandarin_trap 華台陷阱 | 2 | 「先生」「物件」等同形詞勿照華語念 |
| proverb 金句 | 1 | 《拍招呼》P9 金句對照 |

## 執行方式

```powershell
# 全部引擎（沒 key／沒環境的引擎會自動跳過，不會混淆結果）
.\scripts\tts-ab-test.ps1

# 只跑指定引擎
.\scripts\tts-ab-test.ps1 -Engines "concat,yating:tai_female_1"

# 重新合成（預設會跳過已存在的音檔）
.\scripts\tts-ab-test.ps1 -Force
```

- 輸出位置：`<output.base_dir>\tts_ab_test\`（本機，非雲端硬碟）
- 音檔：`<引擎名>\tts_ab_0NN.wav`；報表：`manifest.json`
- ⚠️ **voxcpm 引擎有跨機器限制**：`clone_batch.py` 與「三師爸台語」參考音只在
  裝有 `C:\2026Antigravity_語音` 的那台電腦上（本機 `voxcpm2-voice-cloner` 專案
  只有 `clone.py` 與華語「三師爸」聲音）。VoxCPM2 那欄請在該機器跑同一支腳本，
  或把 wav 複製到本機的 `tts_ab_test\voxcpm\` 後重跑腳本刷新 review.html
- **審聽頁**：`review.html` — 用瀏覽器開啟，逐句試聽、下拉評分（1–5）、填備註；
  評分自動存在瀏覽器（localStorage），完成後按「匯出評分 JSON」交回。

## 意傳媠聲（ithuan provider）技術備忘

- 流程：漢字 →（已有臺羅則直接用）→ `hokbu.ithuan.tw/tau` 標音取 KIP
  → `hapsing.ithuan.tw/bangtsam?taibun=<KIP>` 取 MP3 → ffmpeg 轉 22050Hz 單聲道 WAV
- **輸入一定要臺羅 KIP**，餵漢字會被當羅馬字亂念（實測踩坑）
- 標點跟著 KIP 走（ASCII 標點），漢字＋全形標點會產生大量靜音
- 限流 500 會自動等 65 秒重試一次，仍失敗降級 concat
- 自架不可行：開源服務 repo（tai5-uan5_gian5-gi2_hok8-bu7）已於 2024 封存

## 雅婷 TTS 設定（若未來有預算，拿到 API key 後）

1. 到 [developer.yating.tw](https://developer.yating.tw/) 申請 key
2. 填入 `config.json` 的 `tts.api_key`（⚠️ config.json 不進 git，key 絕不 commit）
3. 重跑 `.\scripts\tts-ab-test.ps1` — 會自動補合成三個台語聲音（雅婷／家豪／意晴），
   review.html 重新產生後即可比對
4. 台語聲音僅支援 16K 取樣率，程式已預設 LINEAR16（WAV）@16K

## 評分基準（1 最差、5 最好）

| 面向 | 說明 |
|------|------|
| 發音準確度 | 聲母／韻母／入聲尾是否正確 |
| 聲調與變調 | 本調正確、連讀變調自然 |
| 自然度 | 節奏、停頓、像不像母語者 |
| 整體可用度 | 可否直接用於教材旁白 |

## 決策原則（審聽後）

- **單詞教學／跟讀**：維持 concat（官方音檔，發音零錯誤）
- **整句旁白**（影片、課文朗讀）：取審聽總分最高且「發音準確度 ≥ 4」的引擎；
  在零預算前提下，意傳媠聲是目前唯一的整句候選
- 任一句發音錯誤的引擎，該句改用 concat 或人工錄音替代
- BreezyVoice-Taigi 權重開源後，加入引擎清單重跑本測試（論文人評：自然度 MOS 5.0，
  但發音準確率僅 59.2%，務必實測）
- 若意傳審聽通過且需正式量產 → 聯絡意傳科技談授權（比雅婷可能更有彈性，且支持本土團隊）
