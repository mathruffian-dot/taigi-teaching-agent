# 《去菜市仔買物件》DESIGN（視覺與技術設計稿)

## 畫面規格
- 1920×1080、9 頁、總長約 170s（實際以旁白音檔量測為準，三處時長必一致）
- 字體：源石黑體 GenSekiGothic2TW（H 900／B 700／M 500，@font-face 指本地 .otf）
- 配色：paper `#FAF7EE`、ink `#1A1A1A`、teal `#0E7C7B`（主）、coral `#E36414`（臺羅專用色）、gold `#C8941F`（微強調）
- 內容填滿 ≥80% 畫布；與 SOIL 簡報同一套三層慣例：**漢字大（ink）／臺羅（coral, italic）／華語（灰 note 字級）**

## 字級階
- hero（金句/封面題）180–220
- title（頁題）120
- 詞卡漢字 140、臺羅 64、華語 36
- 對話漢字 72、臺羅 44、華語 30
- note 28

## 逐頁動畫設計
| # | 版面 | 動畫（單一 0.5–1.5s、階層延遲 0.5s、結束靜止 ≥1.5s）|
|---|------|------|
| 1 | 深 teal 底封面 | 漢字題→臺羅→對象列三層浮現；右上 coral 圓飾 |
| 2 | 三卡橫排 | 聽/講/買三卡 scale-in 依序爆出，底部金句 fade |
| 3 | 詞卡雙欄 | 卡片 flip-in；唸讀時該卡 coral 外框 pulse（對應🔊）|
| 4 | 詞卡雙欄 | 同 P3（結構一致性）|
| 5★ | 音節分解 | 「菜市仔」三音節方塊分離→合併滑接（變調示意箭頭）；「mi̍h」尾音 -h 紅色截斷條動畫 |
| 6 | 對話泡泡 | 泡泡逐句 slide-in，播該句音檔時泡泡高亮 |
| 7★ | 對話泡泡 | 同 P6；「偌濟錢」三字 coral 放大強調 |
| 8★ | 句型積木 | 三塊積木組合→「菜頭/一條」「蘋果/一粒」替換滑入替換 |
| 9 | 金句 hero | 金句浮現→四詞 chips→三步驟任務卡→「多謝逐家」收束 |

## 旁白音訊管線（發音精準版）
```
generate_narration.py（新版，混合供應器）
  ├─ 詞彙唸讀：TaigiTTS(provider=concat) → 教育部官方音檔（快取）
  ├─ 整句/對話：TaigiTTS(provider=ithuan) → 意傳媠聲（餵 SCRIPT.md 的臺羅 KIP，
  │   限流 3 句/分鐘已內建節流；全片約 16 句 ≈ 6 分鐘生成）
  ├─ 頁內組裝：句間 0.35s 靜音、🔊×2 詞彙間 0.6s，ffmpeg concat → page-NN.wav
  └─ get_durations.py 量實長 → 回填 index.html PAGES / record.cjs / render 時長
```

## 渲染管線（沿用 video/拍招呼/ 範本）
```
index.html（本頁面新寫，樣式沿用範本）
record.cjs（Playwright，NODE_PATH=%TEMP%\cvs-render\node_modules）
ffmpeg mux（-map 0:v:0 -map 1:a:0，避免無聲）
輸出：<output.base_dir>\video\菜市仔買物件_v1.mp4（本機，非雲端）
```

## 驗證關卡
1. 旁白全句 `taigi check` ＋ 意傳 /tau 重標比對 → 不一致人工裁決
2. 每頁 wav 生成後抽聽時長合理性（音節數×0.25s 上下）
3. 渲染後四頁抽圖目視（字體、臺羅符號、動畫結束態）
4. 教師審聽（正式發布前必經）
