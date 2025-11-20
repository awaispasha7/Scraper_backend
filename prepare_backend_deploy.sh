#!/bin/bash
# Script to prepare backend for deployment

echo "🔧 Preparing Backend for Deployment..."

# Create Procfile if it doesn't exist
if [ ! -f Procfile ]; then
    echo "📝 Creating Procfile..."
    echo "worker: python forsalebyowner_selenium_scraper.py" > Procfile
    echo "✅ Created Procfile"
fi

# Create runtime.txt if it doesn't exist
if [ ! -f runtime.txt ]; then
    echo "📝 Creating runtime.txt..."
    echo "python-3.11" > runtime.txt
    echo "✅ Created runtime.txt"
fi

# Check if requirements.txt exists
if [ ! -f requirements.txt ]; then
    echo "⚠️  requirements.txt not found!"
else
    echo "✅ requirements.txt found"
fi

echo ""
echo "✅ Backend prepared for deployment!"
echo ""
echo "Next steps:"
echo "1. Install Railway CLI: npm install -g @railway/cli"
echo "2. Login: railway login"
echo "3. Initialize: railway init"
echo "4. Deploy: railway up"
echo ""
echo "Or deploy to Render/Heroku using their dashboards"

