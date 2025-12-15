"""Quick test script for Railway server"""
import requests
import time

RAILWAY_URL = 'https://guardsubmissionbot-production.up.railway.app'

print('=' * 80)
print('GUARD AUTOMATION - RAILWAY SERVER TEST')
print('=' * 80)

# Check health first
print('\n[CHECK] Testing server health...')
try:
    response = requests.get(f'{RAILWAY_URL}/health', timeout=15)
    if response.status_code == 200:
        data = response.json()
        print(f'\n[OK] Server is HEALTHY!')
        print(f'    Service: {data.get("service", "N/A")}')
        print(f'    Active Workers: {data.get("active_workers", "N/A")}/{data.get("max_workers", "N/A")}')
        print(f'    Queue Size: {data.get("queue_size", "N/A")}')
    else:
        print(f'\n[ERROR] Status: {response.status_code}')
        print(response.text)
        exit(1)
except Exception as e:
    print(f'\n[ERROR] Could not connect: {e}')
    exit(1)

# Send automation request with NEW data
print('\n' + '=' * 80)
print('[SENDING REQUEST] New Quote Data')
print('=' * 80)

task_id = f'test_{int(time.time())}'
payload = {
    'action': 'start_automation',
    'task_id': task_id,
    'policy_code': 'TEBP602893',
    'create_account': False,
    'quote_data': {
        'combined_sales': '950000',
        'gas_gallons': '650000',
        'year_built': '2005',
        'square_footage': '5500',
        'mpds': '8'
    }
}

print(f'\n[TASK ID] {task_id}')
print(f'[POLICY] TEBP602893')
print(f'[DATA] Combined Sales: $950,000')
print(f'[DATA] Gas Gallons: 650,000')
print(f'[DATA] Year Built: 2005')
print(f'[DATA] Square Footage: 5,500')
print(f'[DATA] MPDs (Pumps): 8')

try:
    print('\n[SENDING...]')
    response = requests.post(f'{RAILWAY_URL}/webhook', json=payload, timeout=30)
    result = response.json()
    print(f'\n[RESULT] Status: {result.get("status", "N/A")}')
    print(f'[RESULT] Message: {result.get("message", "N/A")}')
    print(f'[RESULT] Task ID: {result.get("task_id", "N/A")}')
    
    if result.get('status') == 'accepted':
        print('\n[SUCCESS] Request accepted! Monitoring task...')
        print('(This will take a few minutes for the automation to complete)')
        
        # Monitor for 5 minutes
        for i in range(60):
            time.sleep(5)
            try:
                status_resp = requests.get(f'{RAILWAY_URL}/task/{task_id}/status', timeout=10)
                if status_resp.status_code == 200:
                    status = status_resp.json()
                    current = status.get('status', 'unknown')
                    elapsed = (i + 1) * 5
                    
                    print(f'[{elapsed:3d}s] Status: {current.upper()}', end='')
                    if status.get('queue_position'):
                        print(f' (Queue: {status["queue_position"]})', end='')
                    print()
                    
                    if current in ['completed', 'success']:
                        print('\n' + '=' * 80)
                        print('[SUCCESS] Task completed!')
                        print('=' * 80)
                        if status.get('message'):
                            print(f'Message: {status["message"]}')
                        break
                    elif current in ['failed', 'error']:
                        print('\n' + '=' * 80)
                        print('[FAILED] Task failed!')
                        print('=' * 80)
                        print(f'Error: {status.get("error", "Unknown error")}')
                        break
            except Exception as e:
                print(f'[WARN] Status check error: {e}')
    else:
        print(f'\n[ERROR] Request not accepted: {result}')
        
except Exception as e:
    print(f'\n[ERROR] {e}')

print('\n' + '=' * 80)
print('[DONE]')
print('=' * 80)

