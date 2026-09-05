import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import json
import hashlib

PSX_URL = "https://dps.psx.com.pk/performers"
SENT_FILE = "sent_market_performer_alerts.json"

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

pakistan_time = datetime.now(ZoneInfo("Asia/Karachi"))
today = pakistan_time.date()
today_string = today.isoformat()

print("PSX Market Performers Alert Bot Started")
print("Pakistan Date:", today)
print("Pakistan Time:", pakistan_time.strftime("%Y-%m-%d %I:%M:%S %p"))

if not DISCORD_WEBHOOK_URL:
    print("ERROR: DISCORD_WEBHOOK_URL secret is missing.")
    raise SystemExit(1)

# Load sent alerts
if os.path.exists(SENT_FILE):
    try:
        with open(SENT_FILE, "r", encoding="utf-8") as file:
            sent_alerts = set(json.load(file))
    except (json.JSONDecodeError, OSError):
        sent_alerts = set()
else:
    sent_alerts = set()

print("Previously sent alerts:", len(sent_alerts))

# Get PSX performers page
response = None

for attempt in range(1, 4):

    print(f"PSX request attempt: {attempt}")

    try:
        response = requests.get(
            PSX_URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        print("PSX Response Status:", response.status_code)

        if response.status_code == 200:
            break

    except requests.RequestException as error:
        print("Request error:", error)

    time.sleep(5)

if response is None or response.status_code != 200:
    print("PSX performers data could not be retrieved.")
    raise SystemExit(1)

# Parse HTML
soup = BeautifulSoup(response.text, "html.parser")

headings = soup.find_all(
    "h3",
    class_="marketPerf__heading"
)

print("Found performer sections:", len(headings))


def extract_table(heading):

    table_container = heading.find_next(
        "div",
        class_="marketPerf__table"
    )

    if not table_container:
        return []

    table = table_container.find("table")

    if not table:
        return []

    tbody = table.find("tbody")

    if not tbody:
        return []

    rows = tbody.find_all("tr")

    stocks = []

    for row in rows:

        columns = row.find_all("td")

        if len(columns) < 4:
            continue

        symbol_element = columns[0].find("strong")

        if not symbol_element:
            continue

        symbol = symbol_element.get_text(strip=True)

        nc_tag = columns[0].find(
            "div",
            class_="tag"
        )

        nc = ""

        if nc_tag:
            nc = nc_tag.get_text(
                " ",
                strip=True
            )

        price = columns[1].get_text(
            " ",
            strip=True
        )

        change = columns[2].get_text(
            " ",
            strip=True
        )

        change = " ".join(change.split())

        volume = columns[3].get_text(
            " ",
            strip=True
        )

        stocks.append({
            "symbol": symbol,
            "price": price,
            "change": change,
            "volume": volume,
            "nc": nc
        })

    return stocks


# Find sections
top_active = []
top_advancers = []

for heading in headings:

    title = heading.get_text(
        " ",
        strip=True
    ).upper()

    if title == "TOP ACTIVE STOCKS":
        top_active = extract_table(heading)

    elif title == "TOP ADVANCERS":
        top_advancers = extract_table(heading)


print("--------------------------------")
print("TOP ACTIVE STOCKS:", len(top_active))
print("TOP ADVANCERS:", len(top_advancers))
print("--------------------------------")


if not top_active:
    print("ERROR: TOP ACTIVE STOCKS not found.")
    raise SystemExit(1)

if not top_advancers:
    print("ERROR: TOP ADVANCERS not found.")
    raise SystemExit(1)


def build_message(title, stocks):

    lines = [
        title,
        ""
    ]

    for stock in stocks:

        symbol = stock["symbol"]

        if stock["nc"]:
            symbol += f" ({stock['nc']})"

        lines.append(
            f"Symbol: {symbol}"
        )

        lines.append(
            f"Price: {stock['price']}"
        )

        lines.append(
            f"Change: {stock['change']}"
        )

        lines.append(
            f"Volume: {stock['volume']}"
        )

        lines.append("")

    return "\n".join(lines).strip()


active_message = build_message(
    "TOP ACTIVE STOCKS",
    top_active
)

advancers_message = build_message(
    "TOP ADVANCERS",
    top_advancers
)


# ==================================================
# MESSAGE 1 — TOP ACTIVE STOCKS
# ==================================================

active_id = hashlib.sha256(
    f"{today_string}|TOP_ACTIVE_STOCKS".encode("utf-8")
).hexdigest()

if active_id in sent_alerts:

    print("TOP ACTIVE STOCKS already sent today.")

else:

    print("Sending TOP ACTIVE STOCKS...")

    discord_response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": active_message
        },
        timeout=30
    )

    print(
        "TOP ACTIVE Discord status:",
        discord_response.status_code
    )

    if discord_response.status_code in (200, 204):

        print("TOP ACTIVE STOCKS sent successfully.")

        sent_alerts.add(active_id)

    else:

        print("TOP ACTIVE STOCKS failed.")
        print(discord_response.text)

    time.sleep(2)


# ==================================================
# MESSAGE 2 — TOP ADVANCERS
# ==================================================

advancers_id = hashlib.sha256(
    f"{today_string}|TOP_ADVANCERS".encode("utf-8")
).hexdigest()

if advancers_id in sent_alerts:

    print("TOP ADVANCERS already sent today.")

else:

    print("Sending TOP ADVANCERS...")

    discord_response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": advancers_message
        },
        timeout=30
    )

    print(
        "TOP ADVANCERS Discord status:",
        discord_response.status_code
    )

    if discord_response.status_code in (200, 204):

        print("TOP ADVANCERS sent successfully.")

        sent_alerts.add(advancers_id)

    else:

        print("TOP ADVANCERS failed.")
        print(discord_response.text)

    time.sleep(2)


# ==================================================
# SAVE DUPLICATE PREVENTION DATA
# ==================================================

with open(
    SENT_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        sorted(sent_alerts),
        file,
        indent=2
    )

print(
    f"Saved {len(sent_alerts)} sent alerts."
)

print("--------------------------------")
print("PSX Market Performers Alert Bot Finished")
print("--------------------------------")
