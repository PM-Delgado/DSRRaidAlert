import os
import requests
import time
from datetime import datetime, timedelta
from pytz import timezone

# =============================
# Configurações
# =============================
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
CHECK_INTERVAL = 5  # loop principal a cada 5s
TEST_DUMMIES_AS_REAL = True
BASE_ICON_URL = os.getenv("DSR_RAID_ALERT_ICONS")
BASE_MAP_URL = os.getenv("DSR_RAID_ALERT_MAPS")
ROLE_ID = os.getenv("DISCORD_ROLE_ID")
ROLE_TAG = f"<@&{ROLE_ID}>"

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

# Timezones
KST = timezone("Asia/Seoul")
BRT = timezone("America/Sao_Paulo")

SCRIPT_START_TIME = None
sent_messages = {}

# =============================
# Utilitários
# =============================


def get_image_path(name: str) -> str:
    if name in custom_icons:
        return f"{custom_icons[name]}?v={int(time.time())}"
    safe_name = name.replace(":", "_")
    return f"https://media.dsrwiki.com/dsrwiki/digimon/{safe_name}/{safe_name}.webp?v={int(time.time())}"


def get_current_kst():
    return datetime.now(KST)


def get_next_daily_time(time_str):
    now = get_current_kst()
    raid_time = datetime.strptime(time_str, "%H:%M").time()
    raid_dt = datetime.combine(now.date(), raid_time, tzinfo=KST)
    if raid_dt <= now:
        raid_dt += timedelta(days=1)
    return raid_dt


def get_next_biweekly_time(time_str, base_date_str):
    now = get_current_kst()
    base_date = datetime.strptime(base_date_str,
                                  "%Y-%m-%d").replace(tzinfo=KST)
    raid_time = datetime.strptime(time_str, "%H:%M").time()
    diff_days = (now.date() - base_date.date()).days
    cycles = diff_days // 14
    next_date = base_date + timedelta(days=cycles * 14)
    raid_dt = datetime.combine(next_date.date(), raid_time, tzinfo=KST)
    if raid_dt <= now:
        raid_dt += timedelta(days=14)
    return raid_dt


def get_dummy_raid_time(minutes_offset, seconds_offset=0):
    global SCRIPT_START_TIME
    if SCRIPT_START_TIME is None:
        SCRIPT_START_TIME = get_current_kst()
        print(
            f"🚀 Script iniciado em: {SCRIPT_START_TIME.strftime('%H:%M:%S')} KST"
        )
    return SCRIPT_START_TIME + timedelta(minutes=minutes_offset,
                                         seconds=seconds_offset)


# Tradução EN->KR
map_translation = {
    "Shibuya": "시부야",
    "Valley of Darkness": "어둠성 계곡",
    "Campground": "캠핑장",
    "Subway Station": "지하철 역",
    "???": "???",
    "Gear Savannah": "기어 사바나"
}


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


# =============================
# Estados e cores
# =============================
def compute_status(time_diff, is_dummy):
    minutes_until = get_remaining_minutes(int(time_diff))
    if time_diff < -300:
        return "finished"
    elif minutes_until > 5:
        return "upcoming"
    elif 1 <= minutes_until <= 5:
        return "starting"
    elif minutes_until == 0 or time_diff >= -300:
        return "ongoing"


def get_raid_status(time_diff, raid_type):
    status = compute_status(time_diff, raid_type == "dummy")
    color = {
        "upcoming": 0xFF0000,
        "starting": 0xFFFF00,
        "ongoing": 0x00FF00,
        "finished": 0x808080,
    }[status]
    return status, color


# =============================
# Webhook helpers
# =============================


def _webhook_post_url_wait_true():
    return WEBHOOK_URL + ("&" if "?" in WEBHOOK_URL else "?") + "wait=true"


def create_embed_content(raid, time_until_raid_seconds):
    brt_time = raid["next_time"].astimezone(BRT)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))
    clean_name = clean_boss_name(raid['name'])
    status, color = get_raid_status(time_until_raid_seconds, raid.get("type"))

    if status in ("upcoming", "starting"):
        desc_status = f"⏳ Falta {minutes_until}min"
    elif status == "ongoing":
        desc_status = "⚔️ **Raid a decorrer!**"
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


# 🔹 NOVA função: atualizar só status/cor no embed existente
def update_embed_fields(embed, raid, time_until_raid_seconds):
    status, color = get_raid_status(time_until_raid_seconds, raid.get("type"))
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))
    embed["color"] = color
    if status in ("upcoming", "starting"):
        desc_status = f"⏳ Falta {minutes_until}min"
    elif status == "ongoing":
        desc_status = "⚔️ **Raid a decorrer!**"
    else:
        desc_status = "✅ **Raid finalizada!**"
    embed["fields"][-1]["value"] = desc_status
    return embed, status


def send_webhook_message(raid, time_until_raid_seconds):
    if not WEBHOOK_URL:
        print("⚠️ Erro: DISCORD_WEBHOOK não está configurado")
        return False, None, None

    embed = create_embed_content(raid, time_until_raid_seconds)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))

    status, _ = get_raid_status(time_until_raid_seconds, raid.get("type"))

    if raid.get("type") == "dummy":
        if status in ("upcoming", "starting"):
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"
        elif status == "ongoing":
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** está a decorrer!"
        else:
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** foi finalizada!"
    else:
        if status in ("upcoming", "starting"):
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"
        elif status == "ongoing":
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** está a decorrer!"
        else:
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** foi finalizada!"

    payload = {"content": content, "embeds": [embed]}
    try:
        response = requests.post(_webhook_post_url_wait_true(), json=payload)
        if response.status_code == 200:
            data = response.json()
            message_id = data.get('id')
            print(f"✅ Mensagem enviada para {raid['name']} (ID: {message_id})")
            return True, message_id, embed
        else:
            print(
                f"❌ Erro no webhook: {response.status_code} - {response.text}")
            return False, None, None
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
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
        print("❌ Erro ao extrair webhook ID e token")
        return False, None
    embed, status = update_embed_fields(embed, raid, time_until_raid_seconds)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))
    if raid.get("type") == "dummy":
        if status in ("upcoming", "starting"):
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"
        elif status == "ongoing":
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** está a decorrer!"
        else:
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** foi finalizada!"
    else:
        if status in ("upcoming", "starting"):
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"
        elif status == "ongoing":
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** está a decorrer!"
        else:
            content = f"||{ROLE_TAG}||\n**{raid['name'].upper()}** foi finalizada!"

    payload = {"content": content, "embeds": [embed]}
    edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
    try:
        response = requests.patch(edit_url, json=payload)
        if response.status_code == 200:
            return True, status
        else:
            print(
                f"❌ Erro ao editar mensagem: {response.status_code} - {response.text}"
            )
            return False, status
    except Exception as e:
        print(f"❌ Erro na edição: {e}")
        return False, status


# =============================
# Raids & Agenda (real + dummy)
# =============================

# frequency: "daily" -> usa get_next_daily_time
#            "biweekly" -> usa get_next_biweekly_time + base_date (YYYY-MM-DD)
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

# Raids dummy para teste local (podes ajustar offsets/nomes/maps)
DUMMY_RAIDS = [
    {
        "name": "🎲 Andromon (Dummy)",
        "map": "Shibuya",
        "type": "dummy",
        "times": [2, 4],  # minutos de offset em relação ao SCRIPT_START_TIME
    },
    {
        "name": "🪨 Gotsumon (Dummy)",
        "map": "Shibuya",
        "type": "dummy",
        "times": [3, 5],  # minutos de offset em relação ao SCRIPT_START_TIME
    }
]


def _build_raid_entry(name: str,
                      map_name: str,
                      next_time_dt,
                      raid_type: str,
                      scheduled_time: str | None = None):
    """Cria o dicionário de raid no formato esperado pelo resto do código."""
    return {
        "name": name,
        "map": map_name,
        "type": raid_type,  # "dummy" ou "real"
        "next_time": next_time_dt,  # datetime tz-aware (KST)
        "scheduled_time":
        scheduled_time,  # string "HH:MM" só para reais (mostrada no embed)
        "image": get_image_path(clean_boss_name(name)),  # thumbnail do boss
    }


def get_upcoming_raids():
    raids = []

    for cfg in REAL_RAIDS:
        name = cfg["name"]
        map_name = cfg["map"]
        freq = cfg.get("frequency", "daily")
        times = cfg.get("times", [])
        base_date = cfg.get("base_date")

        for t in times:
            if freq == "biweekly":
                next_time_dt = get_next_biweekly_time(t, base_date)
            else:
                next_time_dt = get_next_daily_time(t)

            raids.append({
                "name": name,
                "map": map_name,
                "type": "real",
                "next_time": next_time_dt,
                "scheduled_time": t,
                "image": get_image_path(clean_boss_name(name)),
            })

    # Dummy raids for local testing: schedule at 10 and 15 minutes after script start
    now_kst = get_current_kst()
    dummy_raid_times = [now_kst + timedelta(minutes=10), now_kst + timedelta(minutes=15)]
    dummy_names = ["🎲 Andromon (Dummy)", "🪨 Gotsumon (Dummy)"]
    dummy_maps = ["Shibuya", "Shibuya"]
    for i in range(len(dummy_names)):
        raids.append({
            "name": dummy_names[i],
            "map": dummy_maps[i],
            "type": "dummy",
            "next_time": dummy_raid_times[i],
            "scheduled_time": None,
            "image": get_image_path(clean_boss_name(dummy_names[i])),
        })

    raids.sort(key=lambda r: r["next_time"])
    return raids


# =============================
# Loop principal
# =============================


def main():
    print("🔍 Iniciando Discord Raid Bot...")
    while True:
        now_kst = get_current_kst()  # Always use KST for calculations
        upcoming_raids = get_upcoming_raids()

        for raid in upcoming_raids:
            # All raid["next_time"] are KST-aware
            time_diff = (raid["next_time"] - now_kst).total_seconds()
            key = (raid["name"], raid["next_time"].strftime("%Y-%m-%d %H:%M:%S"))

            # Alert exactly at or after threshold (10min = 600s)
            if time_diff <= 600 and key not in sent_messages:
                success, message_id, embed = send_webhook_message(raid, time_diff)
                if success:
                    sent_messages[key] = {
                        'message_id': message_id,
                        'raid_time': raid["next_time"],
                        'last_update': now_kst,
                        'embed': embed
                    }

            # Update status every minute
            if key in sent_messages:
                message_data = sent_messages[key]
                if (now_kst - message_data['last_update']).total_seconds() >= 60:
                    success, status = edit_webhook_message(
                        message_data['message_id'], raid, time_diff,
                        message_data['embed'])
                    if success:
                        sent_messages[key]['last_update'] = now_kst
                        if status == "finished":
                            del sent_messages[key]

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    if WEBHOOK_URL:
        main()
    else:
        print("❌ Configure DISCORD_WEBHOOK antes de continuar.")
