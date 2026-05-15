import os
import requests
import random
import pytz
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ ---
LOCATION_ID = "parkstankozavoda"
EVENT_ID = 10061
PEER_ID = os.getenv("PEER_ID")
VK_TOKEN = os.getenv("VK_TOKEN")
NRMS_USER = os.getenv("NRMS_USERNAME")
NRMS_PASS = os.getenv("NRMS_PASSWORD")

def get_detailed_results(date_str):
    # Дата приходит в формате 2026-05-09, переводим в 09.05.2026
    url_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    url = f"https://5verst.ru/{LOCATION_ID}/results/{url_date}/"
    
    # Очень важные заголовки, чтобы сайт думал, что мы человек
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    res = {"count": 0, "url": url, "new_total": [], "new_location": [], "pbs": []}
    
    try:
        print(f"Запрос к: {url}")
        r = requests.get(url, headers=headers, timeout=20)
        print(f"Статус ответа сайта: {r.status_code}")
        
        if r.status_code != 200:
            return res
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Ищем таблицу. На 5верст она может быть .results-table или просто .sortable
        table = soup.select_one(".results-table") or soup.select_one("table.sortable") or soup.find("table")
        
        if table:
            rows = table.find_all('tr')[1:] # Пропускаем шапку
            res["count"] = len(rows)
            print(f"Найдено строк в таблице: {res['count']}")
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 9: continue
                
                # Имя обычно во второй колонке
                name = cols[1].get_text(strip=True).split('\n')[0]
                
                # Индексы могут меняться, пробуем стандартные (7-Всего, 8-Локация, 9-ЛР)
                try:
                    total_runs = cols[7].get_text(strip=True)
                    loc_runs = cols[8].get_text(strip=True)
                    pb_status = cols[9].get_text(strip=True)
                    
                    if total_runs == "1": res["new_total"].append(name)
                    elif loc_runs == "1": res["new_location"].append(name)
                    if "ЛР" in pb_status: res["pbs"].append(name)
                except:
                    continue
        else:
            print("Таблица с результатами не найдена на странице.")
            
    except Exception as e:
        print(f"Ошибка при парсинге: {e}")
        
    return res

# Остальные функции (NRMS_API, get_next_start_info, send_to_vk) берем из предыдущего кода...
# Оставляю их без изменений для экономии места

class NRMS_API:
    def __init__(self, user, pwd):
        self.base_url = "https://nrms.5verst.ru/api/v1"
        self.headers = {"Content-Type": "application/json"}
        self.user, self.pwd = (user or ""), (pwd or "")

    def login(self):
        if not self.user or not self.pwd: return False
        try:
            r = requests.post(f"{self.base_url}/auth/login", 
                             json={"username": self.user, "password": self.pwd}, timeout=10)
            token = r.json().get("result", {}).get("token")
            if token:
                self.headers["Authorization"] = f"Bearer {token}"
                return True
        except: return False
        return False

    def get_volunteers(self, date_str):
        try:
            f_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            r = requests.post(f"{self.base_url}/event/volunteer/list", 
                             json={"event_id": EVENT_ID, "event_date": f_date}, 
                             headers=self.headers, timeout=15)
            return r.json().get("result", {}).get("volunteer_list", [])
        except: return []

def send_to_vk(message):
    url = "https://api.vk.com/method/messages.send"
    params = {
        "peer_id": PEER_ID, "message": message,
        "random_id": random.getrandbits(31),
        "access_token": VK_TOKEN, "v": "5.131"
    }
    return requests.post(url, params=params).json()

if __name__ == "__main__":
    # Настраиваем московское время
    tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(tz)

    # 1. Считаем дату ПРОШЕДШЕЙ или ТЕКУЩЕЙ субботы (для результатов)
    # Если запустить в субботу после 12:00-13:00, возьмет сегодняшнюю.
    offset = (now.weekday() - 5) % 7
    last_sat_dt = now - timedelta(days=offset)
    
    date_str = last_sat_dt.strftime("%Y-%m-%d")
    display_date = last_sat_dt.strftime("%d.%m.%Y")

    # 2. Считаем дату СЛЕДУЮЩЕЙ субботы (для анонса старта)
    next_sat_dt = last_sat_dt + timedelta(days=7)
    next_display_date = next_sat_dt.strftime("%d.%m.%Y")

    print(f"Ищем результаты за: {display_date}")

    # 3. Получаем результаты с сайта
    results = get_detailed_results(date_str)
    
    if results["count"] > 0:
        api = NRMS_API(NRMS_USER, NRMS_PASS)
        volunteers_text = ""
        organizers = []
        
        # Пытаемся зайти в NRMS
        if api.login():
            vols_raw = api.get_volunteers(date_str)
            if vols_raw:
                v_list = []
                for v in vols_raw:
                    name, role = v.get("full_name"), v.get("role_name")
                    v_list.append(f"• {name} — {role}")
                    if "Организатор" in role: organizers.append(name)
                volunteers_text = "\n".join(v_list)
        
        # Собираем сообщение
        msg = [
            f"🌳 5 вёрст в парке Станкозавода",
            f"🗓 Старт от {display_date}\n━━━━━━━━━━━━━━",
            f"🏁 Финишировало участников: {results['count']}",
            f"📊 Протокол: {results['url']}\n"
        ]
        
        if organizers:
            msg.insert(2, f"🔥 Организаторы: {', '.join(set(organizers))}\n")

        if results['new_total']:
            msg.append(f"🏃‍♂️ Новые участники:\n" + "\n".join(results['new_total']) + "\n")
        
        if results['new_location']:
            msg.append(f"🏃‍♂️ Впервые у нас:\n" + "\n".join(results['new_location']) + "\n")

        if results['pbs']:
            msg.append(f"🥇 Личные рекорды:\n" + "\n".join(results['pbs']) + "\nПоздравляем! 🎉\n")

        if volunteers_text:
            msg.append(f"🍃 Герои нашего старта — волонтеры:\n{volunteers_text}\n")

        msg.append(f"━━━━━━━━━━━━━━\n📅 СЛЕДУЮЩИЙ СТАРТ: {next_display_date}\n⏰ Время: 08:40\nЖдём вас! 🙌")
        
        final_msg = "\n".join(msg)
        print(final_msg)
        
        if VK_TOKEN and PEER_ID:
            send_to_vk(final_msg)
    else:
        print(f"Результаты за {display_date} пока не заг
