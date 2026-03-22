import os, requests, datetime
import pandas as pd
from datetime import timedelta

NRMS_USER = os.getenv("NRMS_USERNAME")
NRMS_PASS = os.getenv("NRMS_PASSWORD")
SHEET_URL = os.getenv("SHEET_CSV_URL")
EVENT_ID = 10061

def get_target_date():
    now = datetime.datetime.now()
    # Ищем ближайшую субботу (weekday 5)
    days_ahead = (5 - now.weekday() + 7) % 7
    # Если сегодня суббота и время > 11:00, планируем на следующую неделю
    if days_ahead == 0 and now.hour >= 11:
        days_ahead = 7
    target = now + timedelta(days=days_ahead)
    return target.strftime("%d.%m.%Y")

def get_token():
    r = requests.post("https://nrms.5verst.ru/api/v1/auth/login", 
                      json={"username": NRMS_USER, "password": NRMS_PASS})
    return r.json()['result']['token']

def run_sync():
    target_date = get_target_date()
    print(f"Целевая дата: {target_date}")
    
    try:
        token = get_token()
    except Exception as e:
        print(f"Ошибка логина: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Читаем таблицу (CSV экспорт по ссылке)
    try:
        df = pd.read_csv(SHEET_URL)
        # Очистим названия колонок от лишних пробелов
        df.columns = df.columns.str.strip()
        # В твоем doPost: 0:verst_id, 1:role_id, 2:role_name, 3:full_name, 4:status
        # Если в CSV нет заголовков, pandas назовет их 0,1,2,3,4
        # Предположим, колонки называются как в Google Таблице
        new_data = df[df.iloc[:, 4] == 'new']
    except Exception as e:
        print(f"Ошибка чтения таблицы: {e}")
        return
    
    if new_data.empty: 
        return print("Нет новых записей для синхронизации")

    # 2. Получаем текущий список с сайта
    r_curr = requests.post("https://nrms.5verst.ru/api/v1/event/volunteer/list", 
                          json={"event_id": EVENT_ID, "event_date": target_date}, headers=headers)
    
    volunteers = []
    if r_curr.status_code == 200:
        existing = r_curr.json().get('result', {}).get('volunteer_list', [])
        volunteers = [{"verst_id": v['verst_id'], "role_id": v['role_id']} for v in existing]

    # 3. Добавляем новых участников из таблицы
    added_count = 0
    for _, row in new_data.iterrows():
        vid = int(row.iloc[0]) # verst_id
        rid = int(row.iloc[1]) # role_id
        # Проверяем, нет ли уже такого человека на этой роли
        if not any(v['verst_id'] == vid and v['role_id'] == rid for v in volunteers):
            volunteers.append({"verst_id": vid, "role_id": rid})
            added_count += 1

    if added_count == 0:
        return print("Все участники уже были в NRMS")

    # 4. Сохраняем финальный список в NRMS
    payload = {
        "event_id": EVENT_ID,
        "date": target_date,
        "upload_status_id": 1,
        "volunteers": volunteers
    }
    
    res = requests.post("https://nrms.5verst.ru/api/v1/volunteer/event/save", json=payload, headers=headers)
    
    if res.status_code == 200:
        print(f"Успешно синхронизировано! Добавлено: {added_count}")
    else:
        print(f"Ошибка NRMS: {res.text}")

if __name__ == "__main__":
    run_sync()
