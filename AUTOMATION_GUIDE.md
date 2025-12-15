# Scraper Automation Guide

## Overview

This guide explains how to automate your scrapers using **cron-job.org** and the frontend control panel.

---

## 🎛️ Frontend Control Panel

After deploying, you'll find a **Scraper Control Panel** on the home page dashboard with:

- **5 Individual Run Buttons**: FSBO, Apartments, Zillow FSBO, Zillow FRBO, Hotpads
- **1 Run All Button**: Triggers all scrapers sequentially

### Usage
1. Click any button to start a scraper
2. A status message will appear showing progress
3. Scrapers run in the background on your Railway server
4. Data appears in Supabase when complete (~10-60 min per scraper)

---

## ⏰ Automated Scheduling with cron-job.org

### Step 1: Get Your Backend URL

Your Railway backend URL looks like:
```
https://your-backend-name.up.railway.app
```

### Step 2: Create cron-job.org Account

1. Go to [cron-job.org](https://console.cron-job.org/signup)
2. Sign up with email
3. Verify your email

### Step 3: Create the Cron Job

1. Click **"Create cronjob"**
2. Fill in the form:

| Field | Value |
|-------|-------|
| **Title** | Scraper Backend - Run All |
| **URL** | `https://YOUR-BACKEND-URL/api/trigger-all` |
| **Schedule** | Every 12 hours |
| **Request Method** | GET |

3. For schedule, select:
   - **Days**: Every day
   - **Hours**: 0, 12 (runs at 12 AM and 12 PM)
   - **Minutes**: 0

4. Click **"Create"**

### Step 4: Test

1. Click **"Test run"** in your cron-job.org dashboard
2. Check Railway logs for scraper activity
3. Verify data appears in Supabase

---

## 📊 API Endpoints Reference

| Endpoint | Description |
|----------|-------------|
| `GET /api/trigger` | Run FSBO scraper |
| `GET /api/trigger-apartments` | Run Apartments scraper |
| `GET /api/trigger-zillow-fsbo` | Run Zillow FSBO scraper |
| `GET /api/trigger-zillow-frbo` | Run Zillow FRBO scraper |
| `GET /api/trigger-hotpads` | Run Hotpads scraper |
| `GET /api/trigger-all` | Run ALL scrapers sequentially |
| `GET /api/status-all` | Get status of all scrapers |

---

## 🔧 Environment Variables

Add to your frontend `.env.local`:
```
NEXT_PUBLIC_BACKEND_URL=https://your-backend-url.up.railway.app
```

---

## ⏱️ Expected Run Times

| Scraper | Approximate Time |
|---------|------------------|
| FSBO (Selenium) | 30-60 minutes |
| Apartments | 15-30 minutes |
| Zillow FSBO | 10-20 minutes |
| Zillow FRBO | 10-20 minutes |
| Hotpads | 10-20 minutes |
| **Total (All)** | **2-3 hours** |

---

## 🆘 Troubleshooting

### "Could not connect to backend"
- Check your `NEXT_PUBLIC_BACKEND_URL` is correct
- Ensure backend is deployed and running
- Check CORS settings in your backend

### Scraper not running
- Check Railway logs for errors
- Verify the scraper directory exists
- Check Supabase connection settings

### No data appearing
- Wait for scraper to complete (check `/api/status-all`)
- Check Supabase table for new entries
- Review Railway logs for pipeline errors
