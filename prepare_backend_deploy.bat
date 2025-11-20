@echo off
echo 🔧 Preparing Backend for Deployment...
echo.

if not exist Procfile (
    echo 📝 Creating Procfile...
    echo worker: python forsalebyowner_selenium_scraper.py > Procfile
    echo ✅ Created Procfile
)

if not exist runtime.txt (
    echo 📝 Creating runtime.txt...
    echo python-3.11 > runtime.txt
    echo ✅ Created runtime.txt
)

if not exist requirements.txt (
    echo ⚠️  requirements.txt not found!
) else (
    echo ✅ requirements.txt found
)

echo.
echo ✅ Backend prepared for deployment!
echo.
echo Next steps:
echo 1. Install Railway CLI: npm install -g @railway/cli
echo 2. Login: railway login
echo 3. Initialize: railway init
echo 4. Deploy: railway up
echo.
echo Or deploy to Render/Heroku using their dashboards

pause

