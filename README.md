# Guard Automation

Automated submission system for Guard by Berkshire Hathaway portal.

## 📁 Project Structure

```
guard_automation/
├── config.py                    # Configuration and settings
├── guard_login.py              # Login automation handler
├── guard_quote.py              # Quote/submission automation
├── webhook_server.py           # Webhook server (Flask)
├── test_webhook_local.py       # Local testing script
├── test_and_download_trace.py  # Test with trace download
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── logs/                      # Log files and screenshots
├── traces/                    # Playwright trace files
├── sessions/                  # Browser session data
└── debug/                     # Debug artifacts

```

## 🚀 Setup

### 1. Install Dependencies

```powershell
cd "c:\Users\Dell\Desktop\RPA For a\guard_automation"
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```powershell
copy .env.example .env
```

Edit `.env`:
```env
GUARD_USERNAME=your_username@example.com
GUARD_PASSWORD=your_password
```

### 3. Run Webhook Server

```powershell
python webhook_server.py
```

Server will start on `http://localhost:5001`

## 🧪 Testing

### Test Locally

```powershell
# Terminal 1: Start webhook server
python webhook_server.py

# Terminal 2: Run test
python test_webhook_local.py
```

### Test with Trace Download

```powershell
python test_and_download_trace.py
```

View downloaded traces:
```powershell
playwright show-trace traces/test_trace_XXXXX.zip
```

## 📡 Webhook API

### Send Automation Request

**Endpoint:** `POST /webhook`

**Payload:**
```json
{
  "action": "start_automation",
  "task_id": "optional_unique_id",
  "data": {
    "form_data": {
      "firstName": "John",
      "lastName": "Doe",
      "companyName": "Example LLC",
      "email": "john@example.com",
      "phone": "(555) 123-4567"
    },
    "quote_data": {
      "coverage_type": "General Liability",
      "policy_limit": "1000000"
    }
  },
  "credentials": {
    "username": "optional@email.com",
    "password": "optional_password"
  }
}
```

**Response:**
```json
{
  "status": "accepted",
  "task_id": "task_20251209_120000",
  "message": "Guard automation task started",
  "status_url": "/task/task_20251209_120000/status"
}
```

### Check Task Status

**Endpoint:** `GET /task/{task_id}/status`

**Response:**
```json
{
  "status": "completed",
  "task_id": "task_20251209_120000",
  "completed_at": "2025-12-09T12:05:30",
  "message": "Automation completed successfully"
}
```

### Download Trace File

**Endpoint:** `GET /trace/{task_id}`

Downloads the Playwright trace file as a ZIP.

## 🔧 Configuration

Edit `config.py` or use environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GUARD_USERNAME` | - | Guard portal username |
| `GUARD_PASSWORD` | - | Guard portal password |
| `WEBHOOK_PORT` | 5001 | Webhook server port |
| `BROWSER_HEADLESS` | false | Run browser in headless mode |
| `MAX_WORKERS` | 3 | Max concurrent automation tasks |
| `ENABLE_TRACING` | true | Enable Playwright traces |

## 📝 Implementation Status

### ✅ Complete
- Project structure setup
- Configuration management
- Webhook server with queue system
- Browser session management
- Trace file generation
- Test scripts (local and deployment)
- Logging system

### ⚠️ Needs Implementation
- Guard portal login logic (`guard_login.py`)
- Guard quote/submission automation (`guard_quote.py`)
- Field mappings and selectors
- Form validation logic

## 🛠️ Next Steps

1. **Provide Guard Portal Details:**
   - Login URL
   - Login form selectors
   - Dashboard navigation
   - Quote form structure

2. **Implement Login Logic:**
   - Update `guard_login.py` with actual selectors
   - Handle MFA if required
   - Session persistence

3. **Implement Quote Automation:**
   - Update `guard_quote.py` with form fields
   - Add data transformation logic
   - Handle dropdowns and dynamic fields

4. **Test and Debug:**
   - Run local tests
   - Check trace files for issues
   - Refine selectors

5. **Deploy (Optional):**
   - Railway/Heroku deployment
   - Update `test_and_download_trace.py` with deployment URL

## 📚 Architecture

Similar to Encova automation:

1. **Webhook Server** - Receives requests, manages queue
2. **Login Handler** - Authenticates with Guard portal
3. **Quote Handler** - Fills submission forms
4. **Queue System** - Max 3 concurrent automations
5. **Browser Lock** - Ensures one browser at a time
6. **Trace Files** - Full Playwright recordings for debugging

## 🐛 Debugging

**View logs:**
```powershell
cat logs/webhook_server.log
```

**View traces:**
```powershell
playwright show-trace traces/YOUR_TRACE_FILE.zip
```

**Check screenshots:**
```
logs/screenshots/TASK_ID/
```

## 🤝 Support

This is a template structure. Implementation requires:
- Guard portal access
- Form field selectors
- Login flow details
- Business logic for data transformation

Ready to implement! Provide the Guard portal link and requirements to complete the automation logic.
