@echo off
setlocal
cd /d "%~dp0"
if "%PORT%"=="" set "PORT=8000"
for /f %%p in ('powershell -NoProfile -Command "$port = if ($env:PORT) { [int]$env:PORT } else { 8000 }; while ($true) { try { $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port); $listener.Start(); $listener.Stop(); $port; break } catch { $port += 1; if ($port -gt 8100) { throw 'No free port found.' } } }"') do set "PORT=%%p"
where python >nul 2>nul
if not errorlevel 1 (
    python -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT% --reload
) else (
    py -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT% --reload
)
endlocal
