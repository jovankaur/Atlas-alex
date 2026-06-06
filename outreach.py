import os
import re
import csv
import time
import smtplib
import requests
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup

# ==========================================
# CONFIG — Fill these in
# ==========================================
SMTP_EMAIL     = os.environ.get("SMTP_EMAIL", "your_gmail@gmail.com")
SMTP_PASSWORD  = os.environ.get("SMTP_PASSWORD", "your_app_password")
YOUR_NAME      = "Jovan"
DAILY_LIMIT    = 20
LOG_FILE       = "contacted.csv"
LEADS_FILE     = "leads_found.csv"

CITIES = [
    "Phoenix Arizona",
    "Dallas Texas",
    "Nashville Tennessee",
    "Charlotte North Carolina",
    "Jacksonville Florida"
]

EMAIL_SUBJECT = "Your website visitors are leaving without talking to anyone"

def email_body(first_name):
    return f"""Hi {first_name},

Most real estate websites lose 70% of visitors because no one's available to respond instantly.

I built Alex — an AI assistant that talks to your visitors 24/7, qualifies them by budget, timeline and location in any language your clients speak and sends you the lead summary immediately.

Try it yourself here: alexai.me

Takes 30 seconds. No signup needed.

If you like what you see, I can have it running on your website within 48 hours.

Worth a quick look?

{YOUR_NAME}"""


# ==========================================
# STEP 1 — LOAD ALREADY CONTACTED
# ==========================================
def load_contacted():
    contacted = set()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    contacted.add(row[0].lower().strip())
    return contacted


def log_contacted(email, name, city):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([email.lower().strip(), name, city, str(datetime.date.today())])


# ==========================================
# STEP 2 — FIND AGENT WEBSITES VIA GOOGLE
# ==========================================
def search_agents(city, num=5):
    """Search Google for solo real estate agents in a city"""
    query = f'solo real estate agent {city} site:*.com -zillow -realtor.com -redfin -trulia -century21 -kw.com'
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num={num}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/url?q=" in href:
                actual = href.split("/url?q=")[1].split("&")[0]
                if actual.startswith("http") and "google" not in actual:
                    links.append(actual)
        
        # Remove duplicates
        seen = set()
        clean = []
        for l in links:
            domain = re.sub(r'https?://(www\.)?', '', l).split('/')[0]
            if domain not in seen:
                seen.add(domain)
                clean.append(l)
        
        return clean[:num]
    
    except Exception as e:
        print(f"  Search error: {e}")
        return []


# ==========================================
# STEP 3 — SCRAPE EMAIL FROM AGENT WEBSITE
# ==========================================
def scrape_email_and_name(url):
    """Visit agent website and extract email + first name"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()
        
        # Find emails — exclude big platform emails
        emails = re.findall(r'[\w.\-]+@[\w.\-]+\.\w{2,4}', text)
        blocked = ["noreply", "support", "info@zillow", "contact@", "admin@", "hello@wordpress"]
        real_emails = [e for e in emails if not any(b in e.lower() for b in blocked)]
        
        email = real_emails[0] if real_emails else None
        
        # Try to find agent first name from page title or h1
        name = "there"
        title = soup.find("title")
        h1 = soup.find("h1")
        
        # Try h1 first
        if h1:
            words = h1.get_text().strip().split()
            if words and words[0].isalpha() and len(words[0]) > 2:
                name = words[0].capitalize()
        elif title:
            words = title.get_text().strip().split()
            if words and words[0].isalpha() and len(words[0]) > 2:
                name = words[0].capitalize()
        
        return email, name
    
    except Exception as e:
        print(f"  Scrape error for {url}: {e}")
        return None, "there"


# ==========================================
# STEP 4 — SEND EMAIL
# ==========================================
def send_email(to_email, first_name):
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Subject"] = EMAIL_SUBJECT
    msg.attach(MIMEText(email_body(first_name), "plain"))
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  Email send failed: {e}")
        return False


# ==========================================
# STEP 5 — SAVE LEADS TO CSV
# ==========================================
def save_lead(name, email, city, website):
    file_exists = os.path.exists(LEADS_FILE)
    with open(LEADS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Name", "Email", "City", "Website", "Date"])
        writer.writerow([name, email, city, website, str(datetime.date.today())])


# ==========================================
# MAIN RUNNER
# ==========================================
def run():
    print("\n🚀 Alex Outreach Tool Starting...")
    print(f"   Daily limit: {DAILY_LIMIT} emails")
    print(f"   Targeting: {', '.join(CITIES)}\n")

    contacted = load_contacted()
    sent_today = 0

    for city in CITIES:
        if sent_today >= DAILY_LIMIT:
            break

        print(f"\n📍 Searching: {city}")
        websites = search_agents(city, num=8)

        if not websites:
            print(f"  No results found for {city}")
            continue

        for site in websites:
            if sent_today >= DAILY_LIMIT:
                break

            print(f"  Checking: {site}")
            email, name = scrape_email_and_name(site)

            if not email:
                print(f"  ❌ No email found")
                continue

            if email.lower() in contacted:
                print(f"  ⏭️  Already contacted: {email}")
                continue

            # Send it
            print(f"  📧 Sending to {name} <{email}>...")
            success = send_email(email, name)

            if success:
                log_contacted(email, name, city)
                save_lead(name, email, city, site)
                contacted.add(email.lower())
                sent_today += 1
                print(f"  ✅ Sent! ({sent_today}/{DAILY_LIMIT})")
                time.sleep(30)  # 30 second gap between emails — avoids spam flags
            else:
                print(f"  ❌ Failed to send")

            time.sleep(5)  # small pause between scrapes

    print(f"\n✅ Done! Sent {sent_today} emails today.")
    print(f"   Check {LEADS_FILE} for full lead list.")


if __name__ == "__main__":
    run()
