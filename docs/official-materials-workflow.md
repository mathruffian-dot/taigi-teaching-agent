# 官方教材蒐集與分析流程

本流程用來推進專案第一階段目標：搜尋、下載、分類與分析臺灣中小學本土語（臺語／閩南語文）官方教材。

## 已確認官方來源

1. 教育部本土語言資源網：108課綱本土語言數位教材專區（閩南語文）
   - 來源網址：<https://mhi.moe.edu.tw/eduCloud/learning-resource/?keyword=&lang=%2F003%2F&level=&media=&stage=>
   - 目前頁面顯示閩南語文共 835 筆資料。
   - 本專案已索引 835 筆資源頁，建立 849 筆 MHI catalog 記錄，下載 33 個 PDF。
   - 835 個 MHI 資源頁已完成分類，包含影音、網站工具、互動資源、聲音與文字參考資源。
2. 教育部語文成果入口網：「咱來學臺灣台語」
   - 入口 PDF：<https://language.moe.gov.tw/files/people_files/tsuguan-book.pdf>
   - 入口 PDF 記載本系列共 7 冊，包含網路學習版與書面製作版，113 年 8 月改版。
   - 本專案已下載入口 PDF、7 冊網路學習版 PDF、7 冊書面製作版 PDF。
3. CIRN 國民中小學課程與教學資源整合平臺
   - 來源網址：<https://cirn.k12ea.gov.tw/>
   - 已下載並索引 `12年國民基本教育本土語文教材教法` 與 `12年國民基本教育本土語文教材教法（第二版）` 兩份官方 PDF。

## 目前資料位置

- 官方來源清單：`data/official_materials/sources.json`
- 教材索引：`data/official_materials/catalog.json`
- 原始下載檔：`data/official_materials/raw/`
- PDF 抽文字：`data/official_materials/processed/pdf_text/`
- 初步分析：`data/official_materials/analysis/summary.md`
- 官方教材文字片段索引：`data/official_materials/analysis/official_material_snippets.md`
- 官方教材結構化素材庫：`data/official_materials/analysis/official_material_bank.md`
- 官方教材生成包：`data/official_materials/analysis/official_generation_packs.md`
- MHI 頁面資源分類摘要：`data/official_materials/analysis/mhi_page_resource_summary.json`
- 全 catalog 結構分析：`data/official_materials/analysis/official_catalog_analysis.md`
- 資料倉庫稽核：`data/official_materials/analysis/repository_audit.md`
- 已確認不可取得附件：`data/official_materials/analysis/unavailable_attachments.md`

## 繼續下載教育部本土語言資源網

先下載一頁驗證：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\collect-mhi-taigi-materials.ps1 -StartPage 1 -MaxPages 1 -Download
```

目前 84 頁已全量跑過；若要重新跑全部頁面：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\collect-mhi-taigi-materials.ps1 -StartPage 1 -MaxPages 84 -Download
```

若中途失敗，可從指定頁續跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\collect-mhi-taigi-materials.ps1 -StartPage 42 -MaxPages 84 -Download
```

## 重新下載「咱來學臺灣台語」

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\collect-tsuguan-materials.ps1 -Download
```

注意：`total.zip` 與 `total-book.zip` 已在 catalog 建索引，但不直接下載到雲端硬碟。若需要完整大型壓縮檔，請依專案大型檔案規則改存本機輸出目錄。

## 重新下載 CIRN 教材教法 PDF

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\collect-cirn-materials.ps1 -Download
```

## 重新分析已下載 PDF

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\analyze-official-materials.ps1
```

分析會產生：

- `data/official_materials/processed/pdf_text/`：每個 PDF 一份抽文字檔。
- `data/official_materials/analysis/pdf_text_index.json`：每個 PDF 的頁數、字數、關鍵詞統計與文字檔位置。
- `data/official_materials/analysis/summary.md`：整體摘要。

## 建立官方教材文字片段索引

抽文字完成後，請建立 RAG 可直接檢索的片段索引：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-snippet-index.ps1
```

片段索引會產生：

- `data/official_materials/analysis/official_material_snippets.json`：給程式檢索的官方教材內文片段。
- `data/official_materials/analysis/official_material_snippets.md`：給教師與接手 Agent 閱讀的片段索引摘要。

目前片段索引已由 50 份 PDF 產生 1010 個文字片段，後續自然語言生成會優先使用這些片段作為官方教材參考。

## 建立官方教材結構化素材庫

片段索引完成後，請建立依用途分類的素材庫：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-material-bank.ps1
```

素材庫會產生：

- `data/official_materials/analysis/official_material_bank.json`：給 RAG 檢索的結構化素材庫。
- `data/official_materials/analysis/official_material_bank.md`：給教師與接手 Agent 閱讀的素材庫摘要。

素材庫會把官方教材片段標記為教案、學習單、評量、詞彙、句型／對話、課綱對應、文化素材與影音互動，並抽出可辨識的課綱代碼與臺羅線索。

## 建立官方教材生成包

素材庫完成後，請建立可直接支援生成器的資產包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-official-generation-packs.ps1
```

生成包會產生：

- `data/official_materials/analysis/official_generation_packs.json`：給自然語言生成器檢索的可轉用資產。
- `data/official_materials/analysis/official_generation_packs.md`：給教師與接手 Agent 閱讀的摘要。

目前生成包會抽出：

- `multiple_choice`：可轉成考卷、測驗與互動網站的選擇題素材；若官方檔案未提供答案，會標記 `teacher_answer_required`。
- `vocabulary_card`：可轉成詞彙卡、投影片與互動練習的語詞素材。
- `reflection_4f`：可轉成學習單或互動反思活動。
- `slide_seed`：可轉成簡報或影片分鏡的 bullet 素材。

自然語言產出流程已會把生成包寫入 `lesson_structure.json`，並在學生講義、考卷、簡報與互動網站中加入官方延伸素材區塊。未確認答案的官方延伸題只作為教師確認後使用的素材，不會接入自動判分。

## 重新分類 MHI 頁面資源

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\classify-mhi-page-resources.ps1
```

分類會補齊 `catalog.json` 中 MHI 資源頁的 `level`、`resource_content`、`media_types`、`provider`、`description`、`related_links`、`resource_kind`、`metadata_status` 與 `metadata_updated_at`，並更新 `data/official_materials/analysis/mhi_page_resource_summary.json`。

## 重新分析官方教材 Catalog

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\analyze-official-catalog.ps1
```

分析會產生：

- `data/official_materials/analysis/official_catalog_analysis.json`：給程式讀取的結構化分析。
- `data/official_materials/analysis/official_catalog_analysis.md`：給教師與接手 Agent 閱讀的摘要。

## 稽核官方教材資料倉庫

每次重新蒐集、下載、分類或抽文字後，請執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\audit-official-repository.ps1
```

稽核會檢查：

- `catalog.json` 必要欄位是否齊全。
- catalog 指到的本機檔案是否存在、是否為 0 位元組。
- 本機 PDF 是否都已完成抽文字。
- `sources.json` 中的 catalog 與 PDF 數量是否和實際資料一致。
- 有附件網址但尚未下載的項目與歷次下載錯誤。

稽核結果會產生：

- `data/official_materials/analysis/repository_audit.json`
- `data/official_materials/analysis/repository_audit.md`

## 下一步

1. 定期重試 `data/official_materials/analysis/unavailable_attachments.md` 中的 2 筆已確認不可取得附件；若官方連結恢復，補抓 PDF、抽文字並重建索引。
2. 繼續爬梳 CIRN 其他本土語文頁面與附件。
3. 持續改善 `official_generation_packs.json` 的抽取規則，尤其是選擇題答案、詞彙表欄位與互動活動格式。
4. 擴充生成器的分格式品質，例如考卷版面、簡報視覺模板、影片分鏡、互動測驗題型與官方素材引用格式。

## 目前全量索引狀態

- `catalog.json`：868 筆。
- MHI 閩南語文：835 個不重複資源頁、849 筆 catalog 記錄。
- MHI 頁面分類：835 個資源頁已分類；依主要類型分為影片 593、網站工具 133、互動 43、聲音 34、其他學習資源 27、文字參考 19。
- 咱來學臺灣台語：17 筆 catalog 記錄。
- CIRN：2 筆 catalog 記錄。
- 本機 PDF：50 個，皆已確認檔案存在。
- PDF 分析：50 個 PDF、1,386 頁、抽取文字 529,597 字元。
- 官方教材文字片段索引：50 份 PDF 產生 1010 個片段，供 RAG 與自然語言產出引用。
- 官方教材結構化素材庫：1010 個素材項目，已分類為教案、學習單、評量、詞彙、句型／對話、課綱對應等用途。
- 官方教材生成包：842 個可生成資產，包含 slide seed、詞彙卡、選擇題與 4F 反思活動。
- Catalog 結構分析：已產生 `official_catalog_analysis.json` 與 `official_catalog_analysis.md`。
- 資料倉庫稽核：本機 PDF 抽文字覆蓋 50 / 50，缺必要欄位 0，缺本機檔案 0，零位元組檔案 0。
- 未下載／未抽文字項目：818 筆，多數已保留為頁面索引與外部連結，另有大型壓縮檔僅建索引。
- 尚未下載附件：0 筆。
- 已確認不可取得附件：2 筆，皆列於 `repository_audit.md`、`unavailable_attachments.md` 與 `mhi_collect_errors.jsonl`。
- 下載錯誤紀錄：`data/official_materials/analysis/mhi_collect_errors.jsonl`。
