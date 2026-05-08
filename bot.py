import os
import requests
import random
import sys
import time
from datetime import datetime, timedelta, timezone

# --- НАСТРОЙКИ ---
VK_TOKEN = os.getenv('VK_TOKEN')
CHAT_IDS_RAW = os.getenv('VK_CHAT_IDS', '')

# Берем из секретов, а если там пусто или ничего нет — берем ID Станкозавода
VK_GROUP_ID = os.getenv('VK_GROUP_ID')
if not VK_GROUP_ID:
    VK_GROUP_ID = '228375526'

print(f"DEBUG: Начало работы. Целевая группа: {VK_GROUP_ID}")

try:
    CHAT_IDS = [int(i.strip()) for i in CHAT_IDS_RAW.split(',') if i.strip()]
    print(f"DEBUG: Распознано чатов для рассылки: {len(CHAT_IDS)}")
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
        # Берем прогноз на 9 утра
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
    try:
        now = get_moscow_now()
        today = now.strftime("%d.%m")
        current_month = ".05" # Ищем всех майских для теста
        print(f"DEBUG: Ищем именинников на дату: {today}")
        
        celebrants = []
        may_birthdays = [] # Список всех именинников мая для логов
        offset = 0
        count = 1000
        total_with_bdate = 0
        
        while True:
            params = {
                "group_id": VK_GROUP_ID,
                "fields": "bdate",
                "offset": offset,
                "count": count,
                "access_token": VK_TOKEN,
                "v": "5.131"
            }
            res = requests.get("https://api.vk.com/method/groups.getMembers", params=params, timeout=15).json()
            
            if "error" in res:
                print(f"Ошибка API ВК: {res['error']['error_msg']}")
                break
                
            items = res.get('response', {}).get('items', [])
            if not items:
                break
                
            for m in items:
                bd = m.get('bdate', '')
                if bd:
                    total_with_bdate += 1
                    parts = bd.split('.')
                    if len(parts) >= 2:
                        try:
                            # Приводим к формату ДД.ММ
                            day = int(parts[0])
                            month = int(parts[1])
                            formatted_bd = f"{day:02d}.{month:02d}"
                            
                            # Логируем всех, у кого ДР в мае (для диагностики)
                            if f".{month:02d}" == current_month:
                                name = f"{m.get('first_name', '')} {m.get('last_name', '')}"
                                may_birthdays.append(f"{name} ({formatted_bd})")
                            
                            # Проверяем, совпадает ли с сегодня
                            if formatted_bd == today:
                                celebrants.append(f"[id{m['id']}|{m.get('first_name', '')} {m.get('last_name', '')}]")
                        except:
                            continue
            
            offset += len(items)
            if len(items) < count:
                break
            time.sleep(0.2)
        
        print(f"DEBUG: Всего в группе: {offset}, с датами: {total_with_bdate}")
        print(f"DEBUG: Именинники мая в группе: {', '.join(may_birthdays) if may_birthdays else 'Никого не нашли'}")
        
        if celebrants:
            return f"🥳 С ДНЁМ РОЖДЕНИЯ! 🎂\n\nСегодня праздник у: {', '.join(celebrants)}! 🎉🧡\nЖелаем лёгких ног, ярких стартов и отличного настроения!"
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
            print(f"Ошибка отправки (ID {peer_id}): {res['error']['error_msg']}")
        else:
            print(f"Успешно отправлено в чат {peer_id}")
    except Exception as e:
        print(f"Ошибка сети при отправке: {e}")

if __name__ == "__main__":
    if not VK_TOKEN:
        print("Ошибка: VK_TOKEN не найден!")
        sys.exit(1)
    if not CHAT_IDS:
        print("Ошибка: Список чатов пуст!")
        sys.exit(1)

    now_msk = get_moscow_now()
    
    # 1. Проверяем погоду (ТОЛЬКО ПО СУББОТАМ)
    # weekday() == 5 — это суббота
    if now_msk.weekday() == 5:
        print("Сегодня суббота, получаем прогноз погоды...")
        weather_text = get_weather()
        if weather_text:
            for chat in CHAT_IDS:
                send_vk_message(chat, weather_text)
    else:
        print(f"Сегодня не суббота (день №{now_msk.weekday()}), погоду пропускаем.")

    # 2. Проверяем дни рождения (КАЖДЫЙ ДЕНЬ)
    print("Проверяем дни рождения...")
    birthday_text = check_birthdays()
    if birthday_text:
        for chat in CHAT_IDS:
            send_vk_message(chat, birthday_text)
    else:
        print("Именинников сегодня не найдено.")

    sys.exit(0)
