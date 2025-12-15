# Setting Up .env File for Supabase

## Quick Setup

### Step 1: Create .env File

Create a file named `.env` in the **same directory** as `upload_to_supabase.py`:

**Location:** `C:\Users\hp\Desktop\apartments home\apartments\apartments\.env`

### Step 2: Add Your Supabase Credentials

Open the `.env` file in a text editor and add:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

**Replace with your actual values:**
- `your-project-id` → Your Supabase project ID
- `your-anon-or-service-role-key` → Your Supabase API key

### Step 3: Get Your Supabase Credentials

1. Go to https://supabase.com and sign in
2. Open your project (or create a new one)
3. Go to **Settings** → **API**
4. Copy:
   - **Project URL** → Use for `SUPABASE_URL`
   - **anon/public key** → Use for `SUPABASE_KEY` (for client-side)
   - Or **service_role key** → Use for `SUPABASE_KEY` (for server-side, more permissions)

### Step 4: Verify .env File Format

Your `.env` file should look like this:

```env
SUPABASE_URL=https://abcdefghijklmnop.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFiY2RlZmdoaWprbG1ub3AiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTYxNjIzOTAyMiwiZXhwIjoxOTMxODE1MDIyfQ.example
```

**Important:**
- No quotes around values (unless they contain spaces)
- No spaces around the `=` sign
- One variable per line
- Lines starting with `#` are comments

## Alternative: Use Command Line Arguments

If you don't want to use a .env file, you can pass credentials directly:

```powershell
python upload_to_supabase.py --supabase-url "https://your-project.supabase.co" --supabase-key "your-key"
```

## Alternative: Set Environment Variables (PowerShell)

```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_KEY="your-anon-key"
python upload_to_supabase.py
```

## Verify Setup

After creating the .env file, run:

```powershell
python upload_to_supabase.py
```

You should see:
```
📄 Found .env file at: C:\Users\hp\Desktop\apartments home\apartments\apartments\.env
✅ Loaded 2 environment variable(s) from .env file
🔌 Connecting to Supabase...
✅ Connected to Supabase
```

## Troubleshooting

### "SUPABASE_URL environment variable is not set"

**Solution:**
1. Check that `.env` file exists in the correct location
2. Verify the file name is exactly `.env` (not `.env.txt` or `env`)
3. Check that the file format is correct (no quotes, no spaces around `=`)
4. Make sure the file is in: `apartments\apartments\.env`

### "Error connecting to Supabase"

**Solution:**
1. Verify your `SUPABASE_URL` is correct (should start with `https://`)
2. Verify your `SUPABASE_KEY` is correct (long JWT token)
3. Check that your Supabase project is active
4. Try using `service_role` key instead of `anon` key

### File Not Found

The script checks these locations in order:
1. `apartments\apartments\.env` (same directory as script)
2. `apartments\.env` (parent directory)
3. `C:\Users\hp\.env` (home directory)

Make sure your `.env` file is in one of these locations.

## Security Note

⚠️ **Never commit your .env file to Git!**

The `.env` file contains sensitive credentials. Make sure it's in your `.gitignore` file.

