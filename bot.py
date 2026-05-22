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
except Exception as e:
    print(f"Ошибка CHAT_IDS: {e}")
    sys.exit(1)

LAT = 56.2874
LON = 43.9160

def get_moscow_now():
    return datetime.now(timezone(timedelta(hours=3)))

def get_weather():
    # Запрашиваем прогноз на сегодня
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,precipitation_probability,weathercode&timezone=Europe%2FMoscow&forecast_days=1"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Берем данные именно на 9 утра
        # Индекс 9 соответствует 09:00, если прогноз начался с 00:00
        temp = data['hourly']['temperature_2m'][9]
        prob = data['hourly']['precipitation_probability'][9]
        code = data['hourly']['weathercode'][9]
        
        weather_map = {
            0: "Ясно ☀️", 1: "Преимущественно ясно 🌤", 2: "Переменная облачность ⛅", 
            3: "Пасмурно ☁️", 45: "Туман 🌫️", 51: "Морось 🌧️", 61: "Небольшой дождь 🌦️", 
            63: "Дождь ☔", 71: "Небольшой снег ❄️", 73: "Снегопад 🌨️", 80: "Ливневый дождь ⛈️"
        }
        status = weather_map.get(code, "Облачно ☁️")
        
        return (f"🌳 ПОГОДА НА СТАРТЕ В 09:00:\n\n"
                f"🌡 Температура: {temp}°C\n"
                f"☁ На улице: {status}\n"
                f"☔ Вероятность осадков: {prob}%\n\n"
                f"Одевайтесь по погоде и до встречи в парке! 🧡")
    except Exception as e:
        print(f"Ошибка погоды: {e}")
        return None

def get_all_potential_birthdays():
    now = get_moscow_now()
    today_str = now.strftime("%d.%m")
    all_users = {}

    # 1. Из группы
    try:
        res = requests.get("https://api.vk.com/method/groups.getMembers", params={
            "group_id": VK_GROUP_ID, "fields": "bdate", "count": 1000,
            "access_token": VK_TOKEN, "v": "5.131"
        }).json()
        for u in res.get('response', {}).get('items', []):
            all_users[u['id']] = u
    except: pass

    # 2. Из чатов (нужны права админа у бота в чате!)
    for chat_id in CHAT_IDS:
        try:
            res = requests.get("https://api.vk.com/method/messages.getConversationMembers", params={
                "peer_id": chat_id, "fields": "bdate", "access_token": VK_TOKEN, "v": "5.131"
            }).json()
            for u in res.get('response', {}).get('profiles', []):
                all_users[u['id']] = u
        except: pass

    celebrants = []
    for u_id, u in all_users.items():
        bdate = u.get('bdate', '')
        if bdate:
            parts = bdate.split('.')
            if len(parts) >= 2:
                if f"{int(parts[0]):02d}.{int(parts[1]):02d}" == today_str:
                    name = f"{u.get('first_name')} {u.get('last_name')}"
                    celebrants.append(f"[id{u_id}|{name}]")

    if celebrants:
        names = ", ".join(list(set(celebrants)))
        return f"🥳 С ДНЁМ РОЖДЕНИЯ! 🎂\n\nСегодня праздник у: {names}! 🎉🧡\nЖелаем лёгких ног, ярких стартов и отличного настроения!"
    return None

def send_vk_message(peer_id, text):
    requests.post("https://api.vk.com/method/messages.send", data={
        "access_token": VK_TOKEN, "peer_id": peer_id, "message": text, 
        "random_id": random.randint(1, 2147483647), "v": "5.131"
    })

if __name__ == "__main__":
    now_msk = get_moscow_now()
    print(f"Запуск бота. Время МСК: {now_msk}")

    # 1. Погода (только по субботам)
    if now_msk.weekday() == 5:
        text = get_weather()
        if text:
            for chat in CHAT_IDS: send_vk_message(chat, text)
    
    # 2. Дни рождения (каждый день)
    text_bd = get_all_potential_birthdays()
    if text_bd:
        for chat in CHAT_IDS: send_vk_message(chat, text_bd)
    else:
        print("Именинников сегодня нет.")

# === (IoT Эмуляция) ===
    # Эмулируем получение данных с "Умного контроллера парка"
    park_device_status = random.choice(["ONLINE", "STANDBY"])
    sensor_humidity = random.randint(30, 80) # Эмуляция датчика влажности
    
    print(f"--- IoT System Status ---")
    print(f"Device ID: STANKO-PARK-01")
    print(f"Status: {park_device_status}")
    print(f"Sensor Data (Humidity): {sensor_humidity}%")
    
    # Если влажность слишком высокая (эмуляция дождя), шлем уведомление админу или в чат
    if sensor_humidity > 75:
        iot_msg = f"⚠️ [IoT-Sensor] В парке зафиксирована высокая влажность ({sensor_humidity}%). Рекомендуем проверить состояние трассы!"
        # for chat in CHAT_IDS: send_vk_message(chat, iot_msg)
