param(
    [switch]$Download,
    [string]$OutputRoot = "data/official_materials"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SourceId = "cirn-local-language"
$PageUrl = "https://cirn.k12ea.gov.tw/web1107/List.aspx?fid=5551"
$RawDir = Join-Path $OutputRoot "raw/cirn/local-language"
$CatalogPath = Join-Path $OutputRoot "catalog.json"
New-Item -ItemType Directory -Force -Path $RawDir | Out-Null

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
        if ([string]::IsNullOrWhiteSpace($key)) {
            $key = "$($item.source_id):$($item.resource_id):$($item.title)"
        }
        $byUrl[$key] = $item
    }
    $json = @($byUrl.Values) | Sort-Object source_id, resource_id, title, attachment_label | ConvertTo-Json -Depth 8
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

$materials = @(
    @{
        id = "cirn-local-language-methods-2023"
        title = "12年國民基本教育本土語文教材教法"
        label = "電子檔 PDF"
        url = "https://cirn.k12ea.gov.tw/Upload/file/43774/121879.pdf"
        file = "12年國民基本教育本土語文教材教法_電子檔.pdf"
        date = "2023/12/18"
    },
    @{
        id = "cirn-local-language-methods-2026-v2"
        title = "12年國民基本教育本土語文教材教法（第二版）"
        label = "第二版 PDF"
        url = "https://cirn.k12ea.gov.tw/Upload/file/43752/131811.pdf"
        file = "12年國民基本教育本土語文教材教法_第二版.pdf"
        date = "2026/05/11"
    }
)

$records = @()
foreach ($material in $materials) {
    $filePath = Join-Path $RawDir $material.file
    if ($Download -and -not (Test-Path $filePath)) {
        Write-Host "下載 $($material.title)"
        Invoke-WebRequest -Uri $material.url -OutFile $filePath -UseBasicParsing -TimeoutSec 240
    }

    $records += [pscustomobject]@{
        source_id = $SourceId
        resource_id = $material.id
        title = $material.title
        page_url = $PageUrl
        attachment_label = $material.label
        attachment_url = $material.url
        official_date_text = $material.date
        downloaded_at = if ($Download -and (Test-Path $filePath)) { (Get-Date).ToString("yyyy-MM-dd") } else { $null }
        language = "本土語文（含臺灣台語／閩南語文）"
        learning_stage = "國民中小學"
        material_type = "教材教法"
        local_path = if ($Download -and (Test-Path $filePath)) { $filePath.Replace((Get-Location).Path + "\", "") } else { $null }
        license_note = "CIRN 國民中小學課程與教學資源整合平臺公開附件；使用時仍需遵守來源頁面與平台使用規範。"
    }
}

$catalog = @(Read-Catalog $CatalogPath)
Save-Catalog -Path $CatalogPath -Items @($catalog + $records)
Write-Host "完成：CIRN 已登錄 $($records.Count) 筆教材教法 PDF。"


