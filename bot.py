import os
import requests
import random
import sys

# --- НАСТРОЙКИ (берем из Secrets) ---
VK_TOKEN = os.getenv('VK_TOKEN')
CHAT_IDS_RAW = os.getenv('VK_CHAT_IDS', '')

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

def send_vk_message(peer_id, text):
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
        print("Ошибка: Список чатов пуст! Проверьте секрет VK_CHAT_IDS в настройках GitHub.")
        sys.exit(1)

    weather_text = get_weather()
    if weather_text:
        for chat in CHAT_IDS:
            send_vk_message(chat, weather_text)
    else:
        print("Не удалось получить прогноз.")
