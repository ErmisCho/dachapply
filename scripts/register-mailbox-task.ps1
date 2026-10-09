# Registers (or replaces) the hourly Windows Scheduled Task "dachapply-mailbox-check".
#
# TASK-275: the hourly mailbox check moved off GitHub Actions so that no scheduled cloud job runs.
# It runs check_mailbox --force from the local runtime worktree (the one
# scripts/dachapply-local-runtime.cmd keeps at origin/main) against the shared production database.
# check_mailbox is in settings.LOCAL_PROD_DB_SERVING_COMMANDS, so the local DB guard allows that.
#
# What must exist locally before registering (checked below, registration fails if missing):
#   - The runtime worktree with backend\ and a .env, i.e. the launcher has run at least once. That
#     .env is hard-linked from the source repo and supplies DATABASE_URL, GMAIL_OAUTH_CLIENT_ID and
#     GMAIL_OAUTH_CLIENT_SECRET.
#   - The Gmail OAuth token file <source repo>\dachapply-gmail-oauth-token.json, written by
#     `manage.py gmail_oauth_setup` (docs/email-setup.md, Option B). The launcher does not link it
#     into the runtime, and the runtime's default GMAIL_OAUTH_TOKEN_PATH points inside the runtime,
#     so the task sets GMAIL_OAUTH_TOKEN_PATH explicitly. In Google's "Testing" mode the token expires
#     about every 7 days; re-run gmail_oauth_setup in the source repo, then no re-registration is needed.
#   - uv on PATH (its full path is baked into the task).
#
# Runs as the current user, only while they are logged on, so a console window flashes each hour.
# Output is appended to %LOCALAPPDATA%\dachapply\mailbox-check.log; MailboxRun rows record the result.
#
# Usage (PowerShell): .\scripts\register-mailbox-task.ps1 [-SourceRepo <path>] [-RuntimeDir <path>]
# Remove:             Unregister-ScheduledTask -TaskName dachapply-mailbox-check -Confirm:$false

param(
    # Default: the repo containing this script. Run it from the owner's checkout, not a worktree.
    [string]$SourceRepo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    # Same default as scripts/dachapply-local-runtime.cmd.
    [string]$RuntimeDir = $(if ($env:DACHAPPLY_RUNTIME_DIR) { $env:DACHAPPLY_RUNTIME_DIR } else { Join-Path $env:LOCALAPPDATA 'dachapply\main-runtime' })
)

$ErrorActionPreference = 'Stop'
$TaskName = 'dachapply-mailbox-check'

$backendDir = Join-Path $RuntimeDir 'backend'
$envFile = Join-Path $RuntimeDir '.env'
$tokenPath = Join-Path $SourceRepo 'dachapply-gmail-oauth-token.json'
$logDir = Join-Path $env:LOCALAPPDATA 'dachapply'
$logFile = Join-Path $logDir 'mailbox-check.log'

if (-not (Test-Path -LiteralPath (Join-Path $backendDir 'manage.py'))) { throw "Runtime backend not found: $backendDir (run the local launcher once first)" }
if (-not (Test-Path -LiteralPath $envFile)) { throw "Runtime .env not found: $envFile (run the local launcher once first)" }
if (-not (Test-Path -LiteralPath $tokenPath)) { throw "Gmail OAuth token not found: $tokenPath (run manage.py gmail_oauth_setup in $SourceRepo\backend)" }
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { throw 'uv is not on PATH' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# LLM_PROVIDER=heuristic keeps the hourly run deterministic, as the cloud workflow it replaces was.
# cmd /c strips only the outermost quote pair, so the inner quoted paths survive.
$command = "set `"GMAIL_OAUTH_TOKEN_PATH=$tokenPath`" && set `"LLM_PROVIDER=heuristic`" && cd /d `"$backendDir`" && `"$uv`" run --locked --no-dev python manage.py check_mailbox --force >> `"$logFile`" 2>&1"
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$command`""

# No -RepetitionDuration: on Windows 10/11 that means repeat indefinitely.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
# StartWhenAvailable catches up a run missed while the PC slept; the 20-minute limit matches the old
# workflow's timeout-minutes; IgnoreNew stops a slow run from overlapping the next one.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

# -Force replaces an existing task of the same name, which makes re-running this idempotent.
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'dachapply hourly check_mailbox --force (TASK-275)' -Force | Out-Null

Write-Host "Registered $TaskName (hourly). Runtime: $backendDir  Token: $tokenPath  Log: $logFile"
Write-Host "Run once now with: Start-ScheduledTask -TaskName $TaskName"
