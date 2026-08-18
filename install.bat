@echo off
echo Installing Python packages...
pip install -r requirements.txt

echo.
echo Installing Chromium browser for Playwright...
playwright install chromium

echo.
echo ================================================
echo  Setup complete!
echo  To start the app, run:  python app.py
echo  Then open your browser: http://localhost:5000
echo ================================================
pause
