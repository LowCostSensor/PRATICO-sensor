# Render the PRATICO 3 guides to PDF with headless Chrome.
#   powershell -NoProfile -ExecutionPolicy Bypass -File docs\pdf\src\render.ps1
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$out = Split-Path $src -Parent
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) { $chrome = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" }
$profile = Join-Path $env:TEMP "pratico-guides-chrome"

$docs = @{ "build-guide.html" = "PRATICO3_Build_Guide.pdf"; "user-guide.html" = "PRATICO3_User_Guide.pdf" }
foreach ($name in $docs.Keys) {
    $html = Join-Path $src $name
    if (-not (Test-Path $html)) { continue }
    $pdf = Join-Path $out $docs[$name]
    $url = "file:///" + ($html -replace "\\", "/" -replace " ", "%20")
    & $chrome --headless=new --disable-gpu --no-first-run --user-data-dir="$profile" `
        --no-pdf-header-footer --virtual-time-budget=5000 --print-to-pdf="$pdf" $url | Out-Null
    Write-Output "$($docs[$name])  $([math]::Round((Get-Item $pdf).Length / 1KB)) KB"
}
