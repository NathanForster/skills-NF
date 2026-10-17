@echo off
rem Runs sync-skills.ps1 from this folder. -ExecutionPolicy Bypass applies to
rem this one run only; the machine's script execution policy is not changed.
rem Usage: double-click it, or run sync-skills.cmd from any terminal.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-skills.ps1" %*
set "SYNC_RC=%ERRORLEVEL%"

rem Started directly (double-clicked, or run from PowerShell or Git Bash), this
rem window closes when the script ends, so wait for a key first. From an open
rem cmd window, return straight to the prompt. Detected by whether this file's
rem name is on the command line that started cmd.exe; quotes are stripped first
rem so the comparison cannot break on them. Delayed expansion is enabled only
rem after the PowerShell call, so a ! in an argument is passed through intact.
setlocal EnableDelayedExpansion
set "STARTED_BY=!CMDCMDLINE:"=!"
if /i not "!STARTED_BY:%~nx0=!"=="!STARTED_BY!" pause
exit /b %SYNC_RC%
