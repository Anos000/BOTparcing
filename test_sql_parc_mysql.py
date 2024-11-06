from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import pytz
import re

# Настройка для работы с Chrome
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# URL страницы интернет-магазина
url = "https://avtobat36.ru/catalog/avtomobili_gruzovye/"
driver.get(url)
html_content = driver.page_source
soup = BeautifulSoup(html_content, 'lxml')

# Находим номер последней страницы
pages = soup.find('div', class_='bx_pagination_page').find_all('li')
last_page = int(pages[-2].text.strip())

# Подключение к базе данных MySQL
db_config = {
    'host': 'krutskuy.beget.tech',  # Замените на ваше имя хоста
    'user': 'krutskuy_parc',       # Ваше имя пользователя
    'password': 'AnosVoldigod0',    # Ваш пароль
    'database': 'krutskuy_parc',    # Имя вашей базы данных
}

# Подключение к базе данных
try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    print("Подключение успешно!")
except mysql.connector.Error as err:
    print(f"Ошибка подключения: {err}")


# Создаем таблицу, если ее нет
cursor.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date_parsed DATETIME,
    title VARCHAR(255),
    number VARCHAR(255),
    price VARCHAR(255),
    image VARCHAR(255),
    link VARCHAR(255)
)
''')

# Создаем таблицу для актуальных данных, если она не существует
cursor.execute('''
CREATE TABLE IF NOT EXISTS today_products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date_parsed DATETIME,
    title VARCHAR(255),
    number VARCHAR(255),
    price VARCHAR(255),
    image VARCHAR(255),
    link VARCHAR(255)
)
''')

# Получаем текущую дату в часовом поясе UTC+3
tz = pytz.timezone("Europe/Moscow")
current_date = datetime.now(tz)

# Получаем ссылки и цены для всех товаров из базы данных
cursor.execute('SELECT link, price FROM products')
existing_products = cursor.fetchall()
existing_links = {item[0]: item[1] for item in existing_products}  # link -> price

# Переменная для хранения данных сегодняшнего дня
today_data = []

def ensure_connection():
    if not conn.is_connected():
        conn.reconnect()

# В основном цикле перед выполнением запросов к базе данных
for page in range(1, last_page + 1):
    ensure_connection()
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

            # Проверка на наличие изображения
            image_element = product.find('img')
            image = f"https://avtobat36.ru{image_element['src']}" if image_element and 'src' in image_element.attrs else "Нет изображения"

            # Добавляем данные для последующей обработки
            today_data.append((current_date, title, number, price, image, link_full))

        except Exception as e:
            print(f"Ошибка при обработке товара: {e}")

# Проверка на новые товары или изменение цены
new_entries = []

for current_date, title, number, price, image, link in today_data:
    # Проверка на наличие ссылки среди записей в базе данных
    if link in existing_links:
        # Если ссылка уже есть, проверяем изменение цены
        last_price = existing_links[link]
        if price != last_price:  # Цена изменилась
            new_entries.append((current_date, title, number, price, image, link))
    else:
        # Новый товар, если ссылка не найдена в базе
        new_entries.append((current_date, title, number, price, image, link))

# Добавление новых товаров и товаров с измененной ценой в базу данных
if new_entries:
    print("Найдены новые товары или изменения в цене, добавляем в базу данных.")
    cursor.executemany('''
        INSERT INTO products (date_parsed, title, number, price, image, link)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', new_entries)
else:
    print("Изменений нет, данные не будут добавлены.")

# Удаляем все записи из таблицы актуальных данных, чтобы сохранить только данные текущего дня
cursor.execute('DELETE FROM today_products')
# Обновляем таблицу актуальных данных новыми данными текущего дня
cursor.executemany('''
    INSERT INTO today_products (date_parsed, title, number, price, image, link)
    VALUES (%s, %s, %s, %s, %s, %s)
''', today_data)



# Сохранение и закрытие соединения
conn.commit()
cursor.close()
conn.close()
driver.quit()
