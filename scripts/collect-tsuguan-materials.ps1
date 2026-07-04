param(
    [switch]$Download,
    [string]$OutputRoot = "data/official_materials"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SourceId = "moe-language-tsuguan"
$RawDir = Join-Path $OutputRoot "raw/moe-language/tsuguan"
$CatalogPath = Join-Path $OutputRoot "catalog.json"
New-Item -ItemType Directory -Force -Path $RawDir | Out-Null

function ConvertTo-SafeFileName {
    param([string]$Name)
    $safe = $Name -replace '[\\/:*?"<>|]', '_'
    $safe = $safe -replace '\s+', ' '
    return $safe.Trim()
}

function Read-Catalog {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @() }
    $raw = Get-Content -Raw -Encoding UTF8 $Path
    if ([string]::IsNullOrWhiteSpace($raw)) { return @() }
    $items = $raw | ConvertFrom-Json
    if ($null -eq $items) { return @() }
    if ($items -is [array]) { return $items }
    return @($items)
}

function Save-Catalog {
    param(
        [string]$Path,
        [object[]]$Items
    )
    $byUrl = [ordered]@{}
    foreach ($item in $Items) {
        $key = "$($item.source_id):$($item.resource_id):$($item.attachment_url)"
        if ([string]::IsNullOrWhiteSpace($key)) { $key = "$($item.source_id):$($item.resource_id):$($item.title)" }
        $byUrl[$key] = $item
    }
    $json = @($byUrl.Values) | Sort-Object source_id, resource_id, title, attachment_label | ConvertTo-Json -Depth 8
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

$materials = @(
    @{ id = "tsuguan-guide"; title = "《咱來學臺灣台語》入口與改版說明"; version = "113年8月改版入口"; kind = "入口說明"; url = "https://language.moe.gov.tw/files/people_files/tsuguan-book.pdf"; file = "00_咱來學臺灣台語_入口與改版說明.pdf" },
    @{ id = "tsuguan-web-01"; title = "《學拼音有撇步》"; version = "網路學習版（附音檔連結）"; kind = "拼音"; url = "https://language.moe.gov.tw/upload/download/jts/01%E6%8B%BC%E9%9F%B3.pdf"; file = "web_01_學拼音有撇步.pdf" },
    @{ id = "tsuguan-web-02a"; title = "《學語詞真輕鬆 01》"; version = "網路學習版（附音檔連結）"; kind = "語詞"; url = "https://language.moe.gov.tw/upload/download/jts/02%E8%AA%9E%E8%A9%9E1.pdf"; file = "web_02a_學語詞真輕鬆01.pdf" },
    @{ id = "tsuguan-web-02b"; title = "《學語詞真輕鬆 02》"; version = "網路學習版（附音檔連結）"; kind = "語詞"; url = "https://language.moe.gov.tw/upload/download/jts/02%E8%AA%9E%E8%A9%9E2.pdf"; file = "web_02b_學語詞真輕鬆02.pdf" },
    @{ id = "tsuguan-web-03a"; title = "《讀語句上簡單 01》"; version = "網路學習版（附音檔連結）"; kind = "語句"; url = "https://language.moe.gov.tw/upload/download/jts/03%E8%AA%9E%E5%8F%A51.pdf"; file = "web_03a_讀語句上簡單01.pdf" },
    @{ id = "tsuguan-web-03b"; title = "《讀語句上簡單 02》"; version = "網路學習版（附音檔連結）"; kind = "語句"; url = "https://language.moe.gov.tw/upload/download/jts/03%E8%AA%9E%E5%8F%A52.pdf"; file = "web_03b_讀語句上簡單02.pdf" },
    @{ id = "tsuguan-web-04a"; title = "《讀文章蓋趣味 01》"; version = "網路學習版（附音檔連結）"; kind = "文章"; url = "https://language.moe.gov.tw/upload/download/jts/04%E6%96%87%E7%AB%A01.pdf"; file = "web_04a_讀文章蓋趣味01.pdf" },
    @{ id = "tsuguan-web-04b"; title = "《讀文章蓋趣味 02》"; version = "網路學習版（附音檔連結）"; kind = "文章"; url = "https://language.moe.gov.tw/upload/download/jts/04%E6%96%87%E7%AB%A02.pdf"; file = "web_04b_讀文章蓋趣味02.pdf" },
    @{ id = "tsuguan-print-01"; title = "《學拼音有撇步》"; version = "書面製作版（無音檔）"; kind = "拼音"; url = "https://language.moe.gov.tw/upload/download/jts/01%E6%8B%BC%E9%9F%B3-book.pdf"; file = "print_01_學拼音有撇步.pdf" },
    @{ id = "tsuguan-print-02a"; title = "《學語詞真輕鬆 01》"; version = "書面製作版（無音檔）"; kind = "語詞"; url = "https://language.moe.gov.tw/upload/download/jts/02%E8%AA%9E%E8%A9%9E1-book.pdf"; file = "print_02a_學語詞真輕鬆01.pdf" },
    @{ id = "tsuguan-print-02b"; title = "《學語詞真輕鬆 02》"; version = "書面製作版（無音檔）"; kind = "語詞"; url = "https://language.moe.gov.tw/upload/download/jts/02%E8%AA%9E%E8%A9%9E2-book.pdf"; file = "print_02b_學語詞真輕鬆02.pdf" },
    @{ id = "tsuguan-print-03a"; title = "《讀語句上簡單 01》"; version = "書面製作版（無音檔）"; kind = "語句"; url = "https://language.moe.gov.tw/upload/download/jts/03語句1-book.pdf"; file = "print_03a_讀語句上簡單01.pdf" },
    @{ id = "tsuguan-print-03b"; title = "《讀語句上簡單 02》"; version = "書面製作版（無音檔）"; kind = "語句"; url = "https://language.moe.gov.tw/upload/download/jts/03%E8%AA%9E%E5%8F%A52-book.pdf"; file = "print_03b_讀語句上簡單02.pdf" },
    @{ id = "tsuguan-print-04a"; title = "《讀文章蓋趣味 01》"; version = "書面製作版（無音檔）"; kind = "文章"; url = "https://language.moe.gov.tw/upload/download/jts/04%E6%96%87%E7%AB%A01-book.pdf"; file = "print_04a_讀文章蓋趣味01.pdf" },
    @{ id = "tsuguan-print-04b"; title = "《讀文章蓋趣味 02》"; version = "書面製作版（無音檔）"; kind = "文章"; url = "https://language.moe.gov.tw/upload/download/jts/04%E6%96%87%E7%AB%A02-book.pdf"; file = "print_04b_讀文章蓋趣味02.pdf" }
)

$records = @()
foreach ($material in $materials) {
    $filePath = Join-Path $RawDir $material.file
    if ($Download -and -not (Test-Path $filePath)) {
        Write-Host "下載 $($material.title) $($material.version)"
        Invoke-WebRequest -Uri $material.url -OutFile $filePath -UseBasicParsing -TimeoutSec 120
    }

    $records += [pscustomobject]@{
        source_id = $SourceId
        resource_id = $material.id
        title = $material.title
        page_url = "https://language.moe.gov.tw/files/people_files/tsuguan-book.pdf"
        attachment_label = $material.version
        attachment_url = $material.url
        official_date_text = "113年8月改版"
        downloaded_at = if ($Download) { (Get-Date).ToString("yyyy-MM-dd") } else { $null }
        language = "臺灣台語"
        learning_stage = "不分學習階段"
        material_type = $material.kind
        local_path = if ($Download) { $filePath.Replace((Get-Location).Path + "\", "") } else { $null }
        license_note = "教育部語文成果入口網公開下載教材；入口 PDF 記載本系列共 7 冊，113 年 8 月改版。"
    }
}

$deferred = @(
    [pscustomobject]@{
        source_id = $SourceId
        resource_id = "tsuguan-web-total-zip"
        title = "《咱來學臺灣台語》7冊一次下載區"
        page_url = "https://language.moe.gov.tw/files/people_files/tsuguan-book.pdf"
        attachment_label = "網路學習版全數下載 ZIP"
        attachment_url = "https://language.moe.gov.tw/upload/download/jts/total.zip"
        official_date_text = "113年8月改版"
        downloaded_at = $null
        language = "臺灣台語"
        learning_stage = "不分學習階段"
        material_type = "大型壓縮檔"
        local_path = $null
        license_note = "大型 ZIP 先建索引，避免直接放入雲端硬碟；需要完整音檔包時再依大型檔案規則下載到本機輸出目錄。"
    },
    [pscustomobject]@{
        source_id = $SourceId
        resource_id = "tsuguan-print-total-zip"
        title = "《咱來學臺灣台語》書面製作版全數下載"
        page_url = "https://language.moe.gov.tw/files/people_files/tsuguan-book.pdf"
        attachment_label = "書面製作版全數下載 ZIP"
        attachment_url = "https://language.moe.gov.tw/upload/download/jts/total-book.zip"
        official_date_text = "113年8月改版"
        downloaded_at = $null
        language = "臺灣台語"
        learning_stage = "不分學習階段"
        material_type = "大型壓縮檔"
        local_path = $null
        license_note = "HEAD 檢查約 145MB，先建索引，避免直接放入雲端硬碟。"
    }
)

$catalog = @(Read-Catalog $CatalogPath)
Save-Catalog -Path $CatalogPath -Items @($catalog + $records + $deferred)
Write-Host "完成：咱來學臺灣台語已登錄 $($records.Count) 個 PDF 與 $($deferred.Count) 個大型 ZIP 索引。"



