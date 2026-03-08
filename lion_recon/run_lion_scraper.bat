@echo off

REM Activate the wx310 conda environment
call C:\ProgramData\miniconda3\Scripts\activate.bat wx310

REM Change to the project directory
cd /d C:\Users\digitalscorpyun\projects_2026\lion_recon

REM Run the Python script
python lion_scraper.py