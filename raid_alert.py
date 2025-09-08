import os
import requests
import time
from datetime import datetime, timedelta
from pytz import timezone

###########################################################
# Configuration
###########################################################
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
CHECK_INTERVAL = 5  # main loop interval in seconds
BASE_ICON_URL = os.getenv("DSR_RAID_ALERT_ICONS")
BASE_MAP_URL = os.getenv("DSR_RAID_ALERT_MAPS")
ROLE_ID = os.getenv("DISCORD_ROLE_ID")
ROLE_TAG = f"<@&{ROLE_ID}>"
# Timezones
KST = timezone("Asia/Seoul")
BRT = timezone("America/Sao_Paulo")
# Add Portugal timezone for logging
LISBON = timezone("Europe/Lisbon")
SCRIPT_START_TIME = None
sent_messages = {}
# Track finished raids to prevent duplicate alerts
completed_raids = set()
# For periodic cleanup of completed_raids
COMPLETED_RAIDS_CLEANUP_INTERVAL = 7 * 24 * 60 * 60  # 7 days in seconds
last_cleanup_time = None

custom_icons = {
    "Pumpkinmon": f"{BASE_ICON_URL}/Pumpkinmon.png",
    "Gotsumon": f"{BASE_ICON_URL}/Gotsumon.png",
    "BlackSeraphimon": f"{BASE_ICON_URL}/BlackSeraphimon.png",
    "Ophanimon: Falldown Mode": f"{BASE_ICON_URL}/Ophanimon.png",
    "Megidramon": f"{BASE_ICON_URL}/Megidramon.png",
    "Omnimon": f"{BASE_ICON_URL}/Omnimon.png",
    "Andromon": f"{BASE_ICON_URL}/Andromon.png"
}

custom_maps = {
    "Pumpkinmon": f"{BASE_MAP_URL}/Pumpkinmon_map.jpg",
    "Gotsumon": f"{BASE_MAP_URL}/Gotsumon_map.jpg",
    "BlackSeraphimon": f"{BASE_MAP_URL}/BlackSeraphimon_map.jpg",
    "Ophanimon: Falldown Mode": f"{BASE_MAP_URL}/Ophanimon_map.jpg",
    "Megidramon": f"{BASE_MAP_URL}/Megidramon_map.jpg",
    "Omnimon": f"{BASE_MAP_URL}/Omnimon_map.jpg",
    "Andromon": f"{BASE_MAP_URL}/Andromon_map.jpg"
}

# Map translation EN->KR
map_translation = {
    "Shibuya": "시부야",
    "Valley of Darkness": "어둠성 계곡",
    "Campground": "캠핑장",
    "Subway Station": "지하철 역",
    "???": "???",
    "Gear Savannah": "기어 사바나"
}

REAL_RAIDS = [
    {
        "name": "🎃 Pumpkinmon",
        "map": "Shibuya",
        "times": ["19:30", "21:30"],
        "frequency": "daily",
    },
    {
        "name": "🪨 Gotsumon",
        "map": "Shibuya",
        "times": ["23:00", "01:00"],
        "frequency": "daily",
    },
    {
        "name": "😈 BlackSeraphimon",
        "map": "???",
        "times": ["23:00"],
        "frequency": "biweekly",
        "base_date": "2025-05-31",
    },
    {
        "name": "🪽 Ophanimon: Falldown Mode",
        "map": "???",
        "times": ["23:00"],
        "frequency": "biweekly",
        "base_date": "2025-06-07",
    },
    {
        "name": "👹 Megidramon",
        "map": "???",
        "times": ["22:00"],
        "frequency": "biweekly",
        "base_date": "2025-06-08",
    },
    {
        "name": "🤖 Omnimon",
        "map": "Valley of Darkness",
        "times": ["22:00"],
        "frequency": "biweekly",
        "base_date": "2025-06-01",
    },
    {
        "name": "🎲 Andromon",
        "map": "Gear Savannah",
        "times": ["19:00"],
        "frequency": "daily",
        "base_date": "2025-08-28",
    },
]

###########################################################
# Utilities
###########################################################
def get_image_path(name: str) -> str:
    if name in custom_icons:
        return f"{custom_icons[name]}?v={int(time.time())}"
    safe_name = name.replace(":", "_")
    return f"https://media.dsrwiki.com/dsrwiki/digimon/{safe_name}/{safe_name}.webp?v={int(time.time())}"

def get_current_kst():
    return datetime.now(KST)

def get_log_time():
    # Returns current time in Portugal timezone as string
    return datetime.now(LISBON).strftime("%Y-%m-%d %H:%M:%S")

def get_next_daily_time(time_str):
    now = get_current_kst()
    raid_time = datetime.strptime(time_str, "%H:%M").time()
    raid_dt = KST.localize(datetime.combine(now.date(), raid_time))
    if raid_dt <= now:
        raid_dt += timedelta(days=1)
    return raid_dt

def get_next_biweekly_time(time_str, base_date_str):
    now = get_current_kst()
    base_date = KST.localize(datetime.strptime(base_date_str, "%Y-%m-%d"))
    raid_time = datetime.strptime(time_str, "%H:%M").time()
    diff_days = (now.date() - base_date.date()).days
    cycles = diff_days // 14
    next_date = base_date + timedelta(days=cycles * 14)
    raid_dt = KST.localize(datetime.combine(next_date.date(), raid_time))
    if raid_dt <= now:
        raid_dt += timedelta(days=14)
    return raid_dt

def get_next_rotation_time(base_time_str, base_date_str):
    """
    Returns the next raid time for Andromon, rotating 25 minutes later each day since base_date.
    """
    now = get_current_kst()
    base_date = KST.localize(datetime.strptime(base_date_str, "%Y-%m-%d"))
    base_hour, base_minute = map(int, base_time_str.split(":"))
    # Calculate days since base_date
    now_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    base_midnight = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
    diff_days = (now_midnight - base_midnight).days
    # Calculate today's raid time
    raid_time = base_date + timedelta(days=diff_days)
    raid_time = raid_time.replace(hour=base_hour, minute=base_minute)
    raid_time += timedelta(minutes=diff_days * 25)
    if raid_time <= now:
        # Move to next day
        diff_days += 1
        raid_time = base_date + timedelta(days=diff_days)
        raid_time = raid_time.replace(hour=base_hour, minute=base_minute)
        raid_time += timedelta(minutes=diff_days * 25)
    return raid_time

def clean_boss_name(raw_name: str) -> str:
    clean = (raw_name.replace('🎃 ', '').replace('😈 ', '').replace(
        '👹 ', '').replace('🤖 ',
                          '').replace('🎲 ', '').replace('🪨 ', '').replace(
                              '🪽 ', '').replace('(Dummy)', '').strip())
    return clean

def get_map_image_url(map_name, boss_name=None):
    clean_name = clean_boss_name(boss_name) if boss_name else None
    if clean_name and clean_name in custom_maps:
        return f"{custom_maps[clean_name]}?v={int(time.time())}"
    kr_name = map_translation.get(map_name)
    if not kr_name:
        return None
    if kr_name == "???":
        return f"https://media.dsrwiki.com/dsrwiki/map/ApocalymonArea.webp?v={int(time.time())}"
    safe_name = "".join(kr_name.split())
    return f"https://media.dsrwiki.com/dsrwiki/map/{safe_name}.webp?v={int(time.time())}"

def get_remaining_minutes(seconds_total: int) -> int:
    if seconds_total <= 0:
        return 0
    minutes = seconds_total // 60
    seconds = seconds_total % 60
    if seconds > 30:
        minutes += 1
    return minutes

def format_minutos_pt(n: int) -> str:
    return "1 minuto" if n == 1 else f"{n} minutos"

###########################################################
# Status and colors
###########################################################
def compute_status(time_diff):
    minutes_until = get_remaining_minutes(int(time_diff))
    if time_diff < -300:
        return "finished"
    elif minutes_until > 5:
        return "upcoming"
    elif 1 <= minutes_until <= 5:
        return "starting"
    elif minutes_until == 0 or (time_diff < 0 and time_diff >= -300):
        return "ongoing"

def get_raid_status(time_diff):
    status = compute_status(time_diff)
    color = {
        "upcoming": 0xFF0000,
        "starting": 0xFFFF00,
        "ongoing": 0x00FF00,
        "finished": 0x808080,
    }[status]
    return status, color

###########################################################
# Webhook helpers
###########################################################
def _webhook_post_url_wait_true():
    return WEBHOOK_URL + ("&" if "?" in WEBHOOK_URL else "?") + "wait=true"

def create_embed_content(raid, time_until_raid_seconds):
    brt_time = raid["next_time"].astimezone(BRT)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))
    clean_name = clean_boss_name(raid['name'])
    status, color = get_raid_status(time_until_raid_seconds)

    if status in ("upcoming", "starting"):
        desc_status = f"⏳ Em {format_minutos_pt(minutes_until)}"
    elif status == "ongoing":
        # Calculate minutes since raid started
        minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
        desc_status = f"⚔️ **Começou há {format_minutos_pt(minutes_ongoing)}**"
    else:
        desc_status = "✅ **Raid finalizada!**"

    # Always show BRT hour for all raids
    horario_str = brt_time.strftime('%H:%M')

    embed = {
        "title": f"{clean_name}",
        "fields": [
            {"name": "", "value": f"📍 {raid['map']}", "inline": False},
            {"name": "", "value": f"⏰ {horario_str}", "inline": False},
            {"name": "", "value": f"{desc_status}", "inline": False}
        ],
        "color": color,
        "thumbnail": {"url": raid["image"]},
        "footer": {"text": "DSR Raid Alert | Done by Douleur"},
    }

    map_image_url = get_map_image_url(raid['map'], clean_name)
    if map_image_url:
        embed["image"] = {"url": map_image_url}
    return embed

# Update only status/color in the existing embed
def update_embed_fields(embed, time_until_raid_seconds):
    status, color = get_raid_status(time_until_raid_seconds)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))
    embed["color"] = color
    if status in ("upcoming", "starting"):
        desc_status = f"⏳ Em {format_minutos_pt(minutes_until)}"
    elif status == "ongoing":
        minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
        desc_status = f"⚔️ **Começou há {format_minutos_pt(minutes_ongoing)}**"
    else:
        desc_status = "✅ **Raid finalizada!**"
    embed["fields"][-1]["value"] = desc_status
    return embed, status

def send_webhook_message(raid, time_until_raid_seconds):
    if not WEBHOOK_URL:
        print("⚠️ Erro: DISCORD_WEBHOOK não está configurado")
        return False, None, None
    # Production log: log every alert sent
    print(f"[{get_log_time()}] [ALERT] Sent alert for {raid['name']} scheduled at {raid['next_time'].strftime('%Y-%m-%d %H:%M:%S %Z')} | Status: {get_raid_status(time_until_raid_seconds)[0]}")

    embed = create_embed_content(raid, time_until_raid_seconds)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))

    status, _ = get_raid_status(time_until_raid_seconds)

    if status == "ongoing":
        minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
        ongoing_str = f"Começou há {format_minutos_pt(minutes_ongoing)}"
    if status in ("upcoming", "starting"):
        content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** | Começa em {format_minutos_pt(minutes_until)}!"
    elif status == "ongoing":
        content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** | {ongoing_str}!"
    else:
        content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** | Raid finalizada!"

    payload = {"content": content, "embeds": [embed]}
    try:
        response = requests.post(_webhook_post_url_wait_true(), json=payload)
        if response.status_code == 200:
            data = response.json()
            message_id = data.get('id')
            return True, message_id, embed
        else:
            print(
                f"Error in webhook: {response.status_code} - {response.text}")
            return False, None, None
    except Exception as e:
        print(f"Error in request: {e}")
        return False, None, None

def edit_webhook_message(message_id, raid, time_until_raid_seconds, embed):
    if not WEBHOOK_URL or not message_id:
        return False, None
    try:
        webhook_parts = WEBHOOK_URL.replace(
            'https://discord.com/api/webhooks/', '').split('/')
        webhook_id = webhook_parts[0]
        webhook_token = webhook_parts[1]
    except Exception:
        print("Error extracting webhook ID and token")
        return False, None
    embed, status = update_embed_fields(embed, time_until_raid_seconds)
    # Production log: log every embed update
    print(f"[{get_log_time()}] [UPDATE] Updated alert for {raid['name']} scheduled at {raid['next_time'].strftime('%Y-%m-%d %H:%M:%S %Z')} | Status: {status}")
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))
    if status == "ongoing":
        minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
        ongoing_str = f"Começou há {format_minutos_pt(minutes_ongoing)}"
    if status in ("upcoming", "starting"):
        content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** | Começa em {format_minutos_pt(minutes_until)}!"
    elif status == "ongoing":
        content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** | {ongoing_str}!"
    else:
        content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** | Raid finalizada!"

    payload = {"content": content, "embeds": [embed]}
    
    edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
    try:
        response = requests.patch(edit_url, json=payload)
        print(f"[DEBUG] Discord PATCH response: {response.status_code}")
        if response.status_code == 200:
            return True, status
        else:
            print(
                f"Error editing message: {response.status_code} - {response.text}"
            )
            return False, status
    except Exception as e:
        print(f"Error in editing webhook message: {e}")
        return False, status

###########################################################
# Raids & Schedule (real + dummy)
###########################################################
# frequency: "daily" -> uses get_next_daily_time
#            "biweekly" -> uses get_next_biweekly_time + base_date (YYYY-MM-DD)
def get_upcoming_raids():
    raids = []
    for cfg in REAL_RAIDS:
        name = cfg["name"]
        map_name = cfg["map"]
        freq = cfg.get("frequency", "daily")
        times = cfg.get("times", [])
        base_date = cfg.get("base_date")
        # Special case for Andromon (rotation raid)
        if name == "🎲 Andromon":
            # Use base_time and base_date for rotation
            base_time = times[0]
            next_time_dt = get_next_rotation_time(base_time, base_date)
            raids.append({
                "name": name,
                "map": map_name,
                "next_time": next_time_dt,
                "scheduled_time": base_time,
                "image": get_image_path(clean_boss_name(name)),
            })
            continue
        for t in times:
            if freq == "biweekly":
                next_time_dt = get_next_biweekly_time(t, base_date)
            else:
                next_time_dt = get_next_daily_time(t)
            raids.append({
                "name": name,
                "map": map_name,
                "next_time": next_time_dt,
                "scheduled_time": t,
                "image": get_image_path(clean_boss_name(name)),
            })
    raids.sort(key=lambda r: r["next_time"])
    return raids


###########################################################
# Main loop
###########################################################
def main():
    global last_cleanup_time
    last_summary_log = None
    print(f"[{get_log_time()}] Starting DSRRaidAlert...")
    # Log relevant environment variables at startup
    print("[ENV] DISCORD_WEBHOOK:", WEBHOOK_URL)
    print("[ENV] DSR_RAID_ALERT_ICONS:", BASE_ICON_URL)
    print("[ENV] DSR_RAID_ALERT_MAPS:", BASE_MAP_URL)
    print("[ENV] DISCORD_ROLE_ID:", ROLE_ID)
    while True:
        now_kst = get_current_kst()  # Always use KST for calculations
        upcoming_raids = get_upcoming_raids()

        # Periodic cleanup of completed_raids (every 7 days)
        if last_cleanup_time is None or (now_kst - last_cleanup_time).total_seconds() > COMPLETED_RAIDS_CLEANUP_INTERVAL:
            cutoff = now_kst - timedelta(seconds=COMPLETED_RAIDS_CLEANUP_INTERVAL)
            before = len(completed_raids)
            completed_raids_copy = set(completed_raids)
            for key in completed_raids_copy:
                # key = (name, time_str)
                try:
                    raid_time = datetime.strptime(key[1], "%Y-%m-%d %H:%M:%S")
                    raid_time = KST.localize(raid_time)
                    if raid_time < cutoff:
                        completed_raids.remove(key)
                except Exception:
                    continue
            after = len(completed_raids)
            print(f"[{get_log_time()}] [CLEANUP] Cleaned up completed_raids: {before} -> {after}")
            last_cleanup_time = now_kst

        # Log a summary of scheduled raids every hour as a table
        if last_summary_log is None or (now_kst - last_summary_log).total_seconds() >= 3600:
            print(f"[{get_log_time()}] [SUMMARY] Scheduled raids:")
            print("+----------------------+---------------------+----------------------+\n| Raid Name            | Scheduled Time       | Map                  |\n+----------------------+---------------------+----------------------+")
            for r in upcoming_raids:
                name = r['name'][:20].ljust(20)
                sched = r['next_time'].strftime('%Y-%m-%d %H:%M').ljust(19)
                mapn = r['map'][:20].ljust(20)
                print(f"| {name} | {sched} | {mapn} |")
            print("+----------------------+---------------------+----------------------+")
            last_summary_log = now_kst

        # First, send new alerts for upcoming raids
        for raid in upcoming_raids:
            time_diff = (raid["next_time"] - now_kst).total_seconds()
            key = (raid["name"], raid["next_time"].strftime("%Y-%m-%d %H:%M:%S"))

            # Alert exactly at or after threshold (10min = 600s)
            if time_diff <= 600 and key not in sent_messages and key not in completed_raids:
                success, message_id, embed = send_webhook_message(raid, time_diff)
                if success:
                    sent_messages[key] = {
                        'message_id': message_id,
                        'raid_time': raid["next_time"],
                        'last_update': now_kst,
                        'embed': embed,
                        'raid': raid  # Store the original raid dict
                    }

        # Then, update all sent messages using their original scheduled time
        for key, message_data in list(sent_messages.items()):
            raid_name, scheduled_time_str = key
            # Use the original scheduled time for updates
            raid = message_data['raid']
            raid_time = message_data['raid_time']
            time_diff = (raid_time - now_kst).total_seconds()
            seconds_since_last_update = (now_kst - message_data['last_update']).total_seconds()
            if seconds_since_last_update >= 60:
                success, status = edit_webhook_message(
                    message_data['message_id'], raid, time_diff,
                    message_data['embed'])
                if success:
                    sent_messages[key]['last_update'] = now_kst
                    # Only remove from sent_messages after a successful update to 'finished'
                    if status == "finished":
                        print(f"[{get_log_time()}] [INFO] Raid {raid_name} finished. Removing from sent_messages and adding to completed_raids.")
                        del sent_messages[key]
                        completed_raids.add(key)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    if WEBHOOK_URL:
        main()
    else:
        print("Config DISCORD_WEBHOOK before continuing.")
