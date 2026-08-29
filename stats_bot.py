import os
import requests
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import vk_api
from vk_api.upload import VkUpload
from datetime import datetime

# ================= НАСТРОЙКИ БОТА =================
# Токен берется из скрытых секретов GitHub Actions
VK_TOKEN = os.getenv('VK_TOKEN')
PEER_ID = 2000000001 # ID беседы, куда кидать график (начинается с 2000000000)
STATS_URL = 'https://stat5verst.ru/parkstankozavoda/starts_all'
# ==================================================

def fetch_and_parse_data():
    """Парсит HTML таблицу и возвращает списки X, Y1, Y2"""
    print(f"[{datetime.now()}] Получаем данные с сайта: {STATS_URL}")
    response = requests.get(STATS_URL)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    if not table:
        raise ValueError("Таблица со статистикой не найдена на странице.")

    rows = table.find_all('tr')
    
    start_numbers = []
    finishers = []
    volunteers = []

    # Пропускаем заголовок таблицы (индекс 0)
    for row in rows[1:]:
        cols = row.find_all('td')
        if len(cols) >= 4:
            try:
                # Столбцы: 0: Номер, 1: Дата, 2: Финишеры, 3: Волонтеры
                s_num = int(cols[0].text.strip())
                f_count = int(cols[2].text.strip())
                v_count = int(cols[3].text.strip())
                
                start_numbers.append(s_num)
                finishers.append(f_count)
                volunteers.append(v_count)
            except ValueError:
                continue # Пропускаем строки с кривыми данными

    # Сортируем списки по возрастанию номеров стартов (для графика слева направо)
    sorted_data = sorted(zip(start_numbers, finishers, volunteers), key=lambda x: x[0])
    
    if not sorted_data:
        raise ValueError("Данные для построения графика пусты.")

    x_starts = [item[0] for item in sorted_data]
    y_finishers = [item[1] for item in sorted_data]
    y_volunteers = [item[2] for item in sorted_data]

    return x_starts, y_finishers, y_volunteers

def create_chart(x, y_fin, y_vol, filename='parkrun_stats.png'):
    """Рисует и сохраняет линейный график"""
    print(f"[{datetime.now()}] Отрисовка графика...")
    
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(x, y_fin, color='#2B326D', marker='o', linewidth=2, markersize=5, label='Финишеры')
    ax.plot(x, y_vol, color='#E6564C', marker='o', linewidth=2, markersize=5, label='Волонтёры')

    ax.set_title('Динамика посещаемости: 5 вёрст Станкозавод', fontsize=16, fontweight='bold', pad=15)
    ax.set_xlabel('Номер старта', fontsize=12, labelpad=10)
    ax.set_ylabel('Количество человек', fontsize=12, labelpad=10)
    
    ax.legend(fontsize=12, loc='upper left')
    ax.grid(True, linestyle='--', alpha=0.7)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()
    
    return filename

def send_to_vk(filename):
    """Отправляет фото в беседу ВК"""
    if not VK_TOKEN:
        raise ValueError("Токен ВК не найден в переменных окружения!")

    print(f"[{datetime.now()}] Отправка в ВК (Peer ID: {PEER_ID})...")
    
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    upload = VkUpload(vk_session)

    photo = upload.photo_messages(filename)[0]
    attachment = f"photo{photo['owner_id']}_{photo['id']}"

    message_text = "📊 Еженедельная статистика парковых пробежек обновлена! Посмотрите динамику финишеров и волонтеров."

    vk.messages.send(
        peer_id=PEER_ID,
        random_id=vk_api.utils.get_random_id(),
        message=message_text,
        attachment=attachment
    )
    print(f"[{datetime.now()}] Успешно отправлено!")

def main():
    image_path = 'parkrun_stats.png'
    try:
        x, y_fin, y_vol = fetch_and_parse_data()
        create_chart(x, y_fin, y_vol, image_path)
        send_to_vk(image_path)
    except Exception as e:
        print(f"[{datetime.now()}] ПРОИЗОШЛА ОШИБКА: {e}")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

if __name__ == '__main__':
    main()
