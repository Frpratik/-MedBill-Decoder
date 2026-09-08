$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$toolsDir = Join-Path $projectRoot '.tools'
$ocrDir = Join-Path $toolsDir 'tesseract'
$sevenZip = @('C:\ProgramData\chocolatey\tools\7z.exe', 'C:\Program Files\7-Zip\7z.exe') |
    Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $sevenZip) {
    throw '7-Zip is needed for local extraction. Alternatively install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki and add it to PATH.'
}
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$installer = Join-Path $toolsDir 'tesseract-installer.exe'
$binaryUrl = 'https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe'
$binaryHash = 'BEE9E3434BD94FD65387D9BE28CD467A41F61B1275383B55B0F59A1331270AE4'
if (-not (Test-Path -LiteralPath $installer)) {
    Invoke-WebRequest -Uri $binaryUrl -OutFile $installer
}
if ((Get-FileHash -LiteralPath $installer).Hash -ne $binaryHash) {
    throw 'Tesseract archive checksum mismatch. Review source; do not run it.'
}
if (-not (Test-Path -LiteralPath (Join-Path $ocrDir 'tesseract.exe'))) {
    & $sevenZip x $installer "-o$ocrDir" -y
    if ($LASTEXITCODE -ne 0) { throw 'Tesseract archive extraction failed.' }
}
$modelDir = Join-Path $ocrDir 'tessdata'
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
$model = Join-Path $modelDir 'eng.traineddata'
if (-not (Test-Path -LiteralPath $model)) {
    Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/eng.traineddata' -OutFile $model
}
if ((Get-FileHash -LiteralPath $model).Hash -ne '7D4322BD2A7749724879683FC3912CB542F19906C83BCC1A52132556427170B2') {
    throw 'English model checksum mismatch. Review the upstream revision.'
}
& (Join-Path $ocrDir 'tesseract.exe') --version
& (Join-Path $ocrDir 'tesseract.exe') --list-langs
if ($LASTEXITCODE -ne 0) { throw 'Tesseract verification failed.' }
