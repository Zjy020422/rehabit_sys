@echo off
echo ====================================
echo Starting Regenix Application
echo ====================================
echo.

echo Step 1: Starting React App (Vite Dev Server)...
cd index
start "Regenix React App" cmd /k "npm run dev"
cd ..

timeout /t 3

echo.
echo Step 2: Starting Flask Backend...
start "Regenix Flask Backend" cmd /k "python app.py"

echo.
echo ====================================
echo Application Started!
echo ====================================
echo.
echo React App: http://localhost:5173
echo Flask Backend: http://localhost:5000
echo Main Page: http://localhost:5000
echo.
echo Press any key to close this window...
pause >nul
