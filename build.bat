@echo off
rem Builds Conduit Legacy Launcher into dist\Conduit Legacy Launcher (needs Python 3 with requirements.txt).
rem The release zip is that folder: the launcher only, nothing of the games, RPCS3 or the PS3 firmware.
setlocal
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --windowed --onedir --name "Conduit Legacy Launcher" ^
  --icon "%~dp0src\app.ico" --add-data "%~dp0src\locales;locales" --add-data "%~dp0src\app.ico;." ^
  --distpath "%~dp0dist" --workpath "%~dp0build" --specpath "%~dp0build" "%~dp0src\launcher.py" || exit /b 1
set "OUT=%~dp0dist\Conduit Legacy Launcher"
copy /y "%~dp0baixar-emulador.bat" "%OUT%\" >nul
copy /y "%~dp0LICENSE" "%OUT%\LICENSE.txt" >nul
copy /y "%~dp0CREDITS.md" "%OUT%\CREDITS.md" >nul
copy /y "%~dp0docs\LEIA-ME.txt" "%OUT%\LEIA-ME.txt" >nul
copy /y "%~dp0docs\THIRD-PARTY.txt" "%OUT%\THIRD-PARTY.txt" >nul
copy /y "%~dp0docs\MODS.md" "%OUT%\MODS.md" >nul
for %%d in (mods jogos) do if not exist "%OUT%\%%d" mkdir "%OUT%\%%d"
echo Pronto: %OUT%
exit /b 0
