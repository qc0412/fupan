from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import fetch_multi_day_lhb
from datetime import datetime
import atexit

app = Flask(__name__)
_cache = {"data": [], "trading_days": [], "updated_at": ""}

def refresh():
    data, days = fetch_multi_day_lhb()
    _cache["data"] = data
    _cache["trading_days"] = days
    _cache["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

refresh()

scheduler = BackgroundScheduler()
scheduler.add_job(refresh, "cron", hour=18, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def index():
    return render_template("index.html", **_cache)

if __name__ == "__main__":
    app.run(debug=False, port=5002)
