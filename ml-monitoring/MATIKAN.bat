@echo off
setlocal
pushd "%~dp0" || exit /b 1
call docker compose down
set "hasil=%errorlevel%"
popd
pause
exit /b %hasil%
