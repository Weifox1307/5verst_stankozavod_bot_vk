import os, requests, datetime
import pandas as pd
from datetime import timedelta

# Данные для Станкозавода
NRMS_USER = os.getenv("NRMS_USERNAME")
NRMS_PASS = os.getenv("NRMS_PASSWORD")
SHEET_URL = os.getenv("SHEET_CSV_URL")
EVENT_ID = 10061

def get_target_date():
    """Считает дату ближайшей субботы"""
    now = datetime.datetime.now()
    days_ahead = (5 - now.weekday() + 7) % 7
    if days_ahead == 0 and now.hour >= 11:
        days_ahead = 7
    target = now + timedelta(days=days_ahead)
    return target.strftime("%d.%m.%Y")

def get_token():
    """Авторизация на сайте 5 вёрст"""
    r = requests.post("https://nrms.5verst.ru/api/v1/auth/login", 
                      json={"username": NRMS_USER, "password": NRMS_PASS})
    return r.json()['result']['token']

def run_sync():
    target_date = get_target_date()
    print(f"--- СИНХРОНИЗАЦИЯ СТАНКОЗАВОД ---")
    print(f"Целевая суббота старта: {target_date}")
    
    try:
        token = get_token()
    except Exception as e:
        print(f"Ошибка логина на NRMS: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Читаем таблицу
    try:
        # Загружаем CSV и чистим названия колонок
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip()
        
        # Фильтруем: только статус 'new'
        new_data = df[df.iloc[:, 4] == 'new'].copy()
        
        if new_data.empty:
            return print("Новых записей со статусом 'new' не найдено.")

        # 2. ФИЛЬТР ПО ДАТЕ (Защита от старых записей)
        # Бот берет только те записи, которые созданы не более 6 дней назад
        now = datetime.datetime.now()
        
        def is_fresh(timestamp_str):
            try:
                # В колонке index 5 (F) лежит дата создания записи
                row_time = pd.to_datetime(timestamp_str)
                # Если разница между сейчас и временем записи меньше 6 дней
                return (now - row_time).days < 6
            except:
                return False

        new_data = new_data[new_data.iloc[:, 5].apply(is_fresh)]

        if new_data.empty:
            return print("В таблице есть статус 'new', но записи старые. Пропускаем.")

    except Exception as e:
        print(f"Ошибка при обработке таблицы: {e}")
        return

    # 3. Получаем текущий список с сайта, чтобы не плодить дубликаты
    r_curr = requests.post("https://nrms.5verst.ru/api/v1/event/volunteer/list", 
                          json={"event_id": EVENT_ID, "event_date": target_date}, headers=headers)
    
    volunteers = []
    if r_curr.status_code == 200:
        existing = r_curr.json().get('result', {}).get('volunteer_list', [])
        volunteers = [{"verst_id": v['verst_id'], "role_id": v['role_id']} for v in existing]

    # 4. Добавляем новых участников
    added_count = 0
    for _, row in new_data.iterrows():
        vid = int(row.iloc[0]) # verst_id
        rid = int(row.iloc[1]) # role_id
        # Проверяем, нет ли уже такого сочетания ID и Роли на сайте
        if not any(v['verst_id'] == vid and v['role_id'] == rid for v in volunteers):
            volunteers.append({"verst_id": vid, "role_id": rid})
            added_count += 1

    if added_count == 0:
        return print("Все новые волонтеры из таблицы уже были добавлены на сайт ранее.")

    # 5. Сохраняем финальный список на NRMS
    payload = {
        "event_id": EVENT_ID,
        "date": target_date,
        "upload_status_id": 1,
        "volunteers": volunteers
    }
    
    res = requests.post("https://nrms.5verst.ru/api/v1/volunteer/event/save", json=payload, headers=headers)
    
    if res.status_code == 200:
        print(f"УСПЕХ: Добавлено {added_count} записей на Станкозавод.")
    else:
        print(f"ОШИБКА NRMS: {res.text}")

if __name__ == "__main__":
    run_sync()
