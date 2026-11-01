import os
import json
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

API_URL = (
    "https://crtinvqnhpqnhouctmbh.supabase.co"
    "/rest/v1/rpc/load_public_region_site"
)

TIMEZONE = ZoneInfo("America/Chicago")

def main():
    today = datetime.now(TIMEZONE).date()
    monday = today + timedelta(days=(7 - today.weekday()) % 7)
    saturday = monday + timedelta(days=5)

   api_key = os.environ["SUPABASE_API_KEY"]

request = urllib.request.Request(
    API_URL,
    data=json.dumps({"p_region_slug": "aggieland"}).encode(),
    headers={
        "Content-Type": "application/json",
        "apikey": api_key,
    },
    method="POST",
)

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)

    calendar = data.get("calendar", [])
    workouts = [
        item for item in calendar
        if monday.isoformat() <= item.get("date", "") <= saturday.isoformat()
    ]

    workouts.sort(
        key=lambda item: (
            item.get("date", ""),
            item.get("startTime") or "",
            (item.get("ao") or {}).get("name") or "",
        )
    )

    print(f"F3 Aggieland: {monday} through {saturday}")
    print(f"Workouts found: {len(workouts)}")
    print()

    for workout in workouts:
        ao = (workout.get("ao") or {}).get("name", "Unknown AO")
        q = workout.get("qName") or "OPEN"
        emphasis = workout.get("emphasis") or "Unspecified"
        time = workout.get("startTime") or ""

        print(f"{workout['date']} | {time} | {ao} | {q} | {emphasis}")


if __name__ == "__main__":
    main()
