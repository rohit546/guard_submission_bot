"""
Configuration file for Guard automation
Stores paths, credentials, and settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
TRACE_DIR = BASE_DIR / "traces"
SESSION_DIR = BASE_DIR / "sessions"
SCREENSHOT_DIR = LOG_DIR / "screenshots"
DEBUG_DIR = BASE_DIR / "debug"

# Create directories if they don't exist
for directory in [LOG_DIR, TRACE_DIR, SESSION_DIR, SCREENSHOT_DIR, DEBUG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Guard credentials (from environment variables)
GUARD_USERNAME = os.getenv('GUARD_USERNAME', '')
GUARD_PASSWORD = os.getenv('GUARD_PASSWORD', '')

# Webhook server settings
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', '0.0.0.0')
# Railway provides PORT env var automatically, fall back to 5001 for local dev
WEBHOOK_PORT = int(os.getenv('PORT', os.getenv('WEBHOOK_PORT', 5001)))
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/webhook')

# Browser settings
# Auto-detect headless mode: if no DISPLAY (server environment), force headless
_headless_env = os.getenv('BROWSER_HEADLESS', 'auto').lower()
if _headless_env == 'auto':
    # Auto-detect: headless if no DISPLAY or running on Railway/Docker
    BROWSER_HEADLESS = not os.getenv('DISPLAY') or os.getenv('RAILWAY_ENVIRONMENT') or os.path.exists('/.dockerenv')
elif _headless_env in ('true', '1', 'yes'):
    BROWSER_HEADLESS = True
else:
    BROWSER_HEADLESS = False
BROWSER_TIMEOUT = int(os.getenv('BROWSER_TIMEOUT', 60000))  # 60 seconds

# Guard portal URL
GUARD_LOGIN_URL = os.getenv('GUARD_LOGIN_URL', 'https://gigezrate.guard.com/auth')

# Max concurrent workers
MAX_WORKERS = int(os.getenv('MAX_WORKERS', 3))

# Trace settings
ENABLE_TRACING = os.getenv('ENABLE_TRACING', 'true').lower() == 'true'
TRACE_SCREENSHOTS = True
TRACE_SNAPSHOTS = True

# File cleanup settings (in days)
CLEANUP_LOGS_DAYS = int(os.getenv('CLEANUP_LOGS_DAYS', 7))
CLEANUP_TRACES_DAYS = int(os.getenv('CLEANUP_TRACES_DAYS', 30))
CLEANUP_SESSIONS_DAYS = int(os.getenv('CLEANUP_SESSIONS_DAYS', 7))

print(f"Guard Automation Config Loaded:")
print(f"  - Base Directory: {BASE_DIR}")
print(f"  - Logs: {LOG_DIR}")
print(f"  - Traces: {TRACE_DIR}")
print(f"  - Sessions: {SESSION_DIR}")
print(f"  - Webhook Port: {WEBHOOK_PORT}")
print(f"  - Browser Headless: {BROWSER_HEADLESS}")
print(f"  - Max Workers: {MAX_WORKERS}")
