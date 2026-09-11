@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "REPO=%~1"
set "DACHAPPLY_SOURCE_REPO=%REPO%"
set "STOP_SCRIPT=%~2"
if not defined REPO goto usage
if not defined DACHAPPLY_RUNTIME_DIR set "DACHAPPLY_RUNTIME_DIR=%LOCALAPPDATA%\dachapply\main-runtime"
set "RUNTIME=%DACHAPPLY_RUNTIME_DIR%"

rem This is a disposable release worktree. Active development worktrees are never reset.
git -C "%REPO%" rev-parse --verify origin/main >nul 2>&1
if errorlevel 1 goto sync_failed

if exist "%RUNTIME%\.git" (
  git -C "%RUNTIME%" reset --hard origin/main >nul 2>&1
  if errorlevel 1 goto sync_failed
) else (
  if exist "%RUNTIME%" goto occupied_runtime
  for %%d in ("%RUNTIME%") do if not exist "%%~dpd" mkdir "%%~dpd"
  git -C "%REPO%" worktree prune
  git -C "%REPO%" worktree add --detach "%RUNTIME%" origin/main >nul 2>&1
  if errorlevel 1 goto sync_failed
)

for /f "delims=" %%c in ('git -C "%RUNTIME%" rev-parse HEAD') do set "LOCAL_SHA=%%c"
for /f "delims=" %%c in ('git -C "%REPO%" rev-parse origin/main') do set "MAIN_SHA=%%c"
if not "!LOCAL_SHA!"=="!MAIN_SHA!" goto sync_failed

if exist "%REPO%\.env" (
  if exist "%RUNTIME%\.env" del /q "%RUNTIME%\.env"
  mklink /H "%RUNTIME%\.env" "%REPO%\.env" >nul
  if errorlevel 1 goto env_failed
)

echo Local release ready: !LOCAL_SHA!
if "%DACHAPPLY_PREPARE_ONLY%"=="1" exit /b 0
if not exist "%STOP_SCRIPT%" goto usage

call "%STOP_SCRIPT%"
pushd "%RUNTIME%"
call uv sync --frozen
if errorlevel 1 goto start_failed
pushd frontend
call npm ci --prefer-offline --no-audit
if errorlevel 1 goto start_failed
popd

rem TASK-226: LAN access is opt-in and off by default. Without DACHAPPLY_LAN_ACCESS nothing below
rem changes anything: BIND stays 127.0.0.1:8000 and no frontend build runs, exactly as before.
rem The flag is read from the same .env Django reads (hard-linked above), so one line there
rem configures both halves and survives a reboot; a value already in this environment wins, matching
rem load_env_file's os.environ.setdefault. The child process inherits it, so the backend sees it too.
rem Opening the Windows firewall is a separate, one-time, elevated step -- see README.md,
rem "Reaching the app from another device on your network", for the exact add and delete commands.
if exist "%RUNTIME%\.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%k in ("%RUNTIME%\.env") do (
    if /i "%%k"=="DACHAPPLY_LAN_ACCESS" if not defined DACHAPPLY_LAN_ACCESS set DACHAPPLY_LAN_ACCESS=%%l
  )
)
set "BIND=127.0.0.1:8000"
if defined DACHAPPLY_LAN_ACCESS (
  set LAN_FLAG=!DACHAPPLY_LAN_ACCESS:"=!
  rem Same truthy set as settings.py's env_bool, so the launcher and Django can never disagree.
  for %%v in (1 true yes on) do if /i "!LAN_FLAG!"=="%%v" set "BIND=0.0.0.0:8000"
)

if "!BIND!"=="0.0.0.0:8000" (
  rem A LAN device is served by Django itself at :8000 out of frontend\dist. Without this build dist
  rem does not exist in the runtime worktree, config/urls.py has no SPA to serve, and / would
  rem otherwise redirect to http://localhost:5173 -- an address a phone resolves to itself. The Vite
  rem server started below is left exactly as it was and is not part of the LAN path at all.
  echo Building the frontend so LAN devices can be served from this host on port 8000 ...
  pushd frontend
  call npm run build
  if errorlevel 1 goto start_failed
  popd
)

start /b "" cmd /c "call .venv\Scripts\activate.bat && cd backend && python manage.py runserver !BIND!"
pushd frontend
call npm run dev
popd
call "%STOP_SCRIPT%"
popd
exit /b 0

:usage
echo ERROR: dachapply local runtime needs the repository and stop-script paths. 1>&2
exit /b 2

:occupied_runtime
echo ERROR: %RUNTIME% exists but is not the dedicated dachapply runtime worktree. 1>&2
exit /b 1

:env_failed
echo ERROR: could not link the local .env into the dedicated runtime. Nothing was started. 1>&2
exit /b 1

:sync_failed
echo ERROR: could not synchronize the local runtime with origin/main. Nothing was started. 1>&2
exit /b 1

:start_failed
call "%STOP_SCRIPT%"
echo ERROR: local dependency setup failed. The local servers were stopped. 1>&2
exit /b 1
