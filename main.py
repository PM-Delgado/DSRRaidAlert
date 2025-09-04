import os
import math
import requests
import time
from datetime import datetime, timedelta
from pytz import timezone

# -----------------------
# Config
# -----------------------
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
CHECK_INTERVAL = 5  # loop a cada 5s

# Timezones
KST = timezone("Asia/Seoul")
BRT = timezone("America/Sao_Paulo")

SCRIPT_START_TIME = None
sent_messages = {
}  # key -> { message_id, raid_time, last_min, last_status, last_update }


# -----------------------
# Utilitários
# -----------------------
def get_image_path(name):
    safe_name = name.replace(":", "_")
    return f"https://media.dsrwiki.com/dsrwiki/digimon/{safe_name}/{safe_name}.webp"


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


def get_aligned_dummy_time(minutes_offset):
    now = get_current_kst()
    base = now.replace(second=0, microsecond=0)
    if now.second > 0:
        base += timedelta(minutes=1)
    return base + timedelta(minutes=minutes_offset)


# Tradução EN -> KR
map_translation = {
    "Shibuya": "시부야",
    "Valley of Darkness": "어둠성 계곡",
    "Campground": "캠핑장",
    "Subway Station": "지하철 역",
    "???": "???",
    "🧪 Test Zone Alpha": "시부야",
    "🧪 Test Zone Beta": "어둠성 계곡",
    "🧪 Test Zone Gamma": "캠핑장",
    "🧪 Test Zone Delta": "지하철 역",
}


def get_map_image_url(map_name):
    kr_name = map_translation.get(map_name)
    if not kr_name:
        return None
    if kr_name == "???":
        return "https://media.dsrwiki.com/dsrwiki/map/ApocalymonArea.webp"
    safe_name = "".join(kr_name.split())
    return f"https://media.dsrwiki.com/dsrwiki/map/{safe_name}.webp"


# -----------------------
# Status / cores
# -----------------------
def compute_status(time_diff_seconds, is_dummy):
    td = time_diff_seconds
    if is_dummy:
        if td >= 120:
            return "upcoming"
        elif 60 <= td < 120:
            return "starting"
        elif -59 <= td < 60:
            return "ongoing"
        else:
            return "finished"
    else:
        if td > 60:
            return "upcoming"
        elif 0 <= td <= 60:
            return "starting"
        elif -300 <= td < 0:
            return "ongoing"
        else:
            return "finished"


def get_raid_status(time_diff_seconds, raid_type):
    is_dummy = (raid_type == "dummy")
    status = compute_status(time_diff_seconds, is_dummy)
    color = {
        "upcoming": 0xFF0000,
        "starting": 0xFFFF00,
        "ongoing": 0x00FF00,
        "finished": 0x808080,
    }[status]
    return status, color


# -----------------------
# Raids (reais + dummies)
# -----------------------
def get_raids_list():
    base_raids = [
        {
            "name": "Pumpmon",
            "image": get_image_path("펌프몬"),
            "times": ["19:30", "21:30"],
            "type": "daily",
            "map": "Shibuya"
        },
        {
            "name": "Woodmon",
            "image": get_image_path("울퉁몬"),
            "times": ["23:00", "01:00"],
            "type": "daily",
            "map": "Shibuya"
        },
        {
            "name": "BlackSeraphimon",
            "image": get_image_path("블랙세라피몬"),
            "times": ["23:00"],
            "type": "biweekly",
            "baseDate": "2025-05-31",
            "map": "???"
        },
        {
            "name": "Ophanimon: Falldown Mode",
            "image": get_image_path("오파니몬:폴다운모드"),
            "times": ["23:00"],
            "type": "biweekly",
            "baseDate": "2025-06-07",
            "map": "???"
        },
        {
            "name": "Megidramon",
            "image": get_image_path("메기드라몬"),
            "times": ["22:00"],
            "type": "biweekly",
            "baseDate": "2025-06-08",
            "map": "???"
        },
        {
            "name": "Omegamon",
            "image": get_image_path("오메가몬"),
            "times": ["22:00"],
            "type": "biweekly",
            "baseDate": "2025-06-01",
            "map": "Valley of Darkness"
        },
    ]

    dummy_raids = [
        {
            "name": "🔥 TEST_BOSS_1",
            "image": get_image_path("오메가몬"),
            "type": "dummy",
            "map": "🧪 Test Zone Alpha",
            "raid_time": get_aligned_dummy_time(2)
        },
        {
            "name": "⚡ TEST_BOSS_2",
            "image": get_image_path("메기드라몬"),
            "type": "dummy",
            "map": "🧪 Test Zone Beta",
            "raid_time": get_aligned_dummy_time(3)
        },
        {
            "name": "💀 TEST_BOSS_3",
            "image": get_image_path("블랙세라피몬"),
            "type": "dummy",
            "map": "🧪 Test Zone Gamma",
            "raid_time": get_aligned_dummy_time(4)
        },
        {
            "name": "👑 TEST_BOSS_4",
            "image": get_image_path("오파니몬:폴다운모드"),
            "type": "dummy",
            "map": "🧪 Test Zone Delta",
            "raid_time": get_aligned_dummy_time(5)
        },
    ]

    return base_raids + dummy_raids


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
                })
    all_raids.sort(key=lambda r: r["next_time"])
    return all_raids


# -----------------------
# Webhook helpers
# -----------------------
def _webhook_post_url_wait_true():
    return WEBHOOK_URL + ("&" if "?" in WEBHOOK_URL else "?") + "wait=true"


def create_embed_content(raid, time_until_raid_seconds):
    brt_time = raid["next_time"].astimezone(BRT)
    minutes_until = max(0, math.ceil(time_until_raid_seconds / 60.0))

    clean_name = raid['name'].replace('🔥 ', '').replace('⚡ ', '').replace(
        '💀 ', '').replace('👑 ', '')
    status, color = get_raid_status(time_until_raid_seconds, raid.get("type"))

    if status in ("upcoming", "starting"):
        desc_status = f"⏳ **Tempo restante:** {minutes_until}min"
    elif status == "ongoing":
        desc_status = "⚔️ **Raid em andamento!**"
    else:
        desc_status = "✅ **Raid finalizada!**"

    embed = {
        "title": f"🚨 {clean_name}",
        "description":
        f"📍 **Mapa:** {raid['map']}\\n⏰ **Horário:** {brt_time.strftime('%H:%M')}\\n{desc_status}",
        "color": color,
        "thumbnail": {
            "url": raid["image"]
        },
        "footer": {
            "text":
            "DSR Raid Timer | Teste de Alertas"
            if raid.get("type") == "dummy" else "DSR Raid Timer"
        },
    }

    map_image_url = get_map_image_url(raid['map'])
    if map_image_url:
        embed["image"] = {"url": map_image_url}

    return embed


def send_webhook_message(raid, time_until_raid_seconds):
    if not WEBHOOK_URL:
        print("⚠️ Erro: DISCORD_WEBHOOK não está configurado")
        return False, None

    embed = create_embed_content(raid, time_until_raid_seconds)
    minutes_until = max(0, math.ceil(time_until_raid_seconds / 60.0))

    if raid.get("type") == "dummy":
        content = f"🧪 **TESTE DE ALERTA** - {raid['name']} começa em {minutes_until} minutos!"
    else:
        content = f"@everyone 🚨 Raid **{raid['name']}** começa em {minutes_until} minutos!"

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
    minutes_until = max(0, math.ceil(time_until_raid_seconds / 60.0))

    if raid.get("type") == "dummy":
        if status == "upcoming":
            content = f"🧪 **TESTE DE ALERTA** - {raid['name']} começa em {minutes_until} minutos!"
        elif status == "starting":
            content = f"🧪 **TESTE DE ALERTA** - {raid['name']} começando em 1 minuto!"
        elif status == "ongoing":
            content = f"⚔️ {raid['name']} está em andamento!"
        else:
            content = f"✅ {raid['name']} foi finalizada!"
    else:
        if status == "upcoming":
            content = f"@everyone 🚨 Raid **{raid['name']}** começa em {minutes_until} minutos!"
        elif status == "starting":
            content = f"@everyone ⚡ Raid **{raid['name']}** começando em 1 minuto!"
        elif status == "ongoing":
            content = f"⚔️ Raid **{raid['name']}** está em andamento!"
        else:
            content = f"✅ Raid **{raid['name']}** foi finalizada!"

    payload = {"content": content, "embeds": [embed]}
    edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"

    try:
        response = requests.patch(edit_url, json=payload)
        if response.status_code == 200:
            print(
                f"✏️ Mensagem atualizada para {raid['name']} ({status}, {minutes_until}min)"
            )
            return True
        else:
            print(
                f"❌ Erro ao editar mensagem: {response.status_code} - {response.text}"
            )
            return False
    except Exception as e:
        print(f"❌ Erro na edição: {e}")
        return False


# -----------------------
# Main loop
# -----------------------
def main():
    if not WEBHOOK_URL:
        print("❌ Configure DISCORD_WEBHOOK antes de continuar.")
        return

    print("🔍 Iniciando Discord Raid Bot...")
    alerted = set()

    while True:
        now = get_current_kst()
        upcoming_raids = get_upcoming_raids()

        for raid in upcoming_raids:
            time_diff = (raid["next_time"] - now).total_seconds()
            is_dummy = (raid.get("type") == "dummy")

            if is_dummy:
                key = raid["name"]
                if 110 <= time_diff <= 130 and key not in alerted:
                    success, message_id = send_webhook_message(raid, time_diff)
                    if success:
                        print(
                            f"📢 Dummy {raid['name']} agendada ({time_diff:.0f}s restantes)"
                        )
                        alerted.add(key)
                        last_min = max(0, math.ceil(time_diff / 60.0))
                        last_status = compute_status(time_diff, True)
                        sent_messages[key] = {
                            'message_id': message_id,
                            'raid_time': raid["next_time"],
                            'last_min': last_min,
                            'last_status': last_status,
                            'last_update': now
                        }
            else:
                key = (raid["name"],
                       raid["next_time"].strftime("%Y-%m-%d %H:%M:%S"))
                if 590 <= time_diff <= 610 and key not in alerted:
                    success, message_id = send_webhook_message(raid, time_diff)
                    if success:
                        print(
                            f"📢 Raid real {raid['name']} agendada ({time_diff/60:.1f}min restantes)"
                        )
                        alerted.add(key)
                        last_min = max(0, math.ceil(time_diff / 60.0))
                        last_status = compute_status(time_diff, False)
                        sent_messages[key] = {
                            'message_id': message_id,
                            'raid_time': raid["next_time"],
                            'last_min': last_min,
                            'last_status': last_status,
                            'last_update': now
                        }

        for key, data in list(sent_messages.items()):
            message_id = data['message_id']
            raid_time = data['raid_time']
            raid_name = key if isinstance(key, str) else key[0]
            raid = next((r for r in upcoming_raids if r["name"] == raid_name),
                        None)
            if not raid:
                continue

            time_diff = (raid["next_time"] - now).total_seconds()
            is_dummy = (raid.get("type") == "dummy")
            current_status = compute_status(time_diff, is_dummy)
            current_min = max(0, math.ceil(time_diff / 60.0))

            if current_min != data.get(
                    'last_min') or current_status != data.get('last_status'):
                if edit_webhook_message(message_id, raid, time_diff):
                    print(
                        f"🔄 Update {raid_name}: {current_status}, {current_min}min restantes"
                    )
                    sent_messages[key]['last_min'] = current_min
                    sent_messages[key]['last_status'] = current_status
                    sent_messages[key]['last_update'] = now

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
