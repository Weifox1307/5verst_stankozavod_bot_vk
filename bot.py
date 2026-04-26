import os
import requests
import random
import sys
from datetime import datetime, timedelta, timezone

# --- НАСТРОЙКИ (берем из Secrets) ---
VK_TOKEN = os.getenv('VK_TOKEN')
CHAT_IDS_RAW = os.getenv('VK_CHAT_IDS', '')
# ID группы Станкозавода (нужен для получения списка участников)
# Если ID группы отличается, замените здесь или добавьте в Secrets
VK_GROUP_ID = os.getenv('VK_GROUP_ID', '213964402') 

print(f"DEBUG: Получена строка чатов длиной {len(CHAT_IDS_RAW)} символов")

# Парсим строку с ID в список чисел
try:
    CHAT_IDS = [int(i.strip()) for i in CHAT_IDS_RAW.split(',') if i.strip()]
    print(f"DEBUG: Распознано чатов: {len(CHAT_IDS)}")
except ValueError as e:
    print(f"Ошибка парсинга ID: {e}")
    sys.exit(1)

LAT = 56.2874
LON = 43.9160

def get_moscow_now():
    """Возвращает текущее время по Москве"""
    return datetime.now(timezone(timedelta(hours=3)))

def get_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,precipitation_probability,weathercode&timezone=Europe%2FMoscow&forecast_days=1"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        temp = data['hourly']['temperature_2m'][9]
        prob = data['hourly']['precipitation_probability'][9]
        code = data['hourly']['weathercode'][9]

        weather_map = {
            0: "Ясно ☀️", 1: "Преимущественно ясно 🌤", 2: "Переменная облачность ⛅", 3: "Пасмурно ☁️",
            45: "Туман 🌫️", 51: "Морось 🌧️", 61: "Небольшой дождь 🌦️", 63: "Дождь ☔",
            71: "Небольшой снег ❄️", 73: "Снегопад 🌨️", 80: "Ливневый дождь ⛈️"
        }
        status = weather_map.get(code, "Облачно ☁️")

        return (
            f"🌳 ПОГОДА НА СТАРТЕ В 09:00:\n\n"
            f"🌡 Температура: {temp}°C\n"
            f"☁ На улице: {status}\n"
            f"☔ Вероятность осадков: {prob}%\n\n"
            f"Одевайтесь по погоде и до встречи в парке Станкозавода! 🧡"
        )
    except Exception as e:
        print(f"Ошибка получения погоды: {e}")
        return None

def check_birthdays():
    """Проверяет дни рождения участников группы и возвращает текст поздравления"""
    try:
        now = get_moscow_now()
        today = now.strftime("%d.%m")
        
        params = {
            "group_id": VK_GROUP_ID,
            "fields": "bdate",
            "access_token": VK_TOKEN,
            "v": "5.131"
        }
        res = requests.get("https://api.vk.com/method/groups.getMembers", params=params, timeout=15).json()
        
        celebrants = []
        items = res.get('response', {}).get('items', [])
        
        for m in items:
            bd = m.get('bdate', '')
            # Проверяем формат даты (может быть D.M или D.M.YYYY)
            if bd and bd.count('.') >= 1:
                parts = bd.split('.')
                day_month = f"{int(parts[0]):02d}.{int(parts[1]):02d}"
                if day_month == today:
                    celebrants.append(f"[id{m['id']}|{m['first_name']} {m['last_name']}]")
        
        if celebrants:
            return f"🥳 С ДНЁМ РОЖДЕНИЯ! 🎂\n\nСегодня праздник у: {', '.join(celebrants)}! 🎉🧡\nЖелаем легких ног и отличного настроения!"
        return None
    except Exception as e:
        print(f"Ошибка при проверке именинников: {e}")
        return None

def send_vk_message(peer_id, text):
    if not text: return
    url = "https://api.vk.com/method/messages.send"
    params = {
        "access_token": VK_TOKEN,
        "peer_id": peer_id,
        "message": text,
        "random_id": random.randint(1, 2**31),
        "v": "5.131"
    }
    try:
        res = requests.post(url, data=params, timeout=10).json()
        if "error" in res:
            print(f"Ошибка ВК (ID {peer_id}): {res['error']['error_msg']}")
        else:
            print(f"Успешно отправлено в чат {peer_id}")
    except Exception as e:
        print(f"Ошибка сети: {e}")

if __name__ == "__main__":
    if not VK_TOKEN:
        print("Ошибка: VK_TOKEN не найден!")
        sys.exit(1)
    if not CHAT_IDS:
        print("Ошибка: Список чатов пуст!")
        sys.exit(1)

    # 1. Проверяем погоду
    weather_text = get_weather()
    if weather_text:
        for chat in CHAT_IDS:
            send_vk_message(chat, weather_text)
    
    # 2. Проверяем дни рождения
    birthday_text = check_birthdays()
    if birthday_text:
        for chat in CHAT_IDS:
            send_vk_message(chat, birthday_text)

    # Выход для GitHub Actions
    sys.exit(0)
