param(
    [int]$StartPage = 1,
    [int]$MaxPages = 1,
    [switch]$Download,
    [string]$OutputRoot = "data/official_materials"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$BaseUrl = "https://mhi.moe.edu.tw"
$ListUrl = "$BaseUrl/eduCloud/learning-resource/index.html?stage=&level=&media=&keyword=&lang=%2F003%2F&reloaded&page={0}"
$SourceId = "moe-mhi-108-minnan"

function Resolve-MhiUrl {
    param([string]$Href)
    if ($Href -match "^https?://") { return $Href }
    if ($Href.StartsWith("/")) { return "$BaseUrl$Href" }
    return "$BaseUrl/$Href"
}

function ConvertTo-SafeFileName {
    param([string]$Name)
    $safe = $Name -replace '[\\/:*?"<>|]', '_'
    $safe = $safe -replace '\s+', ' '
    $safe = $safe.Trim()
    if ($safe.Length -gt 80) { $safe = $safe.Substring(0, 80).Trim() }
    return $safe
}

function Get-Text {
    param([string]$Html)
    return (($Html -replace '<script[\s\S]*?</script>', ' ') `
        -replace '<style[\s\S]*?</style>', ' ' `
        -replace '<[^>]+>', ' ' `
        -replace '&nbsp;', ' ' `
        -replace '&amp;', '&' `
        -replace '\s+', ' ').Trim()
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
    $json = $Items | Sort-Object source_id, resource_id, attachment_url -Unique | ConvertTo-Json -Depth 8
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

function Write-CollectError {
    param(
        [string]$Path,
        [string]$Stage,
        [string]$ResourceId,
        [string]$Url,
        [string]$Message
    )
    $record = [pscustomobject]@{
        timestamp = (Get-Date).ToString("s")
        stage = $Stage
        resource_id = $ResourceId
        url = $Url
        message = $Message
    }
    Add-Content -Path $Path -Value ($record | ConvertTo-Json -Compress -Depth 4) -Encoding UTF8
}

function Get-ResourceLinksFromListPage {
    param([int]$Page)
    $url = $ListUrl -f $Page
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30
    $matches = [regex]::Matches($response.Content, '<a[^>]+href="(?<href>[^"]*TSMhiResource-\d+/[^"]*)"[^>]*>(?<text>[\s\S]*?)</a>', 'IgnoreCase')
    foreach ($match in $matches) {
        $href = $match.Groups["href"].Value
        $text = Get-Text $match.Groups["text"].Value
        if ($href -match 'TSMhiResource-(\d+)') {
            [pscustomobject]@{
                resource_id = "TSMhiResource-$($Matches[1])"
                title = $text -replace '^[A-Z][a-z]{2}\s[A-Z][a-z]{2}\s\d{1,2}\s\d{2}:\d{2}:\d{2}\sCST\s\d{4}\s+', ''
                page_url = Resolve-MhiUrl $href
            }
        }
    }
}

function Get-ResourceRecord {
    param([pscustomobject]$Link)

    $response = Invoke-WebRequest -Uri $Link.page_url -UseBasicParsing -TimeoutSec 30
    $html = $response.Content
    $text = Get-Text $html

    $title = $Link.title
    $titleMatch = [regex]::Match($html, '<title>(?<title>[\s\S]*?)\s+-\s+教育雲資源</title>', 'IgnoreCase')
    if ($titleMatch.Success) { $title = Get-Text $titleMatch.Groups["title"].Value }

    $stage = $null
    $stageMatch = [regex]::Match($text, '第[一二三四五]學習階段')
    if ($stageMatch.Success) { $stage = $stageMatch.Value }

    $date = $null
    $dateMatch = [regex]::Match($text, '(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s[A-Z][a-z]{2}\s\d{1,2}\s\d{2}:\d{2}:\d{2}\sCST\s\d{4}')
    if ($dateMatch.Success) { $date = $dateMatch.Value }

    $attachments = @()
    $attachMatches = [regex]::Matches($html, '<li>\s*(?<label>[^<]+?)(?:<!--[\s\S]*?-->|[\s\r\n])*<a[^>]+href="(?<href>[^"]+\.pdf)"[^>]*>[\s\S]*?</a>', 'IgnoreCase')
    if ($attachMatches.Count -eq 0) {
        $attachMatches = [regex]::Matches($html, '<a[^>]+href="(?<href>[^"]+\.pdf)"[^>]*>(?<label>[\s\S]*?)</a>', 'IgnoreCase')
    }

    foreach ($match in $attachMatches) {
        $href = $match.Groups["href"].Value
        $label = Get-Text $match.Groups["label"].Value
        if ([string]::IsNullOrWhiteSpace($label)) { $label = "PDF" }
        $attachments += [pscustomobject]@{
            label = $label
            url = Resolve-MhiUrl $href
        }
    }

    [pscustomobject]@{
        source_id = $SourceId
        resource_id = $Link.resource_id
        title = $title
        page_url = $Link.page_url
        official_date_text = $date
        language = "臺灣台語／閩南語文"
        learning_stage = $stage
        material_type = if ($title -match '教案|學習單') { "教案／學習單" } else { "學習資源" }
        attachments = $attachments
    }
}

$catalogPath = Join-Path $OutputRoot "catalog.json"
$errorLogPath = Join-Path $OutputRoot "analysis/mhi_collect_errors.jsonl"
$rawRoot = Join-Path $OutputRoot "raw/mhi/108-minnan"
New-Item -ItemType Directory -Force -Path $rawRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $errorLogPath) | Out-Null

$existing = @(Read-Catalog $catalogPath)
$newRecords = @()

for ($page = $StartPage; $page -le $MaxPages; $page++) {
    Write-Host "讀取第 $page 頁..."
    try {
        $links = @(Get-ResourceLinksFromListPage -Page $page)
    } catch {
        Write-Warning "第 $page 頁讀取失敗：$($_.Exception.Message)"
        Write-CollectError -Path $errorLogPath -Stage "list_page" -ResourceId "" -Url ($ListUrl -f $page) -Message $_.Exception.Message
        continue
    }

    foreach ($link in $links) {
        Write-Host "  處理 $($link.resource_id) $($link.title)"
        try {
            $resource = Get-ResourceRecord -Link $link
        } catch {
            Write-Warning "資源頁讀取失敗 $($link.resource_id)：$($_.Exception.Message)"
            Write-CollectError -Path $errorLogPath -Stage "resource_page" -ResourceId $link.resource_id -Url $link.page_url -Message $_.Exception.Message
            continue
        }

        $resourceDir = Join-Path $rawRoot $resource.resource_id
        New-Item -ItemType Directory -Force -Path $resourceDir | Out-Null

        if ($resource.attachments.Count -eq 0) {
            $newRecords += [pscustomobject]@{
                source_id = $resource.source_id
                resource_id = $resource.resource_id
                title = $resource.title
                page_url = $resource.page_url
                attachment_label = "資源頁（未偵測到 PDF 附件）"
                attachment_url = $resource.page_url
                official_date_text = $resource.official_date_text
                downloaded_at = $null
                language = $resource.language
                learning_stage = $resource.learning_stage
                material_type = $resource.material_type
                local_path = $null
                license_note = "教育部本土語言資源網公開資源頁；未偵測到可直接下載的 PDF 附件，後續需人工或專用腳本判斷影音、網站、外部連結等素材。"
            }
            continue
        }

        $attachmentIndex = 0
        foreach ($attachment in $resource.attachments) {
            $attachmentIndex += 1
            $extension = [System.IO.Path]::GetExtension(([uri]$attachment.url).AbsolutePath)
            if ([string]::IsNullOrWhiteSpace($extension)) { $extension = ".pdf" }
            $safeTitle = ConvertTo-SafeFileName $resource.title
            $safeLabel = ConvertTo-SafeFileName $attachment.label
            $fileName = "{0:D2}_{1}_{2}{3}" -f $attachmentIndex, $safeLabel, $safeTitle, $extension
            $filePath = Join-Path $resourceDir $fileName

            $downloadedPath = $null
            if ($Download -and -not (Test-Path $filePath)) {
                try {
                    Invoke-WebRequest -Uri $attachment.url -OutFile $filePath -UseBasicParsing -TimeoutSec 120
                    $downloadedPath = $filePath.Replace((Get-Location).Path + "\", "")
                } catch {
                    Write-Warning "附件下載失敗 $($resource.resource_id) $($attachment.url)：$($_.Exception.Message)"
                    Write-CollectError -Path $errorLogPath -Stage "attachment_download" -ResourceId $resource.resource_id -Url $attachment.url -Message $_.Exception.Message
                }
            } elseif ($Download -and (Test-Path $filePath)) {
                $downloadedPath = $filePath.Replace((Get-Location).Path + "\", "")
            }

            $newRecords += [pscustomobject]@{
                source_id = $resource.source_id
                resource_id = $resource.resource_id
                title = $resource.title
                page_url = $resource.page_url
                attachment_label = $attachment.label
                attachment_url = $attachment.url
                official_date_text = $resource.official_date_text
                downloaded_at = if ($Download) { (Get-Date).ToString("yyyy-MM-dd") } else { $null }
                language = $resource.language
                learning_stage = $resource.learning_stage
                material_type = $resource.material_type
                local_path = $downloadedPath
                license_note = "教育部本土語言資源網公開資源；使用時仍需遵守來源頁面與教育部網站使用規範。"
            }
        }
    }

    Save-Catalog -Path $catalogPath -Items @($existing + $newRecords)
    Write-Host "  已保存至第 $page 頁，暫存新增/更新 $($newRecords.Count) 筆。"
}

$merged = @($existing + $newRecords)
Save-Catalog -Path $catalogPath -Items $merged
Write-Host "完成：新增或更新 $($newRecords.Count) 筆附件索引，catalog 位於 $catalogPath"



