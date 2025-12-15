# Guard Webhook Integration

## Overview
Guard automation now follows the exact same structure as Encova automation:
1. Webhook receives request → Starts Guard Login
2. Guard Login completes → Automatically triggers Guard Quote
3. Guard Quote completes → Returns result

## Webhook Endpoint

### URL
```
POST http://localhost:5000/guard/quote
```

### Request Payload
```json
{
  "action": "start_automation",
  "task_id": "optional_unique_id",
  "policy_code": "TEBP602893",
  "quote_data": {
    "combined_sales": "800000",
    "gas_gallons": "500000",
    "year_built": "2000",
    "square_footage": "4200",
    "mpds": "6"
  }
}
```

### Response
```json
{
  "status": "accepted",
  "task_id": "guard_TEBP602893_20251215_123456",
  "policy_code": "TEBP602893",
  "message": "Guard automation task started",
  "status_url": "/task/guard_TEBP602893_20251215_123456/status"
}
```

## Quote Data Fields

### Webhook Input Parameters (5 fields):
1. **combined_sales** - Used in 3 places:
   - Total Annual Sales (Liability Limits)
   - Annual Gross Sales (Building Information)
   - Convenience Store Receipts (Class Specific)
   
2. **gas_gallons** - Annual Gallons of Gasoline

3. **year_built** - Year Building was Built

4. **square_footage** - Used in 2 places:
   - Total Building Square Footage
   - Total Square Footage Occupied
   
5. **mpds** - Number of Gas Pumps

### Hardcoded Values (9 fields - same for every automation):
- Damage to Premises: $100,000
- Employees: 10
- Stories: 1 (always 1 story)
- Residential Units: 0
- Vacancy %: 0
- Gas Sales %: 40
- CBD %: 0
- Tobacco %: 10
- Alcohol %: 10

## Architecture

```
Webhook Request → guard_login.run_full_automation()
                      ↓
                 1. Login to Guard Portal
                      ↓
                 2. Close login browser
                      ↓
                 3. Initialize GuardQuote with webhook data
                      ↓
                 4. Run quote automation (all panels)
                      ↓
                 5. Return result
```

## Key Files Modified

### 1. guard_login.py
- Added `run_full_automation()` method (similar to Encova)
- Accepts `policy_code` and `quote_data`
- Handles login → quote flow

### 2. guard_quote.py
- Updated `__init__()` to accept webhook parameters
- All hardcoded values now use instance variables
- Main function shows example usage

### 3. webhook_server.py (in automation folder)
- Added `/guard/quote` endpoint
- Added `run_guard_automation_task()` function
- Updated `worker_thread()` to handle both Encova and Guard tasks

## Testing

### Using cURL:
```bash
curl -X POST http://localhost:5000/guard/quote \
  -H "Content-Type: application/json" \
  -d '{
    "policy_code": "TEBP602893",
    "quote_data": {
      "combined_sales": "800000",
      "gas_gallons": "500000",
      "year_built": "2000",
      "square_footage": "4200",
      "mpds": "6"
    }
  }'
```

### Check Status:
```bash
curl http://localhost:5000/task/{task_id}/status
```

## Session Management
- Uses `task_id="default"` for both login and quote
- Shares browser session between login and quote
- No repeated 2FA on subsequent runs

## Queue System
- Supports up to 3 concurrent browser instances
- Guard and Encova tasks share the same queue
- Browser lock ensures one task at a time per browser_data folder
