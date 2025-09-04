import os
import requests
import time
from datetime import datetime, timedelta
from pytz import timezone

# Configurações
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")  # define no Replit
CHECK_INTERVAL = 5  # reduzido para 5 segundos para melhor precisão nos testes

# Timezones
KST = timezone("Asia/Seoul")
BRT = timezone("America/Sao_Paulo")

# Timestamp de início do script (para calcular os dummy raids)
SCRIPT_START_TIME = None

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


def get_dummy_raid_time(minutes_offset, seconds_offset=0):
    """Calcula o horário da dummy raid baseado no início do script"""
    global SCRIPT_START_TIME
    if SCRIPT_START_TIME is None:
        SCRIPT_START_TIME = get_current_kst()
        print(
            f"🚀 Script iniciado em: {SCRIPT_START_TIME.strftime('%H:%M:%S')} KST"
        )

    # A raid acontece no tempo especificado
    # O alerta será enviado 10 minutos antes (para raids normais) ou no momento exato (para dummy)
    raid_time = SCRIPT_START_TIME + timedelta(minutes=minutes_offset,
                                              seconds=seconds_offset)
    return raid_time


def get_map_image_url(map_name):
    """Retorna URL da imagem do mapa baseado no nome"""
    map_images = {
        "Shibuya":
        "https://media.dsrwiki.com/dsrwiki/map/shibuya/shibuya.webp",
        "Valley of Darkness":
        "https://media.dsrwiki.com/dsrwiki/map/valley_of_darkness/valley_of_darkness.webp",
        "🧪 Test Zone Alpha":
        "https://media.dsrwiki.com/dsrwiki/map/shibuya/shibuya.webp",  # Usar Shibuya como exemplo
        "🧪 Test Zone Beta":
        "https://media.dsrwiki.com/dsrwiki/map/shibuya/shibuya.webp",
        "🧪 Test Zone Gamma":
        "https://media.dsrwiki.com/dsrwiki/map/shibuya/shibuya.webp",
        "🧪 Test Zone Delta":
        "https://media.dsrwiki.com/dsrwiki/map/shibuya/shibuya.webp",
        "???": None  # Sem imagem para mapas desconhecidos
    }
    return map_images.get(map_name, None)


# ---------- Lista de Raids ----------


def get_raids_list():
    """Retorna a lista de raids, incluindo as dummy raids calculadas dinamicamente"""
    base_raids = [{
        "name": "Pumpmon",
        "image": get_image_path("펌프몬"),
        "times": ["19:30", "21:30"],
        "type": "daily",
        "map": "Shibuya"
    }, {
        "name": "Woodmon",
        "image": get_image_path("울퉁몬"),
        "times": ["23:00", "01:00"],
        "type": "daily",
        "map": "Shibuya"
    }, {
        "name": "BlackSeraphimon",
        "image": get_image_path("블랙세라피몬"),
        "times": ["23:00"],
        "type": "biweekly",
        "baseDate": "2025-05-31",
        "map": "???"
    }, {
        "name": "Ophanimon: Falldown Mode",
        "image": get_image_path("오파니몬:폴다운모드"),
        "times": ["23:00"],
        "type": "biweekly",
        "baseDate": "2025-06-07",
        "map": "???"
    }, {
        "name": "Megidramon",
        "image": get_image_path("메기드라몬"),
        "times": ["22:00"],
        "type": "biweekly",
        "baseDate": "2025-06-08",
        "map": "???"
    }, {
        "name": "Omegamon",
        "image": get_image_path("오메가몬"),
        "times": ["22:00"],
        "type": "biweekly",
        "baseDate": "2025-06-01",
        "map": "Valley of Darkness"
    }]

    # Adicionar dummy raids para teste
    # As raids acontecem nos tempos especificados, mas os alertas são enviados 10min antes
    dummy_raids = [
        {
            "name": "🔥 TEST_BOSS_1",
            "image": get_image_path("오메가몬"),
            "type": "dummy",
            "map": "🧪 Test Zone Alpha",
            "raid_time":
            get_dummy_raid_time(20, 30)  # Raid em 20min30s, alerta em 10min30s
        },
        {
            "name": "⚡ TEST_BOSS_2",
            "image": get_image_path("메기드라몬"),
            "type": "dummy",
            "map": "🧪 Test Zone Beta",
            "raid_time":
            get_dummy_raid_time(21, 0)  # Raid em 21min, alerta em 11min
        },
        {
            "name": "💀 TEST_BOSS_3",
            "image": get_image_path("블랙세라피몬"),
            "type": "dummy",
            "map": "🧪 Test Zone Gamma",
            "raid_time":
            get_dummy_raid_time(21, 30)  # Raid em 21min30s, alerta em 11min30s
        },
        {
            "name": "👑 TEST_BOSS_4",
            "image": get_image_path("오파니몬:폴다운모드"),
            "type": "dummy",
            "map": "🧪 Test Zone Delta",
            "raid_time":
            get_dummy_raid_time(22, 0)  # Raid em 22min, alerta em 12min
        }
    ]

    return base_raids + dummy_raids


def get_upcoming_raids():
    all_raids = []
    raids = get_raids_list()

    for raid in raids:
        if raid["type"] == "dummy":
            # Para dummy raids, usar o horário pré-calculado
            all_raids.append({
                "name": raid["name"],
                "map": raid["map"],
                "image": raid["image"],
                "next_time": raid["raid_time"],
                "type": "dummy"
            })
        else:
            # Para raids normais, calcular próximo horário
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
                    "type": raid["type"]
                })

    all_raids.sort(key=lambda r: r["next_time"])
    return all_raids


# ---------- Webhook ----------


def send_webhook_alert(raid, time_until_raid_seconds):
    if not WEBHOOK_URL:
        print(
            "⚠️ Erro: DISCORD_WEBHOOK não está configurado nas variáveis de ambiente"
        )
        return False

    # Converter horário para Brasília (UTC-3)
    brt_time = raid["next_time"].astimezone(BRT)

    # Calcular tempo restante correto
    minutes_until = int(time_until_raid_seconds // 60)
    seconds_until = int(time_until_raid_seconds % 60)

    # Mensagem principal
    if raid.get("type") == "dummy":
        content = f"🧪 **TESTE DE ALERTA** - {raid['name']} começa em {minutes_until} minutos!"
    else:
        content = f"@everyone 🚨 Raid **{raid['name']}** começa em {minutes_until} minutos!"

    # Título do embed - limpar emojis do nome
    clean_name = raid['name'].replace('🔥 ', '').replace('⚡ ', '').replace(
        '💀 ', '').replace('👑 ', '')

    # Formato anterior mais organizado
    embed = {
        "title": f"🚨 {clean_name}",
        "description":
        f"📍 **Mapa:** {raid['map']}\n⏰ **Horário:** {brt_time.strftime('%H:%M %Z')}\n⏳ **Tempo restante:** {minutes_until} minutos",
        "color": 0xFF6B00 if raid.get("type") == "dummy" else
        0xFF0000,  # Laranja para teste, vermelho para normal
        "thumbnail": {
            "url": raid["image"]
        },
        "footer": {
            "text":
            "DSR Raid Timer | Teste de Alertas"
            if raid.get("type") == "dummy" else "DSR Raid Timer"
        }
    }

    # Adicionar imagem do mapa se disponível
    map_image_url = get_map_image_url(raid['map'])
    if map_image_url:
        embed["image"] = {"url": map_image_url}
        print(f"🗺️ URL do mapa: {map_image_url}")  # Debug para verificar a URL

    payload = {"content": content, "embeds": [embed]}

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            if raid.get("type") == "dummy":
                print(
                    f"✅ 🧪 TESTE: Alerta enviado para {raid['name']} ({minutes_until}min {seconds_until}s restantes)"
                )
            else:
                print(
                    f"✅ Alerta enviado com sucesso para {raid['name']} ({minutes_until}min restantes)"
                )
            return True
        else:
            print(
                f"❌ Erro no webhook: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erro na requisição do webhook: {e}")
        return False


# ---------- Main Loop ----------


def main():
    print(
        "🔍 Iniciando Discord Raid Bot com raids traduzidas e timezone de Brasília..."
    )
    print("🧪 Modo de teste ativado - Dummy raids configuradas!")

    alerted = set()

    while True:
        now = get_current_kst()
        upcoming_raids = get_upcoming_raids()

        # Mostrar próximas raids (apenas uma vez a cada 30 segundos para não spammar)
        if now.second % 30 == 0:
            print(f"\n⏰ Hora atual (KST): {now.strftime('%H:%M:%S')}")
            print("📋 Próximas raids:")
            for i, raid in enumerate(upcoming_raids[:5]):
                time_diff = (raid["next_time"] - now).total_seconds()
                mins = int(abs(time_diff) // 60)
                secs = int(abs(time_diff) % 60)
                status = "⚠️ TESTE" if raid.get("type") == "dummy" else "📅"
                time_prefix = "+" if time_diff < 0 else ""
                print(
                    f"  {status} {raid['name']} - {raid['map']} - {time_prefix}{mins:02d}:{secs:02d}"
                )

        # Verificar se precisa enviar novos alertas
        for raid in upcoming_raids:
            time_diff = (raid["next_time"] - now).total_seconds()
            key = (raid["name"],
                   raid["next_time"].strftime("%Y-%m-%d %H:%M:%S"))

            # Lógica de alerta: SEMPRE 10 minutos antes
            # Alertar quando restam entre 9min50s e 10min10s (590-610 segundos)
            if 590 <= time_diff <= 610 and key not in alerted:
                minutes_remaining = int(time_diff // 60)
                seconds_remaining = int(time_diff % 60)

                if raid.get("type") == "dummy":
                    print(
                        f"🧪 TESTE: Enviando alerta para {raid['name']} (faltam {minutes_remaining}min {seconds_remaining}s)"
                    )
                else:
                    print(
                        f"📢 Enviando alerta para {raid['name']} (faltam {minutes_remaining}min {seconds_remaining}s)"
                    )

                if send_webhook_alert(raid, time_diff):
                    alerted.add(key)

        # Limpar alertas antigos do cache (raids que já passaram há mais de 1 hora)
        current_time = get_current_kst()
        expired_keys = []
        for key in list(alerted):
            # Extrair timestamp do key (formato: "nome", "YYYY-MM-DD HH:MM:SS")
            try:
                raid_time_str = key[1]
                raid_time = datetime.strptime(raid_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
                if (current_time - raid_time).total_seconds() > 3600:  # 1 hora
                    expired_keys.append(key)
            except (IndexError, ValueError):
                # Se não conseguir parse do tempo, manter o key
                pass

        for key in expired_keys:
            alerted.discard(key)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    if WEBHOOK_URL:
        main()
    else:
        print("❌ Configure DISCORD_WEBHOOK antes de continuar.")
        print(
            "💡 Adicione sua URL do webhook do Discord nas variáveis de ambiente do Replit."
        )
