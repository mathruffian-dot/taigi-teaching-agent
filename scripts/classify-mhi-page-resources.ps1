param(
    [string]$OutputRoot = "data/official_materials",
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$CatalogPath = Join-Path $OutputRoot "catalog.json"
$SummaryPath = Join-Path $OutputRoot "analysis/mhi_page_resource_summary.json"
$SourceId = "moe-mhi-108-minnan"

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
    $json = $Items | Sort-Object source_id, resource_id, attachment_url -Unique | ConvertTo-Json -Depth 12
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

function Set-JsonProperty {
    param(
        [object]$Object,
        [string]$Name,
        [object]$Value
    )
    if ($Object.PSObject.Properties[$Name]) {
        $Object.$Name = $Value
    } else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Get-Text {
    param([string]$Html)
    return (($Html -replace '<script[\s\S]*?</script>', ' ') `
        -replace '<style[\s\S]*?</style>', ' ' `
        -replace '<[^>]+>', ' ' `
        -replace '&nbsp;', ' ' `
        -replace '&amp;', '&' `
        -replace '&#39;', "'" `
        -replace '&quot;', '"' `
        -replace '\s+', ' ').Trim()
}

function Get-BetweenLabel {
    param(
        [string]$Text,
        [string]$Label,
        [string[]]$NextLabels
    )
    $start = $Text.IndexOf($Label)
    if ($start -lt 0) { return $null }
    $from = $start + $Label.Length
    $end = $Text.Length
    foreach ($next in $NextLabels) {
        $idx = $Text.IndexOf($next, $from)
        if ($idx -ge 0 -and $idx -lt $end) { $end = $idx }
    }
    return $Text.Substring($from, $end - $from).Trim()
}

function Resolve-ResourceKind {
    param(
        [string[]]$MediaTypes,
        [string]$Title,
        [string]$Description
    )
    $mediaText = (($MediaTypes | Where-Object { $_ -ne "非影音" }) -join ",")
    $haystack = ($mediaText + " " + $Title + " " + $Description).ToLowerInvariant()
    if ($mediaText -match 'youtube|影音|影片|電視|動畫|教學影片|mv') { return "video" }
    if ($haystack -match 'wordwall|game|遊戲|互動遊戲|線上遊戲|app') { return "interactive" }
    if ($haystack -match '辭典|詞典|工具|檢索|網站查詢|網站學習|網站') { return "website_tool" }
    if ($haystack -match '聲音檔|有聲|廣播|兒歌|音檔|聽') { return "audio" }
    if ($haystack -match '文章|電子書|繪本|文學|新聞|書面|紙本|圖文') { return "text_reference" }
    if ($haystack -match 'youtube|影音|影片|電視|動畫|video|mv') { return "video" }
    return "learning_resource"
}

function Get-HostName {
    param([string]$Url)
    try { return ([uri]$Url).Host.ToLowerInvariant() } catch { return "" }
}

function Get-MhiPageMetadata {
    param(
        [string]$PageUrl,
        [string]$ResourceId
    )
    $html = (Invoke-WebRequest -Uri $PageUrl -UseBasicParsing -TimeoutSec 60).Content
    $text = Get-Text $html
    $nextLabels = @("語言：", "等級：", "資源內容：", "媒體：", "第", "內容簡介", "相關連結", "相關影片", "相關附件", "返回列表")

    $language = Get-BetweenLabel $text "語言：" $nextLabels
    $level = Get-BetweenLabel $text "等級：" $nextLabels
    $resourceContent = Get-BetweenLabel $text "資源內容：" $nextLabels
    $mediaText = Get-BetweenLabel $text "媒體：" $nextLabels
    $description = Get-BetweenLabel $text "內容簡介" @("相關連結", "相關影片", "相關附件", "返回列表")

    $provider = $null
    $dateMatch = [regex]::Match($text, '(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s[A-Z][a-z]{2}\s\d{1,2}\s\d{2}:\d{2}:\d{2}\sCST\s\d{4}')
    if ($dateMatch.Success) {
        $afterDate = $dateMatch.Index + $dateMatch.Length
        $languageIdx = $text.IndexOf("語言：", $afterDate)
        if ($languageIdx -gt $afterDate) {
            $provider = $text.Substring($afterDate, $languageIdx - $afterDate).Trim()
            if ([string]::IsNullOrWhiteSpace($provider)) { $provider = $null }
        }
    }

    $mediaTypes = @()
    if ($mediaText) {
        $mediaTypes = @($mediaText -split '[,，、]' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }

    $relatedLinks = @()
    $linkMatches = [regex]::Matches($html, '<a[^>]+href="(?<href>[^"]+)"[^>]*>(?<text>[\s\S]*?)</a>', 'IgnoreCase')
    foreach ($match in $linkMatches) {
        $href = $match.Groups["href"].Value
        $label = Get-Text $match.Groups["text"].Value
        if ([string]::IsNullOrWhiteSpace($href)) { continue }
        if ($href -match '^(#|javascript:|/eduCloud/learning-resource|/export/system|/assets)') { continue }
        if ($href.StartsWith("/")) { $href = "https://mhi.moe.edu.tw$href" }
        if ($href -notmatch '^https?://') { continue }
        $domainName = Get-HostName $href
        if ($domainName -match 'googletagmanager|accessibility\.moda') { continue }
        $relatedLinks += [pscustomobject]@{
            label = $label
            url = $href
            domain = $domainName
        }
    }

    $embedMatches = [regex]::Matches($html, 'data-src="(?<src>https://www\.youtube\.com/embed/[^"]+)"', 'IgnoreCase')
    foreach ($match in $embedMatches) {
        $src = $match.Groups["src"].Value
        if (-not ($relatedLinks | Where-Object { $_.url -eq $src })) {
            $relatedLinks += [pscustomobject]@{
                label = "YouTube embed"
                url = $src
                domain = "www.youtube.com"
            }
        }
    }

    [pscustomobject]@{
        resource_id = $ResourceId
        language = $language
        level = $level
        resource_content = $resourceContent
        media_types = $mediaTypes
        provider = $provider
        description = $description
        related_links = @($relatedLinks)
        resource_kind = Resolve-ResourceKind -MediaTypes $mediaTypes -Title "" -Description $description
    }
}

$catalog = @(Read-Catalog $CatalogPath)
$mhiRecords = @($catalog | Where-Object { $_.source_id -eq $SourceId })
$resources = @($mhiRecords | Group-Object resource_id | ForEach-Object { $_.Group[0] } | Sort-Object resource_id)
if ($Limit -gt 0) { $resources = @($resources | Select-Object -First $Limit) }

$metadataById = @{}
$count = 0
foreach ($resource in $resources) {
    $count += 1
    Write-Host "分類 $count/$($resources.Count) $($resource.resource_id) $($resource.title)"
    try {
        $metadata = Get-MhiPageMetadata -PageUrl $resource.page_url -ResourceId $resource.resource_id
        $metadata.resource_kind = Resolve-ResourceKind -MediaTypes $metadata.media_types -Title $resource.title -Description $metadata.description
        $metadataById[$resource.resource_id] = $metadata
    } catch {
        Write-Warning "分類失敗 $($resource.resource_id)：$($_.Exception.Message)"
    }
}

foreach ($item in $catalog) {
    if ($item.source_id -ne $SourceId) { continue }
    if (-not $metadataById.ContainsKey($item.resource_id)) { continue }
    $metadata = $metadataById[$item.resource_id]
    Set-JsonProperty $item "level" $metadata.level
    Set-JsonProperty $item "resource_content" $metadata.resource_content
    Set-JsonProperty $item "media_types" $metadata.media_types
    Set-JsonProperty $item "provider" $metadata.provider
    Set-JsonProperty $item "description" $metadata.description
    Set-JsonProperty $item "related_links" $metadata.related_links
    Set-JsonProperty $item "resource_kind" $metadata.resource_kind
    Set-JsonProperty $item "metadata_status" "classified"
    Set-JsonProperty $item "metadata_updated_at" (Get-Date).ToString("yyyy-MM-dd")
}

Save-Catalog -Path $CatalogPath -Items $catalog

$classified = @($catalog | Where-Object { $_.source_id -eq $SourceId -and $_.metadata_status -eq "classified" })
$summary = [pscustomobject]@{
    generated_at = (Get-Date).ToString("s")
    classified_records = $classified.Count
    classified_resources = @($classified | Select-Object -ExpandProperty resource_id -Unique).Count
    by_kind = @($classified | Group-Object resource_kind | Sort-Object Count -Descending | ForEach-Object {
        [pscustomobject]@{ name = $_.Name; count = $_.Count }
    })
    by_media = @($classified | ForEach-Object { $_.media_types } | Where-Object { $_ } | Group-Object | Sort-Object Count -Descending | ForEach-Object {
        [pscustomobject]@{ name = $_.Name; count = $_.Count }
    })
    top_domains = @($classified | ForEach-Object { $_.related_links } | Where-Object { $_ -and $_.domain } | Group-Object domain | Sort-Object Count -Descending | Select-Object -First 20 | ForEach-Object {
        [pscustomobject]@{ domain = $_.Name; count = $_.Count }
    })
}

$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $SummaryPath -Encoding UTF8
Write-Host "完成：已分類 $($summary.classified_resources) 個 MHI 資源頁，摘要位於 $SummaryPath"

