@echo off
rem Baixa o RPCS3 (GPL-2.0, github.com/RPCS3) e o firmware do PS3 (do servidor da Sony) para a pasta rpcs3,
rem sem abrir o launcher. Faz o mesmo que o botao "Baixar / atualizar RPCS3".
rem Downloads RPCS3 and the PS3 firmware into the rpcs3 folder, without opening the launcher.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';" ^
  "$h = @{ 'User-Agent' = 'Conduit-Legacy-Launcher' };" ^
  "$r = Invoke-RestMethod 'https://api.github.com/repos/RPCS3/rpcs3-binaries-win/releases/latest' -Headers $h;" ^
  "$a = $r.assets | Where-Object { $_.name -like '*.7z' } | Select-Object -First 1;" ^
  "New-Item -ItemType Directory -Force 'rpcs3', 'out' | Out-Null;" ^
  "Write-Host ('Baixando ' + $a.name + '...');" ^
  "Invoke-WebRequest $a.browser_download_url -OutFile 'out\rpcs3.7z' -Headers $h -UseBasicParsing;" ^
  "& \"$env:SystemRoot\System32\tar.exe\" -xf 'out\rpcs3.7z' -C 'rpcs3'; if ($LASTEXITCODE) { throw 'Falha ao extrair' };" ^
  "Remove-Item 'out\rpcs3.7z';" ^
  "if (-not (Test-Path 'rpcs3\dev_flash\vsh\etc\version.txt')) {" ^
  "  $list = (Invoke-WebRequest 'http://fus01.ps3.update.playstation.net/update/ps3/list/us/ps3-updatelist.txt' -UseBasicParsing).Content;" ^
  "  $url = [regex]::Match($list, 'CDN=(\S+PS3UPDAT\.PUP)').Groups[1].Value;" ^
  "  Write-Host 'Baixando o firmware do PS3 da Sony (cerca de 200 MB)...';" ^
  "  Invoke-WebRequest $url -OutFile 'out\PS3UPDAT.PUP' -UseBasicParsing;" ^
  "  $q = [char]34; $pup = (Resolve-Path 'out\PS3UPDAT.PUP').Path;" ^
  "  Start-Process 'rpcs3\rpcs3.exe' -ArgumentList ('--headless --installfw ' + $q + $pup + $q) -WorkingDirectory 'rpcs3' -Wait;" ^
  "  Remove-Item 'out\PS3UPDAT.PUP';" ^
  "  if (-not (Test-Path 'rpcs3\dev_flash\vsh\etc\version.txt')) { throw 'O firmware nao foi instalado' }" ^
  "};" ^
  "Write-Host 'Pronto: rpcs3\rpcs3.exe com firmware.'"
if errorlevel 1 echo Nao deu certo. Verifique a internet e tente de novo.
pause
