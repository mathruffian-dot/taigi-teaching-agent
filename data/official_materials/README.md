# 官方臺語教材資料倉庫

此資料夾用來保存臺灣中小學本土語（臺語／閩南語文）官方教材的來源、索引、下載檔案與分析結果。

## 資料夾結構

- `sources.json`：官方來源清單，包含網站名稱、主管機關、網址、可下載範圍與注意事項。
- `catalog.json`：已收錄教材索引。每一筆教材需保留來源網址、下載日期、語言、學習階段、教材類型、檔案路徑與授權／使用限制備註。
- `raw/`：原始下載檔。盡量保留官方檔名，必要時加上可讀前綴。
- `processed/`：抽文字、拆章節、詞彙表、課綱對應等處理後資料。
- `analysis/`：教材分析結果，例如主題分布、詞彙與句型分析、評量題型盤點。

## 資料健康檢查

重新蒐集、下載、分類或分析教材後，請執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit-official-repository.ps1
```

稽核結果會寫入：

- `analysis/repository_audit.json`
- `analysis/repository_audit.md`

稽核重點包含 catalog 必要欄位、本機檔案是否存在、PDF 是否已抽文字、來源統計是否一致，以及尚未下載或下載失敗的附件。

## 文字片段索引

PDF 抽文字後，可建立給 RAG 使用的官方教材片段索引：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-snippet-index.ps1
```

輸出位置：

- `analysis/official_material_snippets.json`
- `analysis/official_material_snippets.md`

## 結構化素材庫

片段索引完成後，可建立依教學用途分類的素材庫：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-material-bank.ps1
```

輸出位置：

- `analysis/official_material_bank.json`
- `analysis/official_material_bank.md`

素材庫會把官方教材片段分類成教案、學習單、評量、詞彙、句型／對話、課綱對應、文化素材與影音互動，作為自然語言生成教材時的 RAG 素材來源。

## 生成包

素材庫完成後，可建立給自然語言生成器使用的生成包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-generation-packs.ps1
```

輸出位置：

- `analysis/official_generation_packs.json`
- `analysis/official_generation_packs.md`

生成包會整理可轉用的選擇題、詞彙卡、投影片 bullet 與 4F 反思活動，並標記可支援考卷、講義、簡報、影片、互動網站與測驗的產出類型。

## 收錄原則

1. 優先收錄教育部、國教署、國教院或地方教育局處等官方來源。
2. 每個檔案都必須能追溯到原始頁面與下載網址。
3. 下載時記錄日期，避免未來官方網站更新後無法判斷版本。
4. 若來源頁面有授權、使用限制或僅供教學使用等說明，需寫入 `catalog.json`。
5. 圖片、音訊、影片等大型媒體先登錄索引；是否下載需依專案大型檔案規則處理。
