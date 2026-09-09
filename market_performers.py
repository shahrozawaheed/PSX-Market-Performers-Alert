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

# ==================================================
# PAKISTAN DATE & TIME
# ==================================================

pakistan_time = datetime.now(ZoneInfo("Asia/Karachi"))
today = pakistan_time.date()
today_string = today.isoformat()

# Display date for Discord title
display_date = pakistan_time.strftime("%B %d, %Y")

print("PSX Market Performers Alert Bot Started")
print("Pakistan Date:", today)
print(
    "Pakistan Time:",
    pakistan_time.strftime("%Y-%m-%d %I:%M:%S %p")
)

# ==================================================
# CHECK DISCORD WEBHOOK
# ==================================================

if not DISCORD_WEBHOOK_URL:
    print("ERROR: DISCORD_WEBHOOK_URL secret is missing.")
    raise SystemExit(1)

# ==================================================
# LOAD SENT ALERTS
# ==================================================

if os.path.exists(SENT_FILE):

    try:
        with open(
            SENT_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            sent_alerts = set(json.load(file))

    except (json.JSONDecodeError, OSError):

        print("Could not read sent alerts file.")
        sent_alerts = set()

else:

    sent_alerts = set()

print("Previously sent alerts:", len(sent_alerts))

# ==================================================
# GET PSX PERFORMERS PAGE
# ==================================================

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

        print(
            "PSX Response Status:",
            response.status_code
        )

        if response.status_code == 200:
            break

        print("PSX request failed. Retrying...")

    except requests.RequestException as error:

        print("Request error:", error)

    if attempt < 3:
        time.sleep(5)

# ==================================================
# CHECK PSX RESPONSE
# ==================================================

if response is None or response.status_code != 200:

    print(
        "PSX performers data could not be retrieved."
    )

    raise SystemExit(1)

# ==================================================
# PARSE HTML
# ==================================================

soup = BeautifulSoup(
    response.text,
    "html.parser"
)

headings = soup.find_all(
    "h3",
    class_="marketPerf__heading"
)

print(
    "Found performer sections:",
    len(headings)
)

# ==================================================
# EXTRACT TABLE DATA
# ==================================================

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

        # Keep symbol exactly as PSX provides it
        symbol = symbol_element.get_text(
            strip=True
        )

        # NC tag
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

        # Keep values exactly as PSX provides them
        price = columns[1].get_text(
            " ",
            strip=True
        )

        change = columns[2].get_text(
            " ",
            strip=True
        )

        change = " ".join(
            change.split()
        )

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


# ==================================================
# FIND TOP ACTIVE & TOP ADVANCERS
# ==================================================

top_active = []
top_advancers = []

for heading in headings:

    title = heading.get_text(
        " ",
        strip=True
    ).upper()

    if title == "TOP ACTIVE STOCKS":

        top_active = extract_table(
            heading
        )

    elif title == "TOP ADVANCERS":

        top_advancers = extract_table(
            heading
        )

# ==================================================
# PRINT RESULTS
# ==================================================

print("--------------------------------")
print(
    "TOP ACTIVE STOCKS:",
    len(top_active)
)
print(
    "TOP ADVANCERS:",
    len(top_advancers)
)
print("--------------------------------")

# ==================================================
# VALIDATE DATA
# ==================================================

if not top_active:

    print(
        "ERROR: TOP ACTIVE STOCKS not found."
    )

    raise SystemExit(1)

if not top_advancers:

    print(
        "ERROR: TOP ADVANCERS not found."
    )

    raise SystemExit(1)

# ==================================================
# CREATE UNIQUE ID FOR TODAY'S DATA
# ==================================================

active_data = json.dumps(
    top_active,
    sort_keys=True
)

advancers_data = json.dumps(
    top_advancers,
    sort_keys=True
)

combined_data = (
    f"{today_string}|"
    f"{active_data}|"
    f"{advancers_data}"
)

alert_id = hashlib.sha256(
    combined_data.encode("utf-8")
).hexdigest()

# ==================================================
# CHECK DUPLICATE
# ==================================================

if alert_id in sent_alerts:

    print(
        "Today's Market Performers alert "
        "has already been sent."
    )

    raise SystemExit(0)

# ==================================================
# BUILD ONE DISCORD MESSAGE
# ==================================================

message = (
    f"**Market Performers | {display_date}**\n\n"
)

# ==================================================
# TOP ACTIVE STOCKS
# ==================================================

message += "**TOP ACTIVE STOCKS**\n\n"

for stock in top_active:

    symbol = stock["symbol"]

    if stock["nc"]:

        symbol += f" ({stock['nc']})"

    message += (
        f"{symbol}\n"
        f"Price: {stock['price']} | "
        f"Change: {stock['change']} | "
        f"Volume: {stock['volume']}\n\n"
    )

# ==================================================
# TOP ADVANCERS
# ==================================================

message += "**TOP ADVANCERS**\n\n"

for stock in top_advancers:

    symbol = stock["symbol"]

    if stock["nc"]:

        symbol += f" ({stock['nc']})"

    message += (
        f"{symbol}\n"
        f"Price: {stock['price']} | "
        f"Change: {stock['change']} | "
        f"Volume: {stock['volume']}\n\n"
    )

# ==================================================
# SEND ONE DISCORD MESSAGE
# ==================================================

print(
    "Sending combined Market Performers message..."
)

discord_response = requests.post(
    DISCORD_WEBHOOK_URL,
    json={
        "content": message,
        "flags": 4
    },
    timeout=30
)

print(
    "Discord response:",
    discord_response.status_code
)

# ==================================================
# SAVE DUPLICATE PREVENTION DATA
# ==================================================

if discord_response.status_code in (200, 204):

    print(
        f"Successfully sent "
        f"{len(top_active) + len(top_advancers)} "
        "stocks in ONE Discord message."
    )

    sent_alerts.add(alert_id)

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

else:

    print(
        "Failed to send Market Performers message."
    )

    print(
        discord_response.text
    )

    # Important:
    # Do NOT save alert_id if Discord failed.

    raise SystemExit(1)

# ==================================================
# FINISHED
# ==================================================

print("--------------------------------")
print(
    "PSX Market Performers Alert Bot Finished"
)
print("--------------------------------")
```
