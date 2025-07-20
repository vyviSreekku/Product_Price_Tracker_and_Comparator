@echo off
echo Starting price update at %date% %time% >> price_updates.log
cd /d C:\Users\HP\Documents\price_tracker
if errorlevel 1 (
    echo Failed to change directory at %date% %time% >> price_updates.log
    exit /b 1
)
python manage.py update_tracked_prices
if errorlevel 1 (
    echo Failed to update prices at %date% %time% >> price_updates.log
    exit /b 1
)
echo Price update completed successfully at %date% %time% >> price_updates.log 