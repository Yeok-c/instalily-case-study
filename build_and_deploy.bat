@echo off
REM filepath: c:\D_Backup\Github\Applications_2025\instalily-case-study\build_and_deploy.bat

echo Setting up environment for build...
echo REACT_APP_API_URL=http://localhost:5000 > frontend\.env.local

echo Building React frontend...
cd frontend
call npm run build

echo Copying build files to Flask static folder...
if not exist ..\backend\webapp\static mkdir ..\backend\webapp\static
xcopy /E /Y build\* ..\backend\webapp\static\

echo Done! You can now run the Flask application to serve both backend and frontend.
echo.
echo Run with: cd ..\backend\webapp && python app.py
echo Then access the application at http://localhost:5000
echo.
echo For troubleshooting:
echo 1. Make sure the backend is running
echo 2. Check browser console for CORS errors
echo 3. Verify network requests in browser dev tools