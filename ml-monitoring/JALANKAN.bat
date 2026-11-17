@echo off
setlocal
pushd "%~dp0" || exit /b 1

echo == Cek Docker Desktop ==
call docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop belum menyala. Buka Docker Desktop, tunggu Engine running, lalu klik file ini lagi.
  goto gagal
)

echo == Mulai stack dan tunggu container siap ==
call docker compose up --build --wait --wait-timeout 120
if errorlevel 1 goto gagal

echo == Status container ==
call docker compose ps > log_ps.txt 2>&1
set "hasil=%errorlevel%"
type log_ps.txt
if not "%hasil%"=="0" goto gagal

echo == Cek otomatis ==
call docker compose exec -T model-api python check_stack.py > log_check.txt 2>&1
set "hasil=%errorlevel%"
type log_check.txt
if not "%hasil%"=="0" goto gagal

echo Panel: http://localhost:8090   Grafana: http://localhost:3001   Prometheus: http://localhost:9090
popd
pause
exit /b 0

:gagal
echo Stack atau pemeriksaan gagal. Periksa output di atas.
popd
pause
exit /b 1
