import schedule
import time
import outreach

def job():
    print("Running daily outreach...")
    outreach.run()

# Runs every day at 9am US Central
schedule.every().day.at("09:00").do(job)

print("Scheduler started. Waiting...")
while True:
    schedule.run_pending()
    time.sleep(60)
