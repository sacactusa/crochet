@echo off
REM ==============================================================================
REM CrochetBench-Dstep Daily Experiment Runner for Windows Task Scheduler
REM Scheduled daily at 15:30 WIB (08:30 UTC), following Pacific midnight reset
REM ==============================================================================

cd /d "c:\Users\salis\OneDrive\Documents\Materi Kuliah\3,5\sempro"

echo [%DATE% %TIME%] Starting daily scheduled experiment run... >> logs\daily_execution.log

REM Run both model families (Family 2.5 and Family 3.8 in parallel threads)
python src\run_daily.py --all >> logs\daily_execution.log 2>&1

echo [%DATE% %TIME%] Daily experiment run finished. >> logs\daily_execution.log

