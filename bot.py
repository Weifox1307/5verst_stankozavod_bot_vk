import os
import requests
import random
import sys
import time
from datetime import datetime, timedelta, timezone

# --- НАСТРОЙКИ ---
VK_TOKEN = os.getenv('VK_TOKEN')
CHAT_IDS_RAW = os.getenv('VK_CHAT_IDS', '')
VK_GROUP_ID = os.getenv('VK_GROUP_ID', '228375526') 

try:
    CHAT_IDS = [int(i.strip()) for i in CHAT_IDS_RAW.split(',') if i.strip()]
except ValueError as e:
    print(f"Ошибка парсинга ID чатов: {e}")
    sys.exit(1)

LAT = 56.2874
LON = 43.9160

def get_moscow_now():
    return datetime.now(timezone(timedelta(hours=3)))

def get_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,precipitation_probability,weathercode&timezone=Europe%2FMoscow&forecast_days=1"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        temp = data['hourly']['temperature_2m'][9]
        prob = data['hourly']['precipitation_probability'][9]
        code = data['hourly']['weathercode'][9]
        weather_map = {0: "Ясно ☀️", 1: "Преимущественно ясно 🌤", 2: "Переменная облачность ⛅", 3: "Пасмурно ☁️", 45: "Туман 🌫️", 51: "Морось 🌧️", 61: "Небольшой дождь 🌦️", 63: "Дождь ☔", 71: "Небольшой снег ❄️", 73: "Снегопад 🌨️", 80: "Ливневый дождь ⛈️"}
        status = weather_map.get(code, "Облачно ☁️")
        return (f"🌳 ПОГОДА НА СТАРТЕ В 09:00:\n\n🌡 Температура: {temp}°C\n☁ На улице: {status}\n☔ Вероятность осадков: {prob}%\n\nОдевайтесь по погоде и до встречи в парке Станкозавода! 🧡")
    except Exception as e:
        print(f"Ошибка получения погоды: {e}")
        return None

def parse_birthdays(items, today, current_month):
    """Парсит список пользователей и ищет именинников"""
    found_now = []
    found_month = []
    
    for m in items:
        bd = m.get('bdate', '')
        if bd and bd.count('.') >= 1:
            try:
                parts = bd.split('.')
                day, month = int(parts[0]), int(parts[1])
                fmt_bd = f"{day:02d}.{month:02d}"
                name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip()
                
                if fmt_bd == today:
                    found_now.append(f"[id{m['id']}|{name}]")
                if f".{month:02d}" == current_month:
                    found_month.append(f"{name} ({fmt_bd})")
            except:
                continue
    return found_now, found_month

def get_all_potential_birthdays():
    now = get_moscow_now()
    today = now.strftime("%d.%m")
    current_month = now.strftime(".%m")
    
    all_users = {} # Используем словарь, чтобы избежать дубликатов по ID

    # 1. Получаем участников группы
    print(f"DEBUG: Получаем участников группы {VK_GROUP_ID}...")
    offset = 0
    while True:
        res = requests.get("https://api.vk.com/method/groups.getMembers", params={
            "group_id": VK_GROUP_ID, "fields": "bdate", "offset": offset,
            "count": 1000, "access_token": VK_TOKEN, "v": "5.131"
        }).json()
        items = res.get('response', {}).get('items', [])
        if not items: break
        for u in items: all_users[u['id']] = u
        offset += len(items)
        if len(items) < 1000: break
        time.sleep(0.2)

    # 2. Получаем участников из каждого чата
    for chat_id in CHAT_IDS:
        print(f"DEBUG: Получаем участников чата {chat_id}...")
        res = requests.get("https://api.vk.com/method/messages.getConversationMembers", params={
            "peer_id": chat_id, "fields": "bdate", "access_token": VK_TOKEN, "v": "5.131"
        }).json()
        # Данные лежат в response['profiles']
        profiles = res.get('response', {}).get('profiles', [])
        for u in profiles:
            all_users[u['id']] = u
        time.sleep(0.2)

    print(f"DEBUG: Всего уникальных людей собрано: {len(all_users)}")
    
    celebrants, may_list = parse_birthdays(all_users.values(), today, current_month)
    
    print(f"DEBUG: Именинники месяца: {', '.join(may_list) if may_list else 'Никого'}")
    
    if celebrants:
        # Убираем возможные дубли в именах (если один человек в разных чатах)
        celebrants = list(set(celebrants))
        return f"🥳 С ДНЁМ РОЖДЕНИЯ! 🎂\n\nСегодня праздник у: {', '.join(celebrants)}! 🎉🧡\nЖелаем лёгких ног, ярких стартов и отличного настроения!"
    return None

def send_vk_message(peer_id, text):
    if not text: return
    params = {"access_token": VK_TOKEN, "peer_id": peer_id, "message": text, "random_id": random.randint(1, 2**31), "v": "5.131"}
    res = requests.post("https://api.vk.com/method/messages.send", data=params).json()
    if "error" in res:
        print(f"Ошибка отправки в {peer_id}: {res['error']['error_msg']}")
    else:
        print(f"Успешно отправлено в {peer_id}")

if __name__ == "__main__":
    if not VK_TOKEN:
        print("Ошибка: VK_TOKEN не найден!"); sys.exit(1)
    
    now_msk = get_moscow_now()
    
    # Погода по субботам
    if now_msk.weekday() == 5:
        weather_text = get_weather()
        if weather_text:
            for chat in CHAT_IDS: send_vk_message(chat, weather_text)
    
    # Дни рождения всегда
    birthday_text = get_all_potential_birthdays()
    if birthday_text:
        for chat in CHAT_IDS: send_vk_message(chat, birthday_text)
    else:
        print("Именинников сегодня не найдено.")
