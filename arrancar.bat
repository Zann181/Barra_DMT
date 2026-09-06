@echo off
title BarraDMT
cd /d "%~dp0"
"C:\Users\Motaz\AppData\Local\Programs\Python\Python313\python.exe" run.py
if errorlevel 1 pause
