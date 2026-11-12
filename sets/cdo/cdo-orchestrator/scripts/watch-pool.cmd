@echo off
REM Task Scheduler entry for the CDO pool watchdog (15-min cadence).
REM schtasks /tr can't hold the full argv — this shim keeps it short.
REM Fill in the three paths below for this machine/install before scheduling.
"PYTHONW_PATH" "SKILL_SCRIPTS_DIR\watch-pool.py" --project-root "PROJECT_ROOT" --orchestration-dir "docs\orchestration" --stall-timeout-minutes 45
