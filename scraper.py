import requests
import time
import os
import json
from datetime import date, timedelta

BASE_URL = "https://duanxianxia.cn"
def _load_credentials():
    username = os.environ.get("DXX_USERNAME")
    password = os.environ.get("DXX_PASSWORD")
    if username and password:
        return username, password
    cred_file = os.path.expanduser("~/.claude/duanxianxia_credentials.json")
    with open(cred_file) as f:
        c = json.load(f)
    return c["username"], c["password"]

COOKIE_FILE = os.path.join(os.path.dirname(__file__), ".cookie_cache")

_session = None


def _login():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/web/login",
    })
    username, password = _load_credentials()
    r = s.post(BASE_URL + "/api/userLogin", data={"username": username, "password": password}, timeout=10)
    r.raise_for_status()
    if r.json().get("result") != "success":
        raise RuntimeError("登录失败")
    cookie_str = "; ".join(f"{c.name}={c.value}" for c in s.cookies)
    try:
        with open(COOKIE_FILE, "w") as f:
            f.write(cookie_str)
    except OSError:
        pass
    s.headers["Cookie"] = cookie_str
    return s


def _get_session():
    global _session
    if _session is not None:
        return _session
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/web/longhu/4ac6af32a6ffc014",
    })
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            s.headers["Cookie"] = f.read().strip()
    _session = s
    return _session


def get_lhb(date_str):
    global _session
    for attempt in range(2):
        try:
            r = _get_session().post(
                BASE_URL + "/api/getLhbByStock",
                data={"date": date_str},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data:
                return data
            # null 或空列表说明 cookie 失效，重新登录
            if attempt == 0:
                _session = _login()
        except Exception:
            if attempt == 0:
                try:
                    _session = _login()
                except Exception:
                    pass
    return []


def fetch_multi_day_lhb():
    trading_days = []
    day_data = {}
    d = date.today()
    while len(trading_days) < 30 and (date.today() - d).days < 60:
        if d.weekday() < 5:
            date_str = d.strftime("%Y-%m-%d")
            data = get_lhb(date_str)
            time.sleep(0.5)
            if data:
                trading_days.append(date_str)
                day_data[date_str] = data
        d -= timedelta(days=1)

    stock_map = {}
    for date_str in trading_days:
        data = day_data[date_str]
        seen = set()
        for item in data:
            code = item["info"]["code"]
            if code in seen:
                continue
            seen.add(code)
            name = item["info"]["name"]
            if code.startswith("9") or "ST" in name.upper():
                continue
            if code not in stock_map:
                stock_map[code] = {"name": name, "code": code, "appearances": []}
            stock_map[code]["appearances"].append({"date": date_str, "zf": item["info"]["zf"]})

    result = list(stock_map.values())
    result.sort(key=lambda x: -len(x["appearances"]))
    return result, trading_days


if __name__ == "__main__":
    from datetime import datetime
    result, trading_days = fetch_multi_day_lhb()
    os.makedirs("data", exist_ok=True)
    with open("data/data.json", "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trading_days": trading_days,
            "data": result,
        }, f, ensure_ascii=False, indent=2)
