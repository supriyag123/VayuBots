#Deployment Process Tip
Always work in .venv locally as this has the correct python version. Generated a requirement from this.... that requirement makes it portable. We can deploy based on this requirements
#load venv
C:\VayuBots\vayu>.\.venv\Scripts\activate

# TEST RUN 
(.venv) C:\VayuBots>python -m uvicorn vayu.server.main:app --reload --port 8000
#Ngrok -
ngrok http 8000 

# Karna Agent Project


pip install -r requirements.txt

\# ============================

\# Karna Marketing CLI Commands

\# ============================



# =======================================================
# 1. CURATE IDEAS
# =======================================================

# Curate ideas for ONE client
python karna.py --client-id recnfq86W5hV816Tv --num-ideas 20

# Curate ideas for ALL active clients
python karna.py --all-clients --num-ideas 20


# =======================================================
# 2. CREATE POSTS
# =======================================================

# Create posts from curated ideas for ONE client
python karna.py --client-id recnfq86W5hV816Tv --create-posts --num-posts 3

# Create posts for ALL active clients
python karna.py --all-clients --create-posts --num-posts 3


# =======================================================
# 3. PUBLISH POSTS
# =======================================================

# Publish approved posts for ONE client
python karna.py --client-id recnfq86W5hV816Tv --publish


# =======================================================
# 4. FULL WORKFLOW (Curation → Posts → Publishing)
# =======================================================

# Run everything end-to-end for ONE client
python karna.py --client-id recnfq86W5hV816Tv --full-workflow --num-ideas 20 --num-posts 3

# Run everything end-to-end for ALL active clients
python karna.py --all-clients --full-workflow --num-ideas 20 --num-posts 3


# =======================================================
# 5. CLIENT DIRECT INPUT (WhatsApp / Web form simulation)
# =======================================================

# Submit a raw idea text for ONE client
python karna.py --client-id recnfq86W5hV816Tv --client-input "Host Diwali festival in Perth"

# Submit with image + specific channel
python karna.py --client-id recnfq86W5hV816Tv \
  --client-input "Host Diwali festival in Perth" \
  --image-url "https://example.com/diwali.jpg" \
  --channel Facebook


# =======================================================
# 6. OPTIONAL PARAMETERS
# =======================================================

# Limit number of clients processed in all-clients mode
--max-clients 2

# Suppress verbose logs
--quiet

# Change number of ideas or posts created
--num-ideas 10
--num-posts 5



\# --- General Options ---



\# Control verbosity

--quiet          # minimal logs

\# (default shows detailed logs)



\# Adjust limits

--num-ideas 20   # max number of ideas to curate

--num-posts 3    # number of posts to create per client

--max-clients 2  # limit number of clients when using --all-clients



=============================================
# Karna WhatsApp Deployment - Step by Step Implementation Guide

This guide will take you from your current setup to a production-ready WhatsApp-enabled system for multiple clients.



## Phase 1: Repository Setup (30 minutes)





### Step 3.1: Create Twilio Account

1. Go to https://www.twilio.com/try-twilio
2. Sign up (you get $15 free credit)
3. Verify your email and phone number

### Step 3.2: Set Up WhatsApp Sandbox

1. In Twilio Console, go to:
   **Messaging** → **Try it out** → **Send a WhatsApp message**

2. You'll see instructions like:
   ```
   Join your sandbox by sending "join <code>" to whatsapp:+14155238886
   ```

3. On your phone:
   - Open WhatsApp
   - Send a message to **+1 415 523 8886**
   - Text: `join [your-code]` (e.g., `join happy-dog`)
   - You should get a confirmation message

### Step 3.3: Get API Credentials

1. From Twilio Console Dashboard, copy:
   - **Account SID** (starts with AC...)
   - **Auth Token** (click "show" to reveal)

2. Save these for your `.env` file

### Step 3.4: Note Your WhatsApp Number

- The sandbox number is usually: `whatsapp:+14155238886`
- Save this for your `.env` file

---

## Phase 4: Local Configuration & Testing (30 minutes)

### Step 4.1: Create .env File

```bash
# Copy the example
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

Fill in these **critical** values:

```bash
# Required
OPENAI_API_KEY=sk-proj-...your-key...
AIRTABLE_API_KEY=pat...your-key...
AIRTABLE_BASE_ID=app...your-base-id...
TWILIO_ACCOUNT_SID=AC...your-sid...
TWILIO_AUTH_TOKEN=...your-token...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Environment
ENVIRONMENT=development
PORT=8000
```

### Step 4.2: Test Local Server

```bash
# Start the server
python server.py

# You should see:
# INFO:     Started server process
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

In another terminal:
```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","timestamp":"2025-...","service":"karna-api"}
```

### Step 4.3: Test with ngrok (Temporary Public URL)

To test WhatsApp locally, you need a public URL:

```bash
# Install ngrok (one-time)
brew install ngrok  # Mac
# or download from https://ngrok.com/download

# Start ngrok
ngrok http 8000

# You'll get a URL like: https://abc123.ngrok.io
```

### Step 4.4: Configure Twilio Webhook Temporarily

1. Go to Twilio Console → Messaging → Settings → WhatsApp Sandbox Settings
2. Under "When a message comes in":
   - Paste: `https://abc123.ngrok.io/webhook/whatsapp`
   - Method: `POST`
3. Click **Save**

### Step 4.5: Test WhatsApp Flow

Send a message from your phone to the Twilio WhatsApp number:

```
You: Hi
Karna: Hi [Your Name]! 👋

How can I help you today?

• 📱 Social Media - manage posts
• 🌐 Web - update website
...
```

**If this works, you're ready for production deployment!**

---

## Phase 5: Production Deployment to Render (45 minutes)

### Step 5.1: Prepare Git Repository

```bash
# Initialize git (if not already)
git init

# Create .gitignore
cat > .gitignore << 'EOF'
venv/
__pycache__/
*.pyc
.env
.DS_Store
*.log
.pytest_cache/
*.egg-info/
EOF

# Add all files
git add .

# Commit
git commit -m "Production-ready Karna with WhatsApp integration"
```

### Step 5.2: Push to GitHub

```bash
# Create new repo on GitHub (github.com/new)
# Then:

git remote add origin https://github.com/YOUR_USERNAME/karna.git
git branch -M main
git push -u origin main
```

### Step 5.3: Create Render Account

1. Go to https://render.com
2. Click **Get Started**
3. Sign up with GitHub
4. Authorize Render to access your repositories

### Step 5.4: Create Web Service on Render

1. From Render Dashboard, click **New +** → **Web Service**

2. Connect your `karna` repository

3. Configure the service:
   - **Name**: `karna-api` (or your preferred name)
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Runtime**: Docker
   - **Instance Type**: 
     - Start with **Starter** ($7/month)
     - Upgrade to **Standard** when you have 5+ clients

4. Click **Create Web Service** (don't worry about env vars yet)

### Step 5.5: Add Environment Variables

In Render Dashboard → Your Service → Environment:

Click **Add Environment Variable** and add each of these:

```
ENVIRONMENT=production
PORT=8000
MAX_WORKERS=2

OPENAI_API_KEY=sk-proj-...
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...

TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

Click **Save Changes** - this will trigger a deployment.

### Step 5.6: Wait for Deployment

- Watch the logs in real-time
- Deployment takes 3-5 minutes
- You'll see: `==> Build successful 🎉`

### Step 5.7: Get Your Production URL

- After deployment, you'll see your URL
- It will be something like: `https://karna-api.onrender.com`
- Test it: Visit `https://karna-api.onrender.com/health`

---

## Phase 6: Production WhatsApp Configuration (15 minutes)

### Step 6.1: Update Twilio Webhook

1. Go to Twilio Console → Messaging → WhatsApp Sandbox Settings

2. Update "When a message comes in":
   - URL: `https://karna-api.onrender.com/webhook/whatsapp`
   - Method: `POST`

3. Click **Save**

### Step 6.2: Test Production

Send a WhatsApp message to test:

```
You: Hi
Karna: [Should respond from production server]
```

### Step 6.3: Test Full Flow

```
You: Social Media
Karna: OK, do you want to check newly curated posts...

You: show me what you got
Karna: [Shows top 3 posts]

You: First
Karna: [Shows selected post details]

You: Approve
Karna: Great! It is posted now...
```

---

## Phase 7: Add More Clients (10 minutes per client)

### For Each New Client:

1. **Add to Airtable**:
   - Go to Clients table
   - Add new record
   - Fill in Name, WhatsApp Phone, Status=Active
   - Add all their preferences

2. **Have Them Join Sandbox**:
   - They need to send `join [code]` to the Twilio number
   - They should send from the phone number you added to Airtable

3. **Test**:
   - Have them send "Hi" to Karna
   - Verify they get a response

4. **Configure Their Socials**:
   - Add their social media credentials
   - Test publishing to their accounts

---

## Phase 8: Monitoring & Maintenance (Ongoing)

### Step 8.1: Set Up Error Monitoring

1. Create Sentry account (free tier available)
2. Create new project
3. Copy DSN
4. Add to Render environment variables:
   ```
   SENTRY_DSN=https://...@sentry.io/...
   ```

### Step 8.2: Set Up Automated Tasks

**Option A: Render Cron Jobs**

1. In Render, click **New +** → **Cron Job**
2. Configure:
   - **Name**: `daily-curation`
   - **Command**: `curl -X POST https://karna-api.onrender.com/api/scheduled/daily-curate`
   - **Schedule**: `0 9 * * *` (9 AM daily)

**Option B: External Cron Service**

Use https://cron-job.org/:
1. Create account
2. Add job with your URL
3. Set schedule

### Step 8.3: Set Up Uptime Monitoring

Use https://uptimerobot.com/ (free):
1. Create monitor
2. URL: `https://karna-api.onrender.com/health`
3. Interval: 5 minutes
4. Add email alert

### Step 8.4: Monitor Logs

In Render Dashboard:
- Click **Logs** tab
- Watch for errors
- Set up log drains if needed

---

## Phase 9: Upgrade to Production WhatsApp (Optional, for later)

When you're ready for production WhatsApp with your own branding:

1. **Request WhatsApp Business API Access**:
   - Twilio Console → Messaging → WhatsApp → Senders
   - Click "Request Access"

2. **Complete Facebook Business Verification**:
   - Requires business documents
   - Takes 1-2 weeks

3. **Submit WhatsApp Profile**:
   - Business name
   - Logo
   - Description
   - Categories

4. **Get Approved**:
   - Wait for Meta approval (3-5 days)

5. **Update Webhook**:
   - Point to your production number
   - Update clients to use new number

---

## Troubleshooting Common Issues

### Issue: "Client not found by phone"

**Solution**:
- Check phone format in Airtable (must be +1234567890)
- Verify WhatsApp Phone field exists
- Check client Status is "Active"

### Issue: "Webhook timeout"

**Solution**:
- Processing takes > 15 seconds
- Already handled with BackgroundTasks
- Check Render logs for actual errors

### Issue: "Module not found"

**Solution**:
```bash
# Rebuild on Render
git add requirements.txt
git commit -m "Update dependencies"
git push

# Render will auto-deploy
```

### Issue: "Airtable rate limit"

**Solution**:
- Airtable has 5 requests/second limit
- Add rate limiting in code
- Consider upgrading Airtable plan

### Issue: "OpenAI timeout"

**Solution**:
- Increase timeout in karna.py
- Check OpenAI API status
- Verify API key is valid

---

## Next Steps

Once everything is working:

1. ✅ Add more clients
2. ✅ Set up monitoring
3. ✅ Enable automated curation
4. ✅ Track usage per client
5. ✅ Set up billing
6. ✅ Request production WhatsApp access

---

## Cost Breakdown

**Monthly Costs (estimated):**
- Render Starter: $7/month
- Twilio WhatsApp: ~$0.005 per message
- OpenAI API: ~$0.01-0.10 per post generation
- **Total for 10 clients**: ~$20-50/month

**When to Upgrade:**
- Render Standard ($25/month): 10+ clients
- Twilio Pro: 1000+ messages/month
- OpenAI higher limits: Heavy usage

---

## Support

If you get stuck:
1. Check Render logs
2. Check Twilio debugger
3. Test locally with ngrok first
4. Review this guide step-by-step

Good luck with your deployment! 🚀

### RENDER

https://vayubots.onrender.com/cron/daily

🚀 How You Use This in Make

You now have two modes per function:

Endpoint	Purpose	Run time	Make setup
/api/karna/full_workflow	Run 1 client and wait for result	<2 min	Use “Make an API call” directly
/api/karna/full_workflow_async	Queue 1 client and return instantly	Long	Use for daily schedule
/api/karna/full_workflow_all_async	Queue all clients	Long	Use for cron-style automation
/api/karna/client_input	Submit idea (text/image)	Instant	Use Softr or WhatsApp form trigger


##local test

http://127.0.0.1:8000/docs
