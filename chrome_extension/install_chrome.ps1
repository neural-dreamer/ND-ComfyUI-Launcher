$ErrorActionPreference = 'Stop'
try {
    $catalog = @(Get-Content -LiteralPath (Join-Path $PSScriptRoot 'browsers.json') -Raw -Encoding UTF8 | ConvertFrom-Json)
    function Find-Spec([string]$exe, [string]$label) {
        $leaf = [IO.Path]::GetFileName($exe).ToLowerInvariant()
        foreach ($spec in ($catalog | Sort-Object { -not [bool]$_.hint })) {
            if ($spec.exe -notcontains $leaf) { continue }
            if ($spec.hint -and (($exe + ' ' + $label) -notmatch $spec.hint)) { continue }
            return $spec
        }
        return $null
    }
    $found = [System.Collections.Generic.List[object]]::new()
    $seen = @{}
    function Add-Browser([string]$label, [string]$exe) {
        if (-not $exe -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) { return }
        $key = [IO.Path]::GetFullPath($exe).ToLowerInvariant()
        if ($seen.ContainsKey($key)) { return }
        $spec = Find-Spec $exe $label
        if (-not $spec) { return }
        $seen[$key] = $true
        if (-not $label) { $label = $spec.name }
        $found.Add([pscustomobject]@{Name=$label; Exe=$exe; Url=$spec.url})
    }
    foreach ($base in @('HKCU:\SOFTWARE\Clients\StartMenuInternet','HKLM:\SOFTWARE\Clients\StartMenuInternet','HKCU:\SOFTWARE\WOW6432Node\Clients\StartMenuInternet','HKLM:\SOFTWARE\WOW6432Node\Clients\StartMenuInternet')) {
        foreach ($key in @(Get-ChildItem -LiteralPath $base -ErrorAction SilentlyContinue)) {
            $label = $key.GetValue('')
            $cmdKey = Get-Item -LiteralPath (Join-Path $key.PSPath 'shell\open\command') -ErrorAction SilentlyContinue
            if (-not $cmdKey) { continue }
            $cmd = $cmdKey.GetValue('')
            if ($cmd -match '^\s*"([^"]+)"|^\s*(.+?\.exe)(?:\s|$)') {
                $exe = if ($Matches[1]) { $Matches[1] } else { $Matches[2] }
                Add-Browser $label $exe
            }
        }
    }
    foreach ($spec in $catalog) {
        foreach ($base in @($env:LOCALAPPDATA,$env:ProgramFiles,${env:ProgramFiles(x86)})) {
            if (-not $base) { continue }
            foreach ($relative in $spec.paths) { Add-Browser $spec.name (Join-Path $base $relative) }
        }
    }
    $choices = @($found | Sort-Object Name)
    Write-Host 'ND Launcher — установка расширения' -ForegroundColor Cyan
    for ($i=0; $i -lt $choices.Count; $i++) {
        Write-Host ("{0}. {1} — {2}" -f ($i+1),$choices[$i].Name,$choices[$i].Exe)
    }
    Write-Host '0. Указать путь к браузеру вручную'
    Write-Host 'Q. Отмена'
    $choice = Read-Host 'Выберите браузер'
    if ($choice -eq 'q') { exit 0 }
    $number = 0
    if (-not [int]::TryParse($choice, [ref]$number) -or $number -lt 0 -or $number -gt $choices.Count) {
        throw 'Неверный номер браузера. Запустите помощник повторно.'
    }
    if ($number -eq 0) {
        $exe = (Read-Host 'Полный путь к EXE браузера').Trim().Trim('"')
        $spec = Find-Spec $exe ''
        if (-not $spec -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            throw 'Поддерживаемый браузер по этому пути не найден.'
        }
        $selected = [pscustomobject]@{Name=$spec.name; Exe=$exe; Url=$spec.url}
    } else { $selected = $choices[$number-1] }
    $source = $PSScriptRoot
    $target = Join-Path $env:LOCALAPPDATA 'NDLauncher\ChromeExtension'
    if ([IO.Path]::GetFullPath($source).TrimEnd('\') -ne [IO.Path]::GetFullPath($target).TrimEnd('\')) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
    }
    Set-Clipboard -Value $target
    Start-Process -FilePath $selected.Exe -ArgumentList $selected.Url
    Write-Host ("Открыт браузер: " + $selected.Name) -ForegroundColor Cyan
    Write-Host '1. Включите режим разработчика.'
    Write-Host '2. Нажмите «Загрузить распакованное расширение» и вставьте путь (Ctrl+V):'
    Write-Host $target -ForegroundColor Cyan
    Write-Host '3. Вставьте ключ из настроек лаунчера в расширение и проверьте связь.'
    Write-Host 'При обновлении нажмите перезагрузку на карточке расширения.'
    Write-Host 'Устанавливайте расширение в нужном профиле браузера. Папку не удаляйте.'
} catch { Write-Host $_.Exception.Message -ForegroundColor Red }
Read-Host 'Нажмите Enter для закрытия'
