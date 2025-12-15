# Guard Webhook Server - Usage Guide

## Overview
The Guard webhook server provides two automation flows:
1. **Use existing policy code** - Run quote automation on an existing account
2. **Create new account** - Create a new account, get policy code, then run quote automation

## Server Details
- **Port**: 5001 (Encova uses 5000)
- **Webhook Endpoint**: `POST http://localhost:5001/webhook`
- **Health Check**: `GET http://localhost:5001/health`
- **Task Status**: `GET http://localhost:5001/task/{task_id}/status`
- **Queue Status**: `GET http://localhost:5001/queue/status`

## Starting the Server

```powershell
cd "C:\Users\Dell\Desktop\RPA For a\guard_automation"
python webhook_server.py
```

The server will:
- Initialize 3 worker threads
- Listen on port 5001
- Use ONE browser at a time (browser lock prevents conflicts)
- Save logs to `logs/webhook_server.log`

## Testing Locally

```powershell
# In a new terminal
python test_webhook_local.py
```

You'll be prompted to choose:
1. Use existing policy code (TEBP602893)
2. Create new account (generates new policy code)

## Webhook Payload Formats

### Option 1: Use Existing Policy Code

```json
{
  "action": "start_automation",
  "task_id": "optional_unique_id",
  "policy_code": "TEBP602893",
  "create_account": false,
  "quote_data": {
    "combined_sales": "800000",
    "gas_gallons": "500000",
    "year_built": "2000",
    "square_footage": "4200",
    "mpds": "6"
  }
}
```

### Option 2: Create New Account

```json
{
  "action": "start_automation",
  "task_id": "optional_unique_id",
  "create_account": true,
  "quote_data": {
    "combined_sales": "800000",
    "gas_gallons": "500000",
    "year_built": "2000",
    "square_footage": "4200",
    "mpds": "6"
  }
}
```

**Note**: When `create_account: true`, the `policy_code` field is NOT required. The system will:
1. Login to Guard portal
2. Create a new account using the account creation form
3. Extract the policy code and quotation URL
4. Run quote automation with the new policy code

## Response Format

### Immediate Response (202 Accepted)

```json
{
  "status": "accepted",
  "task_id": "guard_new_20251215_220000",
  "policy_code": "TEBP602893",
  "message": "Guard automation task started",
  "status_url": "/task/guard_new_20251215_220000/status"
}
```

### Task Status Response

```json
{
  "status": "running",
  "task_id": "guard_new_20251215_220000",
  "policy_code": "TEBP602893",
  "quotation_url": "https://gigezrate.guard.com/...",
  "started_at": "2025-12-15T22:00:00",
  "queue_position": 0
}
```

When `create_account: true`, the status will include:
- `policy_code`: The newly created policy code
- `quotation_url`: The URL for the new account

## Quote Data Parameters

### Required from Webhook (5 parameters)
1. **combined_sales** - Inside Sales / Annual Sales / Convenience Store Receipts
2. **gas_gallons** - Annual Gallons of Gasoline
3. **year_built** - Year building was built
4. **square_footage** - Total building square footage
5. **mpds** - Number of Gas Pumps (Motor Fuel Dispensers)

### Hardcoded in System (9 parameters)
1. **damage_to_premises**: $100,000
2. **employees**: 10
3. **stories**: 1
4. **residential_units**: 0
5. **vacancy_percent**: 0
6. **gas_sales_percent**: 40
7. **cbd_percent**: 0
8. **tobacco_percent**: 10
9. **alcohol_percent**: 10

## Automation Flow

### Flow 1: Existing Policy Code
```
Webhook Request
  ↓
Worker picks up task
  ↓
GuardLogin.run_full_automation()
  ├─ init_browser()
  ├─ login() with 2FA
  ├─ close browser
  ├─ GuardQuote.init_browser()
  ├─ GuardQuote.login() (uses cached session)
  ├─ navigate_to_quote(policy_code)
  ├─ fill_quote_details()
  │   ├─ Policy Information panel
  │   ├─ Location panel
  │   ├─ Liability Limits panel
  │   ├─ Policy Level Coverages panel
  │   ├─ Additional Insureds panel
  │   ├─ Location Information panel
  │   ├─ Windstorm/Hail panel
  │   ├─ Building Information panel (20 fields)
  │   ├─ State Specific panel
  │   └─ Class Specific panel (18 fields)
  └─ close browser
```

### Flow 2: Create New Account
```
Webhook Request (create_account: true)
  ↓
Worker picks up task
  ↓
GuardLogin.init_browser()
  ↓
GuardLogin.login() with 2FA
  ↓
GuardLogin.setup_account()
  ├─ Fill Industry Type: "Retail BOP"
  ├─ Fill "Gasoline Station"
  ├─ Click CONTINUE
  ├─ Fill Agent Information
  ├─ Fill Account Information
  ├─ Fill Prospect Information
  ├─ Click CREATE PROSPECT
  ├─ Extract policy_code and quotation_url
  └─ Return {policy_code, quotation_url}
  ↓
GuardLogin.close()
  ↓
GuardLogin.run_full_automation(policy_code)
  └─ (Same flow as Flow 1)
```

## Error Handling

The system tracks errors at multiple levels:

### Task Status: "failed"
```json
{
  "status": "failed",
  "task_id": "guard_new_20251215_220000",
  "error": "Account creation failed",
  "failed_at": "2025-12-15T22:01:00"
}
```

### Task Status: "error"
```json
{
  "status": "error",
  "task_id": "guard_new_20251215_220000",
  "error": "'NoneType' object has no attribute 'goto'",
  "error_type": "AttributeError",
  "traceback": "...",
  "failed_at": "2025-12-15T22:01:00"
}
```

## Session Management

- Uses `task_id="default"` for session sharing
- Browser data stored in: `sessions/browser_data_default/`
- Cookies and login state persisted across runs
- Trace files saved to: `traces/default.zip`
- Screenshots saved to: `logs/screenshots/default/`

## Concurrent Execution

- **Max Workers**: 3 (configurable in config.py)
- **Browser Lock**: Only ONE browser runs at a time
- **Queue System**: Tasks wait if browser is in use
- **Task Tracking**: Each task has unique ID and status

## Monitoring

### Health Check
```bash
curl http://localhost:5001/health
```

Response:
```json
{
  "status": "healthy",
  "service": "guard-automation",
  "timestamp": "2025-12-15T22:00:00",
  "active_workers": 0,
  "max_workers": 3,
  "queue_size": 0
}
```

### Queue Status
```bash
curl http://localhost:5001/queue/status
```

Response:
```json
{
  "queue_size": 2,
  "active_workers": 1,
  "max_workers": 3,
  "browser_in_use": true
}
```

## Logs and Traces

- **Server Logs**: `logs/webhook_server.log`
- **Trace Files**: `traces/{task_id}.zip` or `traces/default.zip`
- **Screenshots**: `logs/screenshots/{task_id}/`

View trace files:
```bash
playwright show-trace traces/default.zip
```

## Next.js Integration

From your Next.js app, call the webhook:

```typescript
const response = await fetch('http://localhost:5001/webhook', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    action: 'start_automation',
    create_account: true, // or false with policy_code
    quote_data: {
      combined_sales: '800000',
      gas_gallons: '500000',
      year_built: '2000',
      square_footage: '4200',
      mpds: '6'
    }
  })
});

const { task_id, status_url } = await response.json();

// Poll for status
const statusResponse = await fetch(`http://localhost:5001${status_url}`);
const status = await statusResponse.json();
console.log(status.policy_code); // New policy code
console.log(status.quotation_url); // New quotation URL
```

## Deployment Notes

For production deployment:
1. Update `WEBHOOK_HOST` in config.py
2. Use a production WSGI server (gunicorn, waitress)
3. Set up proper CORS origins
4. Configure reverse proxy (nginx)
5. Set `BROWSER_HEADLESS = True` for server environments
6. Set up log rotation for webhook_server.log
7. Monitor queue size and worker utilization

## Comparison with Encova

Both Guard and Encova webhooks share the same architecture:

| Feature | Encova (Port 5000) | Guard (Port 5001) |
|---------|-------------------|-------------------|
| Flask Server | ✅ | ✅ |
| Queue System | ✅ | ✅ |
| Worker Threads | ✅ | ✅ |
| Browser Lock | ✅ | ✅ |
| Task Tracking | ✅ | ✅ |
| CORS Support | ✅ | ✅ |
| Account Creation | ❌ | ✅ |
| Session Persistence | ✅ | ✅ |
| Trace Files | ✅ | ✅ |

The key difference is Guard supports **account creation** flow, which creates a new account first and returns the policy code.
