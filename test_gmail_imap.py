"""
Test script to fetch recent emails from Gmail using IMAP
This will help verify your app password works and can read Guard verification emails
"""
import imaplib
import email
from email.header import decode_header
from datetime import datetime

from guard_login import _get_email_body, extract_guard_verification_code

# Your Gmail credentials
GMAIL_USER = "zara@mckinneyandco.com"  # Replace with your full email
GMAIL_APP_PASSWORD = "gqlv wrxq peqb esrg"  # Your app password (remove spaces)

# Remove spaces from app password
GMAIL_APP_PASSWORD = GMAIL_APP_PASSWORD.replace(" ", "")

print("=" * 80)
print("TESTING GMAIL IMAP CONNECTION")
print("=" * 80)

try:
    # Connect to Gmail IMAP server
    print("\n[1] Connecting to Gmail IMAP server...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    print("✅ Connected to imap.gmail.com:993")
    
    # Login with app password
    print(f"\n[2] Logging in as: {GMAIL_USER}")
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    print("✅ Login successful!")
    
    # Select inbox
    print("\n[3] Selecting INBOX...")
    mail.select("INBOX")
    print("✅ INBOX selected")
    
    # Search for recent emails (all emails, then filter)
    print("\n[4] Searching for recent emails...")
    status, messages = mail.search(None, "ALL")
    
    if status != "OK":
        print("❌ Failed to search emails")
        exit(1)
    
    # Get list of email IDs
    email_ids = messages[0].split()
    
    # Get last 10 emails (to catch Guard verification email)
    recent_emails = email_ids[-10:] if len(email_ids) >= 10 else email_ids
    
    print(f"✅ Found {len(email_ids)} total emails")
    print(f"📧 Fetching last {len(recent_emails)} emails (looking for Guard verification)...\n")
    
    print("=" * 80)
    
    guard_emails_found = 0
    
    for i, email_id in enumerate(reversed(recent_emails), 1):
        # Fetch email
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        
        if status != "OK":
            print(f"❌ Failed to fetch email {email_id}")
            continue
        
        # Parse email
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Decode subject
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()
                
                # Get sender
                from_email = msg.get("From")
                
                # Skip if not from Guard
                if "guard" not in from_email.lower() and "guard" not in subject.lower():
                    continue
                
                guard_emails_found += 1
                
                # Get date
                date = msg.get("Date")
                
                body = _get_email_body(msg)
                verification_code = extract_guard_verification_code(body)
                
                print(f"\n📧 EMAIL #{i}")
                print("-" * 80)
                print(f"From:    {from_email}")
                print(f"Subject: {subject}")
                print(f"Date:    {date}")
                print(f"\nBody Preview (first 200 chars):")
                print(body[:200].replace("\n", " ").replace("\r", ""))
                
                if verification_code:
                    print(f"\n🔑 VERIFICATION CODE FOUND: {verification_code}")
                else:
                    print("\n⚠️  No 6-digit code found in email")
                
                print("-" * 80)
    
    if guard_emails_found == 0:
        print("\n⚠️  No Guard verification emails found in last 10 emails")
        print("Tip: Try logging into Guard portal to trigger a new verification email")
    else:
        print(f"\n✅ Found {guard_emails_found} Guard email(s)!")
    
    print("\n✅ Test completed successfully!")
    
    # Close connection
    mail.close()
    mail.logout()
    print("\n[5] Logged out from Gmail")
    
except imaplib.IMAP4.error as e:
    print(f"\n❌ IMAP Error: {e}")
    print("\nPossible issues:")
    print("1. Wrong email address")
    print("2. Wrong app password")
    print("3. IMAP not enabled in Gmail settings")
    print("4. Need to enable 'Less secure app access'")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
