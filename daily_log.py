#!/usr/bin/env python3
"""Daily VPS log commit: 1-4 random commits/day, aggregate non-secret stats only."""
import os, random, sqlite3, subprocess, time
from datetime import datetime, timedelta, timezone
WIB = timezone(timedelta(hours=7))
REPO = os.path.dirname(os.path.abspath(__file__))
DB = "/home/ubuntu/tele-apibot/tele_proxy.db"
SVCS = ["tele-apibot", "cloudflared", "hermes-gateway", "9router"]
INTERNAL = (-2, -3, int(os.environ.get("ADMIN_TG_ID", "0")))

def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, cwd=REPO).stdout.strip()

def stats():
    now = datetime.now(WIB)
    # usage_logs.timestamp = naive server time (UTC+8)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
        q = "select count(*), coalesce(sum(total_tokens),0) from usage_logs where timestamp >= ? and telegram_id not in (?,?,?)"
        n, tok = c.execute(q, (start, *INTERNAL)).fetchone(); c.close()
    except Exception as e:
        n, tok = "?", "?"
    svc = {s: sh("systemctl", "is-active", s) or "unknown" for s in SVCS}
    up = sh("uptime", "-p"); load = open("/proc/loadavg").read().split()[:3]
    mem = sh("sh", "-c", "free -m | awk '/Mem/{print $3\"/\"$2\" MB\"}'")
    disk = sh("sh", "-c", "df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}'")
    return now, n, tok, svc, up, load, mem, disk

def snapshot(i, total):
    now, n, tok, svc, up, load, mem, disk = stats()
    day = now.strftime("%Y-%m-%d"); path = f"logs/{now:%Y}/{now:%m}/{day}.md"
    full = os.path.join(REPO, path); os.makedirs(os.path.dirname(full), exist_ok=True)
    new = not os.path.exists(full)
    with open(full, "a") as f:
        if new: f.write(f"# VPS daily log {day}\n")
        f.write(f"\n## {now:%H:%M} WIB (snapshot {i}/{total})\n")
        f.write(f"- uptime: {up}\n- load: {' '.join(load)}\n- mem: {mem}\n- disk: {disk}\n")
        f.write("- services: " + ", ".join(f"{k}={v}" for k, v in svc.items()) + "\n")
        f.write(f"- API requests today: {n}, tokens today: {tok}\n")
    sh("git", "add", path)
    sh("git", "commit", "-q", "-m", f"log: {day} {now:%H:%M} WIB snapshot {i}/{total}")

def main():
    total = random.randint(1, 4)
    sh("git", "pull", "-q", "--rebase", "origin", "main")
    for i in range(1, total + 1):
        snapshot(i, total)
        if i < total and not os.environ.get("NO_SLEEP"):
            time.sleep(random.randint(60, 600))
    r = subprocess.run(["git", "push", "-q", "origin", "main"], capture_output=True, text=True, cwd=REPO)
    print(datetime.now(WIB).strftime("%F %T WIB"), f"commits={total}", "push=ok" if r.returncode == 0 else "push=FAIL " + r.stderr.strip()[:200])

if __name__ == "__main__":
    main()
