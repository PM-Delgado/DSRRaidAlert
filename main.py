import os
import requests
import time
from datetime import datetime, timedelta
from pytz import timezone
from bs4 import BeautifulSoup

# Configurações
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")  # define no Replit
CHECK_INTERVAL = 60  # segundos

# Fuso horário da Coreia
KST = timezone("Asia/Seoul")


def fetch_raid_info():
    url = "https://dsrwiki.com/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Exemplo tentativo: encontramos algo como:
    # <div id="raid-timer">14:30 (KST) - Map Name</div>
    div = soup.find("div", id="raid-timer")
    if not div:
        return None, None, None

    text = div.get_text(strip=True)
    # Aqui terás de adaptar o parsing conforme o formato real:
    # por exemplo "14:30 KST – Shibuya"
    try:
        time_str, map_name = text.split("–", 1)
        map_name = map_name.strip()
        raid_time = datetime.strptime(time_str.strip(), "%H:%M").time()
    except ValueError as e:
        print(f"❌ Erro no formato da data/hora: {e} | texto: {text}")
        return None, None, None
    except Exception as e:
        print(f"❌ Erro no parsing: {e} | texto: {text}")
        return None, None, None

    # Criar datetime completo com a próxima ocorrência da hora
    now_kst = datetime.now(KST)
    raid_dt = datetime.combine(now_kst.date(), raid_time, tzinfo=KST)
    if raid_dt < now_kst:
        raid_dt += timedelta(days=1)
    return raid_dt, map_name, soup


def send_webhook_alert(map_name, image_url=None, map_url=None):
    if not WEBHOOK_URL:
        print("⚠️ Erro: DISCORD_WEBHOOK não está configurado nas variáveis de ambiente")
        return False
    
    content = f"@everyone Raid **{map_name}** starting in 10 minutes!"
    payload = {"content": content}
    
    if image_url or map_url:
        embed = {}
        if image_url:
            embed["image"] = {"url": image_url}
        if map_url:
            embed["thumbnail"] = {"url": map_url}
        if embed:
            embeds = [embed]
            payload["embeds"] = embeds
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print(f"✅ Alerta enviado com sucesso para {map_name}")
            return True
        else:
            print(f"❌ Erro ao enviar webhook: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erro na requisição webhook: {e}")
        return False


def main():
    alerted_dates = set()
    while True:
        raid_dt, map_name, soup = fetch_raid_info()
        if raid_dt and map_name:
            now = datetime.now(KST)
            diff = (raid_dt - now).total_seconds()
            date_key = (raid_dt.date(), map_name)
            if 9 * 60 <= diff <= 10 * 60 and date_key not in alerted_dates:
                # Extra: extrair imagens se possível
                image_url = None
                map_url = None
                # Exemplo fictício:
                # img = soup.find("img", {"class": "boss-img"})
                # if img: image_url = img["src"]

                send_webhook_alert(map_name, image_url, map_url)
                alerted_dates.add(date_key)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    def send_test_message():
        if not WEBHOOK_URL:
            print("⚠️ DISCORD_WEBHOOK não configurado. Defina a variável de ambiente primeiro.")
            return False
        
        try:
            response = requests.post(WEBHOOK_URL, json={"content": "🚀 Teste bem-sucedido do Replit para o Discord!"})
            if response.status_code == 204:
                print("✅ Mensagem de teste enviada com sucesso!")
                return True
            else:
                print(f"❌ Erro no teste: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Erro na mensagem de teste: {e}")
            return False

    print("🔍 Iniciando Discord Raid Bot...")
    if send_test_message():
        print("🚀 Bot iniciado com sucesso! Monitorando raids...")
        main()
    else:
        print("❌ Configure DISCORD_WEBHOOK antes de continuar.")
