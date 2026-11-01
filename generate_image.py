import os
import json
import math
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

API_URL = (
    "https://crtinvqnhpqnhouctmbh.supabase.co"
    "/rest/v1/rpc/load_public_region_site"
)

TIMEZONE = ZoneInfo("America/Chicago")
OUTPUT_FILE = "weekly_schedule.png"

# Canvas
WIDTH = 1600
HEIGHT = 2000
BG_COLOR = "#0b0b0b"
PANEL_COLOR = "#151515"
PANEL_BORDER = "#2a2a2a"
TEXT_COLOR = "#f2f2f2"
SUBTLE_TEXT = "#bbbbbb"
HEADER_COLOR = "#ffffff"
FOOTER_COLOR = "#bdbdbd"

# AO colors
AO_COLORS = {
    "The Cave": "#4169E1",      # Royal Blue
    "The Forest": "#228B22",    # Green
    "The Keep": "#C9A227",      # Gold
    "The Rock": "#8B5A2B",      # Brown
    "The Mine": "#0ABAB5",      # Tiffany Blue
    "The Iron": "#C0C0C0",      # Silver
    "The Watch": "#D32F2F",     # Red
    "Southie": "#F57C00",       # Orange
}

# Emphasis emoji map
EMPHASIS_EMOJI = {
    "heavy": "🏋️",
    "lower": "🦵",
    "ruck": "🎒",
    "30/30": "💡",
    "bootcamp": "🛡️",
    "benchmark": "📋",
    "upper": "💪",
    "cardio": "❤️",
    "core": "🆎",
    "stairs": "🗼",
    "murph training": "🏅",
    "murph_training": "🏅",
}

DAY_NAMES = [
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
]

DAY_ORDER = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
}

LEFT_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY"]
RIGHT_DAYS = ["THURSDAY", "FRIDAY", "SATURDAY"]


def get_font(size, bold=False):
    # Works on GitHub Actions Ubuntu runners
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)

    return ImageFont.load_default()


def get_emphasis_emoji(raw_value):
    value = (raw_value or "").strip().lower()

    if value == "" or value == "unspecified":
        return "🛡️"  # default to Bootcamp

    return EMPHASIS_EMOJI.get(value, "⭕")


def fetch_workouts():
    api_key = os.environ["SUPABASE_API_KEY"]

    today = datetime.now(TIMEZONE).date()
    monday = today + timedelta(days=(7 - today.weekday()) % 7)
    saturday = monday + timedelta(days=5)

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

    return monday, saturday, workouts


def format_date_range(monday, saturday):
    if monday.month == saturday.month:
        return f"{monday.strftime('%B')} {monday.day}–{saturday.day}, {monday.year}"
    return f"{monday.strftime('%B')} {monday.day} – {saturday.strftime('%B')} {saturday.day}, {monday.year}"


def group_by_day(workouts):
    grouped = defaultdict(list)

    for workout in workouts:
        date_obj = datetime.strptime(workout["date"], "%Y-%m-%d").date()
        day_name = DAY_NAMES[date_obj.weekday()]

        ao_name = (workout.get("ao") or {}).get("name", "Unknown AO")
        q_name = workout.get("qName") or "OPEN"
        start_time = workout.get("startTime") or ""
        emoji = get_emphasis_emoji(workout.get("emphasis"))

        grouped[day_name].append({
            "date": date_obj,
            "ao": ao_name,
            "q": q_name,
            "time": start_time,
            "emoji": emoji,
        })

    return grouped


def fit_text(draw, text, font, max_width):
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text

    suffix = "…"
    trimmed = text
    while len(trimmed) > 1:
        trimmed = trimmed[:-1]
        candidate = trimmed + suffix
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            return candidate
    return suffix


def draw_centered_text(draw, y, text, font, fill, canvas_width):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (canvas_width - w) / 2
    draw.text((x, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def draw_panel(draw, x, y, w, h, day_name, items, date_font, title_font, item_font, small_font):
    # panel
    draw.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=18,
        fill=PANEL_COLOR,
        outline=PANEL_BORDER,
        width=2
    )

    padding_x = 20
    cur_y = y + 16

    # header
    if items:
        date_text = items[0]["date"].strftime("%a %m/%d")
    else:
        date_text = day_name[:3].title()

    draw.text((x + padding_x, cur_y), day_name, font=title_font, fill=HEADER_COLOR)

    date_bbox = draw.textbbox((0, 0), date_text, font=date_font)
    date_w = date_bbox[2] - date_bbox[0]
    draw.text((x + w - padding_x - date_w, cur_y + 2), date_text, font=date_font, fill=SUBTLE_TEXT)

    cur_y += 42

    # divider
    draw.line((x + padding_x, cur_y, x + w - padding_x, cur_y), fill=PANEL_BORDER, width=2)
    cur_y += 16

    if not items:
        draw.text((x + padding_x, cur_y), "No workouts scheduled", font=item_font, fill=SUBTLE_TEXT)
        return

    line_height = 31
    q_indent = 30
    max_text_width = w - (padding_x * 2) - 125
    max_q_width = w - (padding_x * 2) - q_indent

    for item in items:
        if cur_y + line_height + 22 > y + h - 12:
            draw.text((x + padding_x, cur_y), "…", font=item_font, fill=SUBTLE_TEXT)
            break

        time_text = item["time"] or ""
        emoji = item["emoji"]
        ao_text = f"{time_text}  {emoji}  {item['ao']}"
        ao_color = AO_COLORS.get(item["ao"], TEXT_COLOR)

        ao_text = fit_text(draw, ao_text, item_font, max_text_width + 90)
        draw.text((x + padding_x, cur_y), ao_text, font=item_font, fill=ao_color)
        cur_y += line_height - 2

        q_text = f"Q: {item['q']}"
        q_text = fit_text(draw, q_text, small_font, max_q_width)
        draw.text((x + padding_x + q_indent, cur_y), q_text, font=small_font, fill=TEXT_COLOR)
        cur_y += 24


def create_legend(draw, x, y, font, small_font, max_width):
    left_items = [
        ("🏋️", "Heavy"),
        ("🦵", "Lower"),
        ("🎒", "Ruck"),
        ("💡", "30/30"),
        ("🛡️", "Bootcamp"),
        ("📋", "Benchmark"),
    ]

    right_items = [
        ("💪", "Upper"),
        ("❤️", "Cardio"),
        ("🆎", "Core"),
        ("🗼", "Stairs"),
        ("🏅", "Murph"),
        ("⭕", "Other"),
    ]

    draw.text((x, y), "KEY", font=font, fill=HEADER_COLOR)
    y += 28

    col_gap = 220
    row_gap = 26

    for i, (emoji, label) in enumerate(left_items):
        draw.text((x, y + i * row_gap), f"{emoji} {label}", font=small_font, fill=FOOTER_COLOR)

    for i, (emoji, label) in enumerate(right_items):
        draw.text((x + col_gap, y + i * row_gap), f"{emoji} {label}", font=small_font, fill=FOOTER_COLOR)


def render_image(monday, saturday, workouts):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    title_font = get_font(54, bold=True)
    subtitle_font = get_font(30, bold=False)
    panel_title_font = get_font(30, bold=True)
    panel_date_font = get_font(22, bold=False)
    item_font = get_font(24, bold=True)
    small_font = get_font(21, bold=False)
    footer_font = get_font(22, bold=False)

    # Header
    y = 40
    y += draw_centered_text(draw, y, "F3 AGGIELAND", title_font, HEADER_COLOR, WIDTH)
    y += 8
    y += draw_centered_text(draw, y, "WEEKLY Q SCHEDULE", subtitle_font, TEXT_COLOR, WIDTH)
    y += 8
    date_range = format_date_range(monday, saturday)
    y += draw_centered_text(draw, y, date_range, subtitle_font, SUBTLE_TEXT, WIDTH)

    # Counts
    count_text = f"{len(workouts)} workouts"
    draw_centered_text(draw, y + 6, count_text, footer_font, FOOTER_COLOR, WIDTH)

    # Panels area
    top = 180
    bottom = 1680
    left_margin = 60
    right_margin = 60
    col_gap = 36
    row_gap = 26

    panel_width = (WIDTH - left_margin - right_margin - col_gap) // 2
    panel_height = (bottom - top - row_gap * 2) // 3

    grouped = group_by_day(workouts)

    # Left column
    for idx, day in enumerate(LEFT_DAYS):
        px = left_margin
        py = top + idx * (panel_height + row_gap)
        draw_panel(
            draw, px, py, panel_width, panel_height,
            day, grouped.get(day, []),
            panel_date_font, panel_title_font, item_font, small_font
        )

    # Right column
    for idx, day in enumerate(RIGHT_DAYS):
        px = left_margin + panel_width + col_gap
        py = top + idx * (panel_height + row_gap)
        draw_panel(
            draw, px, py, panel_width, panel_height,
            day, grouped.get(day, []),
            panel_date_font, panel_title_font, item_font, small_font
        )

    # Footer
    footer_y = 1715
    draw.line((70, footer_y - 12, WIDTH - 70, footer_y - 12), fill=PANEL_BORDER, width=2)
    create_legend(draw, 80, footer_y, get_font(22, bold=True), get_font(20, bold=False), WIDTH - 160)

    footer_text = "AO LOCATIONS: F3AGGIELAND.COM/AO-LOCATIONS"
    bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
    footer_w = bbox[2] - bbox[0]
    draw.text((WIDTH - 80 - footer_w, footer_y + 70), footer_text, font=footer_font, fill=FOOTER_COLOR)

    img.save(OUTPUT_FILE)
    print(f"Saved image to {OUTPUT_FILE}")


def main():
    monday, saturday, workouts = fetch_workouts()
    print(f"Creating image for {monday} through {saturday}")
    print(f"Workouts found: {len(workouts)}")
    render_image(monday, saturday, workouts)


if __name__ == "__main__":
    main()
