from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from datetime import datetime
import pytz
import re
import requests
import base64
import time

# Настройка для работы с Chrome
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Загрузка файла settings.txt с GitHub
github_url = "https://api.github.com/repos/Anos000/BOTparcing/contents/settings.txt"
response = requests.get(github_url)

if response.status_code == 200:
    file_content = response.json()
    decoded_content = base64.b64decode(file_content['content']).decode('utf-8').splitlines()
    db_config = {
        'host': decoded_content[0].strip(),
        'user': decoded_content[1].strip(),
        'password': decoded_content[2].strip(),
        'database': decoded_content[3].strip()
    }
    print(f"Содержимое settings.txt успешно загружено: {db_config}")
else:
    print(f"Ошибка загрузки settings.txt: {response.status_code}")
    exit(1)

# Создаем пул соединений
pool = MySQLConnectionPool(pool_name="mypool", pool_size=20, **db_config)

# Функция для получения соединения из пула
def get_connection():
    try:
        return pool.get_connection()
    except mysql.connector.Error as err:
        print(f"Ошибка получения соединения из пула: {err}")
        raise

# Создаем таблицы, если их нет
try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS All_products (
        id INT,
        date_parsed DATETIME,
        title VARCHAR(255),
        number VARCHAR(255),
        price VARCHAR(255),
        image VARCHAR(255),
        link VARCHAR(255),
        site_id INT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS All_today_products (
        id INT,
        date_parsed DATETIME,
        title VARCHAR(255),
        number VARCHAR(255),
        price VARCHAR(255),
        image VARCHAR(255),
        link VARCHAR(255),
        site_id INT
    )
    ''')
    conn.commit()
    cursor.close()
    conn.close()
except mysql.connector.Error as err:
    print(f"Ошибка настройки базы данных: {err}")
    exit(1)

# URL страницы интернет-магазина
url = "https://avtobat36.ru/catalog/avtomobili_gruzovye/"
driver.get(url)
html_content = driver.page_source
soup = BeautifulSoup(html_content, 'lxml')

# Находим номер последней страницы
pages = soup.find('div', class_='bx_pagination_page').find_all('li')
last_page = int(pages[-2].text.strip())

# Получаем текущую дату в часовом поясе UTC+3
tz = pytz.timezone("Europe/Moscow")
current_date = datetime.now(tz)

# Получаем ссылки и цены для всех товаров из базы данных
try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT link, price FROM All_products')
    existing_products = cursor.fetchall()
    existing_links = {item[0]: item[1] for item in existing_products}  # link -> price
    cursor.close()
    conn.close()
except mysql.connector.Error as err:
    print(f"Ошибка загрузки данных из базы: {err}")
    exit(1)

# Переменная для хранения данных сегодняшнего дня
today_data = []

# Основной цикл по страницам
for page in range(1, last_page + 1):
    page_url = f"https://avtobat36.ru/catalog/avtomobili_gruzovye/?PAGEN_2={page}"
    driver.get(page_url)
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'lxml')

    products = soup.find_all('div', class_=re.compile(r'catalog-section-item sec_item itm_'))
    print(f"Страница {page}: найдено товаров {len(products)}")

    for product in products:
        try:
            title_element = product.find('a', class_='d-lnk-txt')
            title = title_element.text.strip() if title_element else "Нет названия"

            price_element = product.find('span', class_='js-price')
            price = price_element.text.strip() if price_element else 'Необходимо уточнять'
            price = re.sub(r'\D', '', price)

            number_element = product.find('div', class_='sec_params d-note')
            if number_element:
                details = number_element.text.strip()
                number = details[details.find(':') + 1:details.find('П') - 1].strip()
            else:
                number = 'Артикул отсутствует'

            link_element = product.find('a', class_='d-lnk-txt')
            link = link_element['href'] if link_element else "Нет ссылки"
            link_full = f"https://avtobat36.ru{link}"

            image_element = product.find('img')
            image = f"https://avtobat36.ru{image_element['src']}" if image_element and 'src' in image_element.attrs else "Нет изображения"

            today_data.append((current_date, title, number, price, image, link_full, 1))
        except Exception as e:
            print(f"Ошибка при обработке товара: {e}")

# Проверка новых товаров и обновление данных
new_entries = []

for current_date, title, number, price, image, link, site_id in today_data:
    if link in existing_links:
        last_price = existing_links[link]
        if price != last_price:
            new_entries.append((current_date, title, number, price, image, link, site_id))
    else:
        new_entries.append((current_date, title, number, price, image, link, site_id))

if new_entries:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        print("Найдены новые товары или изменения в цене, добавляем в базу данных.")
        cursor.executemany('''
            INSERT INTO All_products (date_parsed, title, number, price, image, link, site_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', new_entries)
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Ошибка добавления данных в базу: {err}")

# Обновляем таблицу актуальных данных
try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SET SESSION innodb_lock_wait_timeout = 300')  # Увеличиваем таймаут ожидания
    batch_size = 100  # Уменьшение размера пакета
    while True:
        cursor.execute('DELETE FROM All_today_products WHERE date_parsed < CURDATE() LIMIT %s', (batch_size,))
        rows_deleted = cursor.rowcount
        conn.commit()  # Подтверждаем удаление
        print(f"Удалено {rows_deleted} строк из All_today_products")
        if rows_deleted == 0:
            break

    # Добавляем новые записи в All_today_products
    if today_data:
        cursor.executemany('''
            INSERT INTO All_today_products (date_parsed, title, number, price, image, link, site_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', today_data)
        conn.commit()
        print(f"Добавлено {len(today_data)} новых записей в All_today_products")

    cursor.close()
    conn.close()
except mysql.connector.Error as err:
    print(f"Ошибка обновления таблицы актуальных данных: {err}")

# Завершение работы
driver.quit()
