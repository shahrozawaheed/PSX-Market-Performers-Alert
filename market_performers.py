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

# Pakistan time
pakistan_time = datetime.now(ZoneInfo("Asia/Karachi"))
today = pakistan_time.date()
today_string = today.isoformat()

print("PSX Market Performers Alert Bot Started")
print("Pakistan Date:", today)
print("Pakistan Time:", pakistan_time.strftime("%Y-%m-%d %I:%M:%S %p"))

if not DISCORD_WEBHOOK_URL:
    print("ERROR: DISCORD_WEBHOOK_URL secret is missing.")
    raise SystemExit(1)


# --------------------------------------------------
# Load previously sent alerts
# --------------------------------------------------

if os.path.exists(SENT_FILE):

    try:
        with open(SENT_FILE, "r", encoding="utf-8") as file:
            sent_alerts = set(json.load(file))

    except (json.JSONDecodeError, OSError):

        print("Could not read sent_market_performer_alerts.json.")
        sent_alerts = set()

else:

    sent_alerts = set()

print("Previously sent alerts:", len(sent_alerts))


# --------------------------------------------------
# Get PSX performers page
# --------------------------------------------------

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

        print("PSX request failed. Retrying...")

    except requests.RequestException as error:

        print("Request error:", error)

    time.sleep(5)


if response is None or response.status_code != 200:

    print("PSX performers data could not be retrieved.")
    raise SystemExit(1)


# --------------------------------------------------
# Parse HTML
# --------------------------------------------------

soup = BeautifulSoup(response.text, "html.parser")

headings = soup.find_all(
    "h3",
    class_="marketPerf__heading"
)

print("Found performer sections:", len(headings))


# --------------------------------------------------
# Extract a performers table
# --------------------------------------------------

def extract_table(heading):

    table_container = heading.find_next(
        "div",
        class_="marketPerf__table"
    )

    if not table_container:

        print(
            f"Table container not found for: "
            f"{heading.get_text(strip=True)}"
        )

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

        # Symbol
        symbol_element = columns[0].find(
            "strong"
        )

        if not symbol_element:
            continue

        symbol = symbol_element.get_text(strip=True)

        # Check for NC tag
        nc_tag = columns[0].find(
            "div",
            class_="tag"
        )

        nc = ""

        if nc_tag:
            nc = nc_tag.get_text(" ", strip=True)

        # Price
        price = columns[1].get_text(
            " ",
            strip=True
        )

        # Change
        change = columns[2].get_text(
            " ",
            strip=True
        )

        # Remove icon text / extra whitespace
        change = " ".join(change.split())

        # Volume
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


# --------------------------------------------------
# Find required sections
# --------------------------------------------------

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

    print("ERROR: TOP ACTIVE STOCKS data not found.")
    raise SystemExit(1)

if not top_advancers:

    print("ERROR: TOP ADVANCERS data not found.")
    raise SystemExit(1)


# --------------------------------------------------
# Build Discord message
# --------------------------------------------------

def build_message(title, stocks):

    lines = [title, ""]

    for stock in stocks:

        symbol_line = f"Symbol: {stock['symbol']}"

        if stock["nc"]:
            symbol_line += f" ({stock['nc']})"

        lines.append(symbol_line)
        lines.append(f"Price: {stock['price']}")
        lines.append(f"Change: {stock['change']}")
        lines.append(f"Volume: {stock['volume']}")
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


# --------------------------------------------------
# Send exactly ONE message per category per day
# --------------------------------------------------

categories = [
    (
        "TOP_ACTIVE_STOCKS",
        active_message
    ),
    (
        "TOP_ADVANCERS",
        advancers_message
    )
]

new_alerts_sent = False


for category, message in categories:

    # One alert per category per day
    unique_string = f"{today_string}|{category}"

    alert_id = hashlib.sha256(
        unique_string.encode("utf-8")
    ).hexdigest()

    if alert_id in sent_alerts:

        print(
            f"SKIPPED duplicate: "
            f"{category} for {today_string}"
        )

        continue

    print("--------------------------------")
    print(f"Sending: {category}")
    print("--------------------------------")

    discord_response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": message
        },
        timeout=30
    )

    print(
        f"Discord response for {category}: "
        f"{discord_response.status_code}"
    )

    if discord_response.status_code in (200, 204):

        print(
            f"Successfully sent {category}."
        )

        sent_alerts.add(alert_id)
        new_alerts_sent = True

    else:

        print(
            f"Failed to send {category}."
        )

        print(discord_response.text)

    time.sleep(1)


# --------------------------------------------------
# Save duplicate prevention data
# --------------------------------------------------

if new_alerts_sent:

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
        f"Saved {len(sent_alerts)} sent alerts "
        f"to {SENT_FILE}"
    )

else:

    print("No new alerts were sent.")


print("--------------------------------")
print("PSX Market Performers Alert Bot Finished")
print("--------------------------------")
