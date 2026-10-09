<#
  DZ_NT_FixDuplicates.ps1 — повторы системных скриптов NinjaTrader после обновления, v1.1 (2026-09-30)

  ПРИЧИНА ОШИБОК CS0101 / CS0111 / CS0229 / CS0121: один и тот же класс объявлен в bin\Custom
  дважды — новая сборка положила свои системные файлы (@…cs), а старые копии остались.
  NinjaTrader компилирует ВСЁ в bin\Custom и подпапках.

  ЧТО ДЕЛАЕТ. Ищет повторы по ОБЪЯВЛЕННЫМ КЛАССАМ (namespace + class), а не по имени файла:
  копия «@X - Копия.cs» тоже найдётся. Частичные классы (partial) не считаются повтором —
  так устроены обёртки индикаторов. Для каждого повтора оставляет САМЫЙ НОВЫЙ файл,
  остальные ПЕРЕНОСИТ за пределы bin\Custom с сохранением подпапок. Ничего не удаляет.

  ЗАПУСК (NinjaTrader закрыт):
    powershell -ExecutionPolicy Bypass -File DZ_NT_FixDuplicates.ps1            — только план
    powershell -ExecutionPolicy Bypass -File DZ_NT_FixDuplicates.ps1 -Apply     — перенос
#>
param([switch]$Apply)

$custom = Join-Path $env:USERPROFILE "Documents\NinjaTrader 8\bin\Custom"
$stamp  = Get-Date -Format "yyyyMMdd_HHmm"
$quar   = Join-Path $env:USERPROFILE "Documents\NT8_Duplicates_$stamp"

if (-not (Test-Path $custom)) { Write-Host "Нет папки $custom" -ForegroundColor Red; exit 1 }
if ($Apply -and (Get-Process -Name "NinjaTrader" -ErrorAction SilentlyContinue)) {
    Write-Host "NinjaTrader запущен. Закройте его и повторите: файлы открытой сборки переносить нельзя." -ForegroundColor Red; exit 1
}

# 1. Все объявления: полное имя класса -> файлы
$decl = @{}
Get-ChildItem $custom -Recurse -Filter *.cs -File | ForEach-Object {
    $file = $_
    $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
    if (-not $text) { return }
    $ns = [regex]::Match($text, '(?m)^\s*namespace\s+([\w\.]+)').Groups[1].Value
    foreach ($m in [regex]::Matches($text, '(?m)^\s*(?:public|internal)\s+(?:sealed\s+|abstract\s+|static\s+)*(?!partial\b)(?:class|struct|enum)\s+(\w+)')) {
        $key = "$ns.$($m.Groups[1].Value)"
        if (-not $decl.ContainsKey($key)) { $decl[$key] = New-Object System.Collections.Generic.List[object] }
        if (-not ($decl[$key] | Where-Object { $_.FullName -eq $file.FullName })) { $decl[$key].Add($file) }
    }
}

# 2. Повторы: оставить самый новый, остальные — в план переноса
$plan = @{}
$dups = $decl.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 } | Sort-Object Name
foreach ($d in $dups) {
    # Самый новый; при равном времени (копирование сохраняет время) — ближайший к корню bin\Custom
    $sorted = $d.Value | Sort-Object @{Expression = 'LastWriteTime'; Descending = $true}, @{Expression = { $_.FullName.Split('\').Count }; Ascending = $true}
    $keep = $sorted[0]
    Write-Host ""
    Write-Host $d.Name -ForegroundColor Yellow
    Write-Host ("  ОСТАВИТЬ  {0:yyyy-MM-dd HH:mm}  {1}" -f $keep.LastWriteTime, $keep.FullName.Substring($custom.Length)) -ForegroundColor Green
    foreach ($f in ($sorted | Select-Object -Skip 1)) {
        if ($f.Name -like "@*") {
            Write-Host ("  ПЕРЕНЕСТИ {0:yyyy-MM-dd HH:mm}  {1}" -f $f.LastWriteTime, $f.FullName.Substring($custom.Length))
            $plan[$f.FullName] = $f
        } else {
            # Переносятся только системные файлы @: несистемное совпадение может быть вложенным классом
            Write-Host ("  НЕ ТРОГАЮ (не системный файл, разберите вручную)  {0}" -f $f.FullName.Substring($custom.Length)) -ForegroundColor Magenta
        }
    }
}

Write-Host ""
if ($plan.Count -eq 0) { Write-Host "Повторов не найдено." -ForegroundColor Green; exit 0 }
Write-Host ("Классов с повторами: {0}; файлов к переносу: {1}" -f @($dups).Count, $plan.Count) -ForegroundColor Cyan

$dz = $plan.Keys | Where-Object { (Split-Path $_ -Leaf) -like "DZ_*" }
if ($dz) {
    Write-Host "ВНИМАНИЕ: среди переносимых есть файлы проекта DZ_ — проверьте план вручную:" -ForegroundColor Red
    $dz | ForEach-Object { Write-Host "  $_" }
}

if (-not $Apply) { Write-Host "Это план. Для переноса запустите с ключом -Apply (NinjaTrader должен быть закрыт)."; exit 0 }

# 3. Перенос с сохранением подпапок и журнал
$log = New-Object System.Collections.Generic.List[object]
foreach ($p in $plan.Keys) {
    $rel = $p.Substring($custom.Length).TrimStart('\')
    $dst = Join-Path $quar $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Move-Item -LiteralPath $p -Destination $dst
    $log.Add([pscustomobject]@{ From = $p; To = $dst; Time = (Get-Date) })
}
$log | Export-Csv -Path (Join-Path $quar "moved_files.csv") -NoTypeInformation -Encoding UTF8
Write-Host ("Перенесено файлов: {0} -> {1}" -f $log.Count, $quar) -ForegroundColor Green
Write-Host "Запустите NinjaTrader и нажмите F5 в редакторе NinjaScript. Вернуть файл — перенести его обратно из этой папки."
