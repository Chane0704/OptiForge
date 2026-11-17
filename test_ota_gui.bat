@echo off
title OptiForge OTA Update Simulator
echo ========================================================
echo  Testing OptiForge In-App OTA Update System
echo  Simulating version 1.0.0 to trigger update to v1.0.1
echo ========================================================
set OPTIFORGE_VERSION_OVERRIDE=1.0.0
"C:\Users\anish\miniconda3\python.exe" -m optiforge.app.main
pause
