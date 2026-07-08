$desktop = Resolve-Path "$PSScriptRoot\..\desktop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $desktop

$localElectron = Join-Path $desktop "node_modules\.bin\electron.cmd"
if (!(Test-Path $localElectron)) {
  npm install
}

if (Test-Path $localElectron) {
  & $localElectron --version *> $null
}

if ($LASTEXITCODE -eq 0) {
  & $localElectron .
  exit $LASTEXITCODE
}

$runner = Join-Path $root ".electron-runner"
$runnerElectron = Join-Path $runner "node_modules\.bin\electron.cmd"
if (!(Test-Path $runnerElectron)) {
  New-Item -ItemType Directory -Force $runner | Out-Null
  Push-Location $runner
  if (!(Test-Path "package.json")) {
    '{"private":true,"devDependencies":{}}' | Set-Content -Encoding UTF8 package.json
  }
  if (-not $env:ELECTRON_MIRROR) {
    $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
  }
  npm install electron@33.4.11 --save-dev
  Pop-Location
}
& $runnerElectron .
