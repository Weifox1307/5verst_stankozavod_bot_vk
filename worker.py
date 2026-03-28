import os, requests, datetime
import pandas as pd
from datetime import timedelta

# Данные для Станкозавода
NRMS_USER = os.getenv("NRMS_USERNAME")
NRMS_PASS = os.getenv("NRMS_PASSWORD")
SHEET_URL = os.getenv("SHEET_CSV_URL")
EVENT_ID = 10061 # Для Кстово поменяй на 10079

def get_target_date():
    """Считает дату ближайшей БУДУЩЕЙ субботы"""
    now = datetime.datetime.now()
    # 5 - это суббота. Считаем сколько дней до нее
    days_ahead = (5 - now.weekday() + 7) % 7
    # Если сегодня суббота и время > 11:00, целевая дата — СЛЕДУЮЩАЯ неделя
    if days_ahead == 0 and now.hour >= 11:
        days_ahead = 7
    target = now + timedelta(days=days_ahead)
    return target.strftime("%d.%m.%Y")

def get_sync_boundary():
    """Находит время окончания последнего старта (суббота 11:00)"""
    now = datetime.datetime.now()
    # Сколько дней назад была суббота (5)
    days_since_sat = (now.weekday() - 5) % 7
    last_sat = now - timedelta(days=days_since_sat)
    boundary = last_sat.replace(hour=11, minute=0, second=0, microsecond=0)
    
    # Если сейчас утро субботы (до 11:00), то граница — ПРОШЛАЯ суббота
    if now.weekday() == 5 and now.hour < 11:
        boundary -= timedelta(days=7)
        
    return boundary

def get_token():
    """Авторизация на сайте 5 вёрст"""
    r = requests.post("https://nrms.5verst.ru/api/v1/auth/login", 
                      json={"username": NRMS_USER, "password": NRMS_PASS})
    return r.json()['result']['token']

def run_sync():
    target_date = get_target_date()
    boundary_time = get_sync_boundary()
    
    print(f"--- СИНХРОНИЗАЦИЯ СТАНКОЗАВОД ---")
    print(f"Целевая суббота: {target_date}")
    print(f"Игнорируем всё, что записано до: {boundary_time.strftime('%d.%m %H:%M')}")
    
    try:
        token = get_token()
    except Exception as e:
        print(f"Ошибка логина: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Читаем таблицу
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip()
        
        # Фильтр 1: Только статус 'new'
        new_data = df[df.iloc[:, 4] == 'new'].copy()
        
        if new_data.empty:
            return print("Новых записей не найдено.")

        # Фильтр 2: УМНАЯ ГРАНИЦА ВРЕМЕНИ
        # Оставляем только те записи, которые сделаны ПОСЛЕ 11:00 последней субботы
        new_data.iloc[:, 5] = pd.to_datetime(new_data.iloc[:, 5])
        new_data = new_data[new_data.iloc[:, 5] > boundary_time]

    except Exception as e:
        print(f"Ошибка при обработке таблицы: {e}")
        return
    
    if new_data.empty: 
        return print("Все новые записи в таблице относятся к прошлому старту. Пропускаем.")

    # 2. Получаем текущий список с сайта
    r_curr = requests.post("https://nrms.5verst.ru/api/v1/event/volunteer/list", 
                          json={"event_id": EVENT_ID, "event_date": target_date}, headers=headers)
    
    volunteers = []
    if r_curr.status_code == 200:
        existing = r_curr.json().get('result', {}).get('volunteer_list', [])
        volunteers = [{"verst_id": v['verst_id'], "role_id": v['role_id']} for v in existing]

    # 3. Добавляем новых участников
    added_count = 0
    for _, row in new_data.iterrows():
        vid = int(row.iloc[0]) # verst_id
        rid = int(row.iloc[1]) # role_id
        if not any(v['verst_id'] == vid and v['role_id'] == rid for v in volunteers):
            volunteers.append({"verst_id": vid, "role_id": rid})
            added_count += 1

    if added_count == 0:
        return print("Все свежие волонтеры уже на сайте.")

    # 4. Сохраняем на сайт
    payload = {
        "event_id": EVENT_ID,
        "date": target_date,
        "upload_status_id": 1,
        "volunteers": volunteers
    }
    
    res = requests.post("https://nrms.5verst.ru/api/v1/volunteer/event/save", json=payload, headers=headers)
    
    if res.status_code == 200:
        print(f"УСПЕХ: Добавлено {added_count} новых волонтеров на 04.04.2026")
    else:
        print(f"ОШИБКА NRMS: {res.text}")

if __name__ == "__main__":
    run_sync()
