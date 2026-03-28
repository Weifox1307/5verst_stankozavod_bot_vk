import os, requests, datetime
import pandas as pd
from datetime import timedelta, timezone

# --- НАСТРОЙКИ ---
NRMS_USER = os.getenv("NRMS_USERNAME")
NRMS_PASS = os.getenv("NRMS_PASSWORD")
SHEET_URL = os.getenv("SHEET_CSV_URL")
EVENT_ID = 10061  # Для Кстово замени на 10079

def get_moscow_now():
    """Возвращает текущее время в Москве (UTC+3)"""
    return datetime.datetime.now(timezone(timedelta(hours=3)))

def get_target_date():
    """Считает дату ближайшей БУДУЩЕЙ субботы по МСК"""
    now = get_moscow_now()
    # 5 - это суббота
    days_ahead = (5 - now.weekday() + 7) % 7
    
    # Если сегодня суббота и время по Москве >= 11:00, целевая дата — СЛЕДУЮЩАЯ неделя
    if days_ahead == 0 and now.hour >= 11:
        days_ahead = 7
        
    target = now + timedelta(days=days_ahead)
    return target.strftime("%d.%m.%Y")

def get_sync_boundary():
    """Находит время окончания последнего старта (суббота 11:00 по МСК)"""
    now = get_moscow_now()
    # Сколько дней назад была суббота
    days_since_sat = (now.weekday() - 5) % 7
    last_sat = now - timedelta(days=days_since_sat)
    
    # Устанавливаем границу на 11:00 утра по Москве
    boundary = last_sat.replace(hour=11, minute=0, second=0, microsecond=0)
    
    # Если сейчас утро субботы (до 11:00), то граница — это ПРОШЛАЯ суббота 11:00
    if now.weekday() == 5 and now.hour < 11:
        boundary -= timedelta(days=7)
        
    return boundary

def get_token():
    """Авторизация на сайте 5 вёрст"""
    r = requests.post("https://nrms.5verst.ru/api/v1/auth/login", 
                      json={"username": NRMS_USER, "password": NRMS_PASS})
    return r.json()['result']['token']

def run_sync():
    now_msk = get_moscow_now()
    target_date = get_target_date()
    boundary_time = get_sync_boundary()
    
    print(f"--- СИНХРОНИЗАЦИЯ (EVENT {EVENT_ID}) ---")
    print(f"Текущее время МСК: {now_msk.strftime('%d.%m %H:%M')}")
    print(f"Целевая суббота: {target_date}")
    print(f"Точка отсечения старых записей: {boundary_time.strftime('%d.%m %H:%M')}")
    
    try:
        token = get_token()
    except Exception as e:
        print(f"Ошибка логина на NRMS: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Читаем таблицу
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip()
        
        # Фильтр 1: Только статус 'new'
        new_data = df[df.iloc[:, 4] == 'new'].copy()
        
        if new_data.empty:
            return print("Новых записей в таблице не найдено.")

        # --- ИСПРАВЛЕННЫЙ БЛОК ВРЕМЕНИ ---
        msk_tz = timezone(timedelta(hours=3))
        # Считаем, что время в CSV — это время по Москве (UTC+3)
        new_data.iloc[:, 5] = pd.to_datetime(new_data.iloc[:, 5]).dt.tz_localize(msk_tz, ambiguous='infer')
        
        # Оставляем только те записи, которые сделаны ПОСЛЕ 11:00 последней субботы МСК
        new_data = new_data[new_data.iloc[:, 5] > boundary_time]
        # ---------------------------------

    except Exception as e:
        print(f"Ошибка при обработке таблицы: {e}")
        return
    
    if new_data.empty: 
        return print("Все новые записи относятся к уже прошедшему старту. Игнорируем.")

    # 2. Получаем текущий список с сайта, чтобы не плодить дубли
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
        return print("Все свежие волонтеры уже есть на сайте.")

    # 4. Сохраняем на сайт
    payload = {
        "event_id": EVENT_ID,
        "date": target_date,
        "upload_status_id": 1,
        "volunteers": volunteers
    }
    
    res = requests.post("https://nrms.5verst.ru/api/v1/volunteer/event/save", json=payload, headers=headers)
    
    if res.status_code == 200:
        print(f"УСПЕХ: Синхронизировано человек: {added_count}")
    else:
        print(f"ОШИБКА NRMS: {res.text}")

if __name__ == "__main__":
    run_sync()
