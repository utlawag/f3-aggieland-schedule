"""Render F3 Aggieland's next Monday-Saturday Q schedule as a PNG."""
import base64
import html
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

API_URL = "https://crtinvqnhpqnhouctmbh.supabase.co/rest/v1/rpc/load_public_region_site"
TZ = ZoneInfo("America/Chicago")
OUTPUT = Path("weekly_schedule_v2.png")
WIDTH = 1650

AO_COLORS = {
    "the cave": "#4169E1", "the forest": "#35B54A", "the keep": "#C9A227",
    "the rock": "#B88752", "the mine": "#0ABAB5", "the iron": "#C0C0C0",
    "the watch": "#FF4141", "southie": "#F57C00",
    "the pit stop": "#F5FF00", "f3 franklin": "#B388FF",
    "convergence": "#F5F5F5", "f3 dads": "#B8F36B",
    "f3 navasota": "#FF9270",
}
EMPHASIS = {
    "heavy": ("🏋️", "Heavy"), "upper": ("💪", "Upper"),
    "lower": ("🦵", "Lower"), "cardio": ("❤️", "Cardio"),
    "ruck": ("🎒", "Ruck"), "core": ("🆎", "Core"),
    "30/30": ("💡", "30/30"), "stairs": ("🗼", "Stairs"),
    "bootcamp": ("🛡️", "Bootcamp"),
    "benchmark": ("📋", "Benchmark"),
    "murph training": ("🏅", "Murph Training"),
}
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def emphasis_icon(value):
    key = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    if key in ("", "unspecified", "none", "null"):
        key = "bootcamp"
    return EMPHASIS.get(key, ("⭕", "Other"))[0]


def next_monday(now):
    # On Sundays select tomorrow. On other days select the next future Monday.
    today = now.date()
    delta = (7 - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def fetch_schedule():
    key = os.environ["SUPABASE_API_KEY"]
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({"p_region_slug": "aggieland"}).encode("utf-8"),
        headers={"Content-Type": "application/json", "apikey": key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if not isinstance(result, dict) or not isinstance(result.get("calendar"), list):
        raise RuntimeError("Q App API did not return calendar[]")
    return result


def time_label(raw):
    raw = str(raw or "").strip()
    if not raw:
        return "TIME TBD"
    try:
        # Q App may use compact 24-hour times (0530) or colon times (05:30).
        if raw.isdigit():
            parsed = datetime.strptime(raw.zfill(4), "%H%M")
        else:
            parsed = datetime.strptime(raw, "%H:%M")
        return parsed.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return raw


def date_range_label(monday, saturday):
    if monday.month == saturday.month:
        return f"{monday.strftime('%B')} {monday.day}–{saturday.day}, {monday.year}"
    return f"{monday.strftime('%B')} {monday.day} – {saturday.strftime('%B')} {saturday.day}, {saturday.year}"


def workout_html(item):
    ao = str((item.get("ao") or {}).get("name") or "Unknown AO")
    q = str(item.get("qName") or "OPEN").strip() or "OPEN"
    is_open = q.upper() == "OPEN"
    color = AO_COLORS.get(ao.casefold(), "#F5F5F5")
    return (
        '<div class="workout">'
        f'<span class="ao" style="color:{color}">{html.escape(ao.upper())}</span>'
        f' <span class="emoji">{emphasis_icon(item.get("emphasis"))}</span>'
        f' <span class="hyphen">-</span> '
        f'<span class="q{" open" if is_open else ""}">{html.escape("OPEN" if is_open else q)}</span>'
        '</div>'
    )


def panel_html(day, day_date, workouts):
    groups = defaultdict(list)
    for item in workouts:
        groups[time_label(item.get("startTime"))].append(item)
    # Consistent chronological order; unknown times at bottom.
    def sort_key(label):
        try:
            return (0, datetime.strptime(label, "%I:%M %p").hour * 60 + datetime.strptime(label, "%I:%M %p").minute)
        except ValueError:
            try:
                return (0, datetime.strptime(label, "%I:%M %p".replace("%I", "%-I")).hour * 60)
            except Exception:
                try:
                    return (0, datetime.strptime(label, "%I:%M %p").hour)
                except ValueError:
                    return (1, 0)
    # Python's %I accepts non-zero-padded hour on common runners.
    contents = []
    def ao_sort(item):
        name = str((item.get("ao") or {}).get("name") or "").casefold()
        return (name in {"f3 franklin", "f3 navasota"}, name)

    for label in sorted(groups, key=sort_key):
        entries = "".join(workout_html(row) for row in sorted(groups[label], key=ao_sort))
        contents.append(f'<div class="timegroup"><div class="time">{html.escape(label)}</div><div class="entries">{entries}</div></div>')
    if not contents:
        contents = ['<div class="empty">No workouts scheduled</div>']
    return (
        '<section class="panel">'
        f'<div class="dayline"><h2>{day.upper()}</h2><span>{day_date.strftime("%b").upper()} {day_date.day}</span></div>'
        + "".join(contents) + '</section>'
    )


def build_html(monday, workouts):
    by_day = defaultdict(list)
    for item in workouts:
        by_day[item["date"]].append(item)
    for rows in by_day.values():
        rows.sort(key=lambda it: (it.get("startTime") or "99:99", (it.get("ao") or {}).get("name") or ""))
    # Three across, two down: Monday/Tuesday/Wednesday, then Thursday/Friday/Saturday.
    panels = [
        panel_html(DAYS[index], monday + timedelta(days=index),
                   by_day[(monday + timedelta(days=index)).isoformat()])
        for index in range(6)
    ]
    legend = [
        ("🏋️", "Heavy"), ("💪", "Upper"), ("🦵", "Lower"), ("❤️", "Cardio"),
        ("🎒", "Ruck"), ("🆎", "Core"), ("💡", "30/30"), ("🗼", "Stairs"),
        ("🛡️", "Bootcamp"), ("🏅", "Murph Training"), ("📋", "Benchmark"), ("⭕", "Other"),
    ]
    legend_html = "".join(f'<span class="legend-item"><span class="emoji">{e}</span><span>{html.escape(label)}</span></span>' for e, label in legend)
    logo_path = Path("f3-logo.png")
    if not logo_path.is_file():
        raise FileNotFoundError("Expected f3-logo.png at the repository root")
    logo_uri = "data:image/png;base64," + base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><style>
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#090a0c; color:#f5f5f5; font-family:Arial,"DejaVu Sans",sans-serif; }}
.canvas {{ width:{WIDTH}px; padding:34px 42px 35px; }}
header {{ text-align:center; padding:0 0 20px; }}
.brand {{ display:flex; align-items:center; justify-content:center; gap:12px; }}
.brand img {{ width:68px; height:68px; object-fit:contain; }}
h1 {{ margin:0; font-size:62px; font-weight:900; letter-spacing:1.7px; line-height:1.05; }}
.subtitle {{ font-size:30px; letter-spacing:3px; font-weight:700; margin:7px 0 5px; }}
.dates {{ color:#cdced2; font-size:25px; }}
.grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px 20px; align-items:stretch; }}
.panel {{ background:#17181b; border:2px solid #37393e; border-radius:15px; padding:17px 20px 21px; min-width:0; }}
.dayline {{ display:flex; justify-content:space-between; align-items:baseline; border-bottom:2px solid #383a40; margin-bottom:11px; padding-bottom:9px; }}
h2 {{ margin:0; font-size:32px; line-height:1.2; letter-spacing:0.4px; }}
.dayline span {{ color:#b9bbc2; font-size:22px; }}
.timegroup {{ margin:8px 0 12px; }}
.time {{ font-size:22px; color:#e9ebef; font-weight:800; margin-bottom:4px; }}
.entries {{ margin-left:23px; display:flex; flex-direction:column; gap:7px; }}
.workout {{ font-size:25px; line-height:1.22; overflow-wrap:anywhere; }}
.ao {{ font-weight:900; }}
.q {{ font-weight:500; }}
.q.open {{ color:#39FF14; font-weight:900; text-shadow:0 0 5px #39ff1433; }}
.emoji {{ font-family:"Noto Color Emoji","Apple Color Emoji","Segoe UI Emoji",sans-serif; font-size:0.93em; }}
.empty {{ color:#adb0b8; font-size:23px; padding:12px 0; }}
footer {{ margin-top:18px; padding-top:0; }}
.legend-box {{ border:2px solid #37393e; border-radius:12px; padding:11px 15px 12px; }}
.legend-title {{ font-size:20px; font-weight:800; margin-bottom:7px; }}
.legend {{ display:flex; flex-wrap:wrap; column-gap:22px; row-gap:7px; font-size:19px; color:#dddfe3; }}
.legend-item {{ display:inline-flex; align-items:center; gap:4px; white-space:nowrap; }}
.footline {{ display:flex; justify-content:space-between; align-items:center; margin-top:20px; color:#bdbfc6; font-size:20px; }}
.footline strong {{ color:#e8e8ec; }}
</style></head><body><div class="canvas">
<header><div class="brand"><img src="{logo_uri}" alt="F3 logo"><h1>AGGIELAND</h1></div><div class="subtitle">WEEKLY Q SCHEDULE</div><div class="dates">{html.escape(date_range_label(monday, monday + timedelta(days=5)))}</div></header>
<main class="grid">{''.join(panels)}</main>
<footer><div class="legend-box"><div class="legend-title">EMPHASIS KEY</div><div class="legend">{legend_html}</div></div>
<div class="footline"><span>AO LOCATIONS: <strong>F3AGGIELAND.COM/AO-LOCATIONS/</strong></span><span>Powered by <strong>The Q App</strong></span></div></footer>
</div></body></html>'''


def main():
    now = datetime.now(TZ)
    week_choice = os.environ.get("SCHEDULE_WEEK", "upcoming").strip().lower()
    if week_choice == "current":
        monday = next_monday(now) if now.weekday() == 6 else now.date() - timedelta(days=now.weekday())
    elif week_choice == "upcoming":
        monday = next_monday(now)
    else:
        raise ValueError(f"Unsupported SCHEDULE_WEEK: {week_choice}")
    saturday = monday + timedelta(days=5)
    data = fetch_schedule()
    rows = [r for r in data["calendar"] if monday.isoformat() <= r.get("date", "") <= saturday.isoformat()]
    if not rows:
        raise RuntimeError(f"No workouts found for {monday} through {saturday}; refusing to generate an empty graphic")
    print(f"Schedule: {monday} through {saturday}; {len(rows)} workouts")
    markup = build_html(monday, rows)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": 1200}, device_scale_factor=1)
        page.set_content(markup, wait_until="load")
        page.evaluate("document.fonts.ready")
        page.locator(".canvas").screenshot(path=str(OUTPUT))
        browser.close()
    generated_at = datetime.now(TZ)
    manifest = {
        "weekStart": monday.isoformat(),
        "weekEnd": saturday.isoformat(),
        "generatedDate": generated_at.date().isoformat(),
        "generatedAt": generated_at.isoformat(),
        "workoutCount": len(rows),
        "imageFile": "weekly_schedule.png",
    }
    Path("weekly_schedule_metadata.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Created {OUTPUT} containing {len(rows)} workouts")
    print(f"Freshness metadata: {manifest}")


if __name__ == "__main__":
    main()
