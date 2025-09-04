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
BASE_ICON_URL = "https://raw.githubusercontent.com/PM-Delgado/DSRRaidAlert/main/RAlertIcons"
BASE_MAP_URL = "https://raw.githubusercontent.com/PM-Delgado/DSRRaidAlert/main/RAlertMaps"

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
        return f"{custom_icons[name]}?v={int(time.time())}"  # append timestamp
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


def get_map_image_url(map_name, boss_name=None):
    # tenta primeiro buscar pela tabela custom
    if boss_name and boss_name in custom_maps:
        return f"{custom_maps[boss_name]}?v={int(time.time())}"

    # fallback para Wiki (caso não exista no custom_maps)
    kr_name = map_translation.get(map_name)
    if not kr_name:
        return None
    if kr_name == "???":
        return "https://media.dsrwiki.com/dsrwiki/map/ApocalymonArea.webp"
    safe_name = "".join(kr_name.split())
    return f"https://media.dsrwiki.com/dsrwiki/map/{safe_name}.webp"


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

    if TEST_DUMMIES_AS_REAL:
        is_dummy = False

    if is_dummy:
        if time_diff < -60:  # mais de 1min após o início
            return "finished"
        elif minutes_until > 1:
            return "upcoming"
        elif minutes_until == 1:
            return "starting"
        else:  # inclui minutes_until == 0 e até -60s
            return "ongoing"
    else:
        if time_diff < -300:  # mais de 5min após o início
            return "finished"
        elif minutes_until > 10:
            return "upcoming"
        elif 1 <= minutes_until <= 5:
            return "starting"
        elif minutes_until == 0 or time_diff >= -300:
            return "ongoing"


def get_raid_status(time_diff, raid_type):
    is_dummy = (raid_type == "dummy")
    status = compute_status(time_diff, is_dummy)
    color = {
        "upcoming": 0xFF0000,
        "starting": 0xFFFF00,
        "ongoing": 0x00FF00,
        "finished": 0x808080,
    }[status]
    return status, color


# =============================
# Definição das raids
# =============================


def get_raids_list():
    base_raids = [
        {
            "name": "🎃 Pumpkinmon",
            "image": get_image_path("Pumpkinmon"),
            "times": ["19:30", "21:30"],
            "type": "daily",
            "map": "Shibuya"
        },
        {
            "name": "🪨 Gotsumon",
            "image": get_image_path("Gotsumon"),
            "times": ["23:00", "01:00"],
            "type": "daily",
            "map": "Shibuya"
        },
        {
            "name": "😈 BlackSeraphimon",
            "image": get_image_path("BlackSeraphimon"),
            "times": ["23:00"],
            "type": "biweekly",
            "baseDate": "2025-05-31",
            "map": "???"
        },
        {
            "name": "🪽 Ophanimon: Falldown Mode",
            "image": get_image_path("Ophanimon: Falldown Mode"),
            "times": ["23:00"],
            "type": "biweekly",
            "baseDate": "2025-06-07",
            "map": "???"
        },
        {
            "name": "👹 Megidramon",
            "image": get_image_path("Megidramon"),
            "times": ["22:00"],
            "type": "biweekly",
            "baseDate": "2025-06-08",
            "map": "???"
        },
        {
            "name": "🤖 Omnimon",
            "image": get_image_path("Omnimon"),
            "times": ["22:00"],
            "type": "biweekly",
            "baseDate": "2025-06-01",
            "map": "Valley of Darkness"
        },
    ]

    rotation_raids = [{
        "name": "🎲 Andromon",
        "image": get_image_path("Andromon"),
        "times": ["19:00"],
        "type": "daily",
        "baseDate": "2025-08-28",
        "map": "Gear Savannah"
    }]

    # --- dummies agora simulam raids reais ---
    dummy_raids = [{
        "name": "🪨 Gotsumon (Dummy)",
        "image": get_image_path("Gotsumon"),
        "type": "dummy",
        "map": "Shibuya",
        "raid_time": get_dummy_raid_time(2, 0)
    }, {
        "name": "🪽 Ophanimon: Falldown Mode",
        "image": get_image_path("Ophanimon: Falldown Mode"),
        "type": "dummy",
        "map": "???",
        "raid_time": get_dummy_raid_time(3, 0)
    }, {
        "name": "🎲 Andromon (Dummy) (Rotation)",
        "image": get_image_path("Andromon"),
        "type": "dummy",
        "map": "Gear Savannah",
        "raid_time": get_dummy_raid_time(4, 0)
    }, {
        "name": "🎃 Pumpkinmon (Dummy)",
        "image": get_image_path("Pumpkinmon"),
        "type": "dummy",
        "map": "Shibuya",
        "raid_time": get_dummy_raid_time(5, 0)
    }, {
        "name": "😈 BlackSeraphimon (Dummy)",
        "image": get_image_path("BlackSeraphimon"),
        "type": "dummy",
        "map": "???",
        "raid_time": get_dummy_raid_time(6, 0)
    }, {
        "name": "👹 Megidramon (Dummy)",
        "image": get_image_path("Megidramon"),
        "type": "dummy",
        "map": "???",
        "raid_time": get_dummy_raid_time(7, 0)
    }, {
        "name": "🤖 Omnimon (Dummy)",
        "image": get_image_path("Omnimon"),
        "type": "dummy",
        "map": "Valley of Darkness",
        "raid_time": get_dummy_raid_time(8, 0)
    }]

    return base_raids + rotation_raids + dummy_raids


def get_upcoming_raids():
    all_raids = []
    raids = get_raids_list()

    for raid in raids:
        if raid["type"] == "dummy":
            all_raids.append({
                "name": raid["name"],
                "map": raid["map"],
                "image": raid["image"],
                "next_time": raid["raid_time"],
                "type": raid["type"],
            })
        else:
            for t in raid.get("times", []):
                if raid["type"] == "daily":
                    next_time = get_next_daily_time(t)
                elif raid["type"] == "biweekly":
                    next_time = get_next_biweekly_time(t, raid["baseDate"])
                else:
                    continue
                all_raids.append({
                    "name": raid["name"],
                    "map": raid["map"],
                    "image": raid["image"],
                    "next_time": next_time,
                    "type": raid["type"],
                    "scheduled_time": t,
                })

    all_raids.sort(key=lambda r: r["next_time"])
    return all_raids


# =============================
# Webhook helpers
# =============================


def _webhook_post_url_wait_true():
    return WEBHOOK_URL + ("&" if "?" in WEBHOOK_URL else "?") + "wait=true"


def create_embed_content(raid, time_until_raid_seconds):
    brt_time = raid["next_time"].astimezone(BRT)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))

    clean_name = raid['name'].replace('🎃 ', '').replace('😈 ', '').replace(
        '👹 ', '').replace('🤖 ', '').replace('🎲 ',
                                            '').replace('🪨 ',
                                                        '').replace('🪽 ', '')

    status, color = get_raid_status(time_until_raid_seconds, raid.get("type"))

    # Descrição do estado
    if status in ("upcoming", "starting"):
        desc_status = f"⏳ Falta {minutes_until}min"
    elif status == "ongoing":
        desc_status = "⚔️ **Raid a decorrer!**"
    else:
        desc_status = "✅ **Raid finalizada!**"

    # Mostrar hora
    if raid.get("type") == "dummy":
        horario_str = brt_time.strftime('%H:%M')
    else:
        # Usa o horário definido originalmente (sem offsets)
        horario_str = raid.get("scheduled_time", brt_time.strftime('%H:%M'))

    embed = {
        "title":
        f"{clean_name}",
        "fields": [{
            "name": "",
            "value": f"📍 {raid['map']}",
            "inline": False
        }, {
            "name": "",
            "value": f"⏰ {horario_str}",
            "inline": False
        }, {
            "name": "",
            "value": f"{desc_status}",
            "inline": False
        }],
        "color":
        color,
        "thumbnail": {
            "url": raid["image"]
        },
        "footer": {
            "text": "DSR Raid Alert | Done by tatsuya666"
        },
    }

    map_image_url = get_map_image_url(
        raid['map'], raid['name'].replace('🎃 ', '').replace('😈 ', '').replace(
            '👹 ', '').replace('🤖 ',
                              '').replace('🎲 ',
                                          '').replace('🪨 ',
                                                      '').replace('🪽 ', ''))

    if map_image_url:
        embed["image"] = {"url": map_image_url}

    return embed


def send_webhook_message(raid, time_until_raid_seconds):
    if not WEBHOOK_URL:
        print("⚠️ Erro: DISCORD_WEBHOOK não está configurado")
        return False, None

    embed = create_embed_content(raid, time_until_raid_seconds)
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))

    if raid.get("type") == "dummy":
        content = f"**{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"
    else:
        content = f"@everyone **{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"

    payload = {"content": content, "embeds": [embed]}

    try:
        response = requests.post(_webhook_post_url_wait_true(), json=payload)
        if response.status_code == 200:
            data = response.json()
            message_id = data.get('id')
            print(f"✅ Mensagem enviada para {raid['name']} (ID: {message_id})")
            return True, message_id
        else:
            print(
                f"❌ Erro no webhook: {response.status_code} - {response.text}")
            return False, None
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return False, None


def edit_webhook_message(message_id, raid, time_until_raid_seconds):
    if not WEBHOOK_URL or not message_id:
        return False
    try:
        webhook_parts = WEBHOOK_URL.replace(
            'https://discord.com/api/webhooks/', '').split('/')
        webhook_id = webhook_parts[0]
        webhook_token = webhook_parts[1]
    except Exception:
        print("❌ Erro ao extrair webhook ID e token")
        return False

    embed = create_embed_content(raid, time_until_raid_seconds)
    status, _ = get_raid_status(time_until_raid_seconds, raid.get("type"))
    minutes_until = get_remaining_minutes(int(time_until_raid_seconds))

    if raid.get("type") == "dummy":
        if status in ("upcoming", "starting"):
            content = f"**{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"
        elif status == "ongoing":
            content = f"**{raid['name'].upper()}** está a decorrer!"
        else:
            content = f"**{raid['name'].upper()}** foi finalizada!"
    else:
        if status in ("upcoming", "starting"):
            content = f"**{raid['name'].upper()}** começa em {format_minutos_pt(minutes_until)}!"
        elif status == "ongoing":
            content = f"**{raid['name'].upper()}** está a decorrer!"
        else:
            content = f"**{raid['name'].upper()}** foi finalizada!"

    payload = {"content": content, "embeds": [embed]}
    edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"

    try:
        response = requests.patch(edit_url, json=payload)
        if response.status_code == 200:
            return True
        else:
            print(
                f"❌ Erro ao editar mensagem: {response.status_code} - {response.text}"
            )
            return False
    except Exception as e:
        print(f"❌ Erro na edição: {e}")
        return False


# =============================
# Loop principal
# =============================


def main():
    print("🔍 Iniciando Discord Raid Bot...")
    alerted = set()

    while True:
        now = get_current_kst()
        upcoming_raids = get_upcoming_raids()

        for raid in upcoming_raids:
            time_diff = (raid["next_time"] - now).total_seconds()
            key = (raid["name"],
                   raid["next_time"].strftime("%Y-%m-%d %H:%M:%S"))

            is_dummy = (raid.get("type") == "dummy")

            # Alertas iniciais
            if is_dummy:
                # Alerta 2min antes
                if 110 <= time_diff <= 130 and key not in alerted:
                    success, message_id = send_webhook_message(raid, time_diff)
                    if success:
                        alerted.add(key)
                        sent_messages[key] = {
                            'message_id': message_id,
                            'raid_time': raid["next_time"],
                            'last_update': now,
                        }
            else:
                # Alerta 10min antes
                if 590 <= time_diff <= 610 and key not in alerted:
                    success, message_id = send_webhook_message(raid, time_diff)
                    if success:
                        alerted.add(key)
                        sent_messages[key] = {
                            'message_id': message_id,
                            'raid_time': raid["next_time"],
                            'last_update': now,
                        }

            # Atualizações posteriores
            if key in sent_messages:
                message_data = sent_messages[key]
                status, _ = get_raid_status(time_diff, raid.get("type"))

                # Continuar a editar até garantir que chegou a "finished"
                still_relevant = True
                if status == "finished":
                    # ainda permite edições até 10min depois só para garantir a transição
                    still_relevant = (
                        now -
                        message_data['last_update']).total_seconds() < 600

                if still_relevant and (now - message_data['last_update']
                                       ).total_seconds() >= 60:
                    if edit_webhook_message(message_data['message_id'], raid,
                                            time_diff):
                        sent_messages[key]['last_update'] = now

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    if WEBHOOK_URL:
        main()
    else:
        print("❌ Configure DISCORD_WEBHOOK antes de continuar.")
