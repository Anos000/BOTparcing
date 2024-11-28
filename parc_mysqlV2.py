from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import mysql.connector
from datetime import datetime
import pytz
import re
import time
import requests
import base64

# Настройка для работы с Chrome
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Запуск браузера в фоновом режиме
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Устанавливаем драйвер для Chrome
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

# Подключение к базе данных
def ensure_connection():
    global conn, cursor
    try:
        if conn.is_connected():
            return
    except NameError:
        pass
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        print("Подключение восстановлено!")
    except mysql.connector.Error as err:
        print(f"Ошибка подключения: {err}")
        time.sleep(5)
        ensure_connection()

# Устанавливаем начальное соединение
ensure_connection()

# Создаем таблицы
with conn.cursor() as cursor:
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

# URL страницы интернет-магазина
url = "https://vapkagro.ru/catalog/avtomobilnye-zapchasti/?PAGEN_1=1&SIZEN_1=12"
driver.get(url)

# Получаем HTML-код после выполнения JavaScript
html_content = driver.page_source
soup = BeautifulSoup(html_content, 'lxml')

# Определение количества страниц
pagination = soup.find('ul', class_='bx_pagination_page_list_num')
last_page = int(pagination.find_all('a')[-1].text.strip()) if pagination else 1
print(f"Найдено страниц: {last_page}")

# Получаем текущую дату в часовом поясе UTC+3
tz = pytz.timezone("Europe/Moscow")
current_date = datetime.now(tz)

# Извлекаем данные из базы
ensure_connection()
with conn.cursor(dictionary=True) as cursor:
    cursor.execute('SELECT link, price FROM All_products')
    existing_data = {row['link']: row['price'] for row in cursor.fetchall()}



# Обработка страниц
today_data = []
for page in range(1, last_page + 1):
    print(f"Парсим страницу: {page}")
    driver.get(f"https://vapkagro.ru/catalog/avtomobilnye-zapchasti/?PAGEN_1={page}&SIZEN_1=12")
    time.sleep(2)  # Задержка для прогрузки страницы

    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'lxml')

    products = soup.find_all('div', class_='product-item-container tiles')
    if not products:
        print(f"Нет товаров на странице {page}.")
        continue

    for product in products:
        try:
            # Извлечение данных товара
            title = product.find('div', class_='name')['title'].strip()
            price = re.sub(r'\D', '', product.find('span', id=re.compile(r'bx_\w+_price')).text.strip())
            link = f"https://vapkagro.ru{product.find('div', class_='product_item_title').find('a')['href']}"
            
            driver.get(link)
            time.sleep(1)
            soup = BeautifulSoup(driver.page_source, 'lxml')

            number = next(
                (li.find('span', class_='product-item-detail-properties-value').text.strip()
                 for li in soup.select('.product-item-detail-properties-item')
                 if li.find('span', class_='product-item-detail-properties-name').text.strip() == 'Артикул'),
                'Артикул не найден'
            )

            image = soup.find('meta', itemprop='image')
            image = f"https://vapkagro.ru{image['content']}" if image else "Нет изображения"

            # Обновление базы данных
            ensure_connection()
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO All_today_products (date_parsed, title, number, price, image, link, site_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (current_date, title, number, price, image, link, 2))

                if link in existing_data and existing_data[link] != price:
                    today_data.append((current_date, title, number, price, image, link, 2))
                elif link not in existing_data:
                    today_data.append((current_date, title, number, price, image, link, 2))
        except Exception as e:
            print(f"Ошибка при обработке товара: {e}")

# Сохранение новых данных
if today_data:
    ensure_connection()
    with conn.cursor() as cursor:
        cursor.executemany('''
            INSERT INTO All_products (date_parsed, title, number, price, image, link, site_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', today_data)

conn.commit()
driver.quit()
