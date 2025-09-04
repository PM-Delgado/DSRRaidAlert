import os
import requests
import time
from datetime import datetime, timedelta
from pytz import timezone

# Configurações
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")  # define no Replit
CHECK_INTERVAL = 30  # segundos

# Timezones
KST = timezone("Asia/Seoul")
BRT = timezone("America/Sao_Paulo")

# ---------- Funções utilitárias ----------


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


# ---------- Lista de Raids (traduzida) ----------

raids = [
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
    # Dummy raid para teste em 10 minutos
    {
        "name": "TEST_BOSS",
        "image": get_image_path("오메가몬"),
        "times":
        [(get_current_kst() + timedelta(minutes=10)).strftime("%H:%M")],
        "type": "daily",
        "map": "Test Zone"
    },
]


def get_upcoming_raids():
    all_raids = []
    for raid in raids:
        for t in raid["times"]:
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
                "next_time": next_time
            })
    all_raids.sort(key=lambda r: r["next_time"])
    return all_raids


# ---------- Webhook ----------


def send_webhook_alert(raid):
    if not WEBHOOK_URL:
        print(
            "⚠️ Erro: DISCORD_WEBHOOK não está configurado nas variáveis de ambiente"
        )
        return False

    # Converter horário para Brasília
    brt_time = raid["next_time"].astimezone(BRT)

    content = f"@everyone Raid **{raid['name']}** in **{raid['map']}** starts in 10 minutes!"
    embed = {
        "title": raid["name"],
        "description":
        f"Map: {raid['map']}\nTime: {brt_time.strftime('%H:%M %Z')}",
        "image": {
            "url": raid["image"]
        },
    }
    payload = {"content": content, "embeds": [embed]}

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print(f"✅ Alert sent successfully for {raid['name']}")
            return True
        else:
            print(f"❌ Webhook error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Webhook request error: {e}")
        return False


# ---------- Main Loop ----------


def main():
    alerted = set()
    while True:
        now = get_current_kst()
        for raid in get_upcoming_raids():
            diff = (raid["next_time"] - now).total_seconds()
            key = (raid["name"], raid["next_time"].strftime("%Y-%m-%d %H:%M"))
            if 9 * 60 <= diff <= 10 * 60 and key not in alerted:
                send_webhook_alert(raid)
                alerted.add(key)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    print(
        "🔍 Starting Discord Raid Bot with translated raids and Brasília timezone..."
    )
    if WEBHOOK_URL:
        main()
    else:
        print("❌ Configure DISCORD_WEBHOOK before continuing.")
