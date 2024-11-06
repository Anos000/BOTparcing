from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import mysql.connector
from datetime import datetime
import pytz
import re
import time

# Настройка для работы с Chrome
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Запуск браузера в фоновом режиме
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Устанавливаем драйвер для Chrome
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# URL страницы интернет-магазина
url = "https://vapkagro.ru/catalog/avtomobilnye-zapchasti/?PAGEN_1=1&SIZEN_1=12"
driver.get(url)

# Получаем HTML-код после выполнения JavaScript
html_content = driver.page_source
soup = BeautifulSoup(html_content, 'lxml')

# Извлекаем список всех ссылок на страницы
pagination = soup.find('ul', class_='bx_pagination_page_list_num')
if pagination:
    last_page = int(pagination.find_all('a')[-1].text.strip())
else:
    last_page = 1  # Если нет пагинации, предполагаем, что только одна страница

print(f"Найдено страниц: {last_page}")

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

# Создаем таблицу, если она не существует
cursor.execute('''
CREATE TABLE IF NOT EXISTS productsV2 (
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
CREATE TABLE IF NOT EXISTS today_productsV2 (
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

# Извлекаем ссылки и последние цены товаров из базы данных
cursor.execute('SELECT link, price FROM productsV2')
existing_data = {row[0]: row[1] for row in cursor.fetchall()}  # link -> price

# Переменная для хранения данных сегодняшнего дня
today_data = []

# Удаляем все записи из таблицы актуальных данных, чтобы сохранить только данные текущего дня
cursor.execute('DELETE FROM today_productsV2')

# Цикл по всем страницам
for page in range(1, last_page + 1):
    print(f"Парсим страницу: {page}")
    driver.get(f"https://vapkagro.ru/catalog/avtomobilnye-zapchasti/?PAGEN_1={page}&SIZEN_1=12")
    time.sleep(2)  # Задержка для прогрузки страницы

    # Получаем HTML-код после выполнения JavaScript
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'lxml')

    # Находим все товары на странице
    products = soup.find_all('div', class_='product-item-container tiles')

    if not products:
        print(f"Нет товаров на странице {page}, пропускаем страницу.")
        continue

    # Проходим по каждому товару и извлекаем данные
    for product in products:
        try:
            # Извлекаем название товара
            title = product.find('div', class_='name')['title'].strip()

            # Извлекаем цену товара
            try:
                price = product.find('span', id=re.compile(r'bx_\w+_price')).text.strip()
                price = re.sub(r'\D', '', price)
            except:
                price = 'Необходимо уточнять'

            # Извлекаем ссылку на товар
            link = product.find('div', class_='product_item_title').find('a')['href']
            full_link = f"https://vapkagro.ru{link}"
            driver.get(full_link)  # Переходим на страницу с товаром для извлечения артикулов

            time.sleep(1)  # Ожидание для загрузки страницы

            # Инициализируем BeautifulSoup для страницы с артикулом
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'lxml')

            # Находим артикул
            details = soup.find('div', class_='product-item-detail-tabs').find_all('li', class_='product-item-detail-properties-item')
            number = 'Артикул не найден'
            for detail in details:
                if detail.find('span', class_='product-item-detail-properties-name').text.strip() == 'Артикул':
                    number = detail.find('span', class_='product-item-detail-properties-value').text.strip()
                    break

            # Извлекаем изображение
            image_element = soup.find('meta', itemprop='image')
            if image_element and 'content' in image_element.attrs:
                # Образуем ссылку на изображение, добавляя URL магазина
                image = f"https://vapkagro.ru{image_element['content']}"
            else:
                image = "Нет изображения"

            print(title, number, price, image)

            # Добавляем товар в `today_productsV2`
            cursor.execute('''
                INSERT INTO today_productsV2 (date_parsed, title, number, price, image, link)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (current_date, title, number, price, image, full_link))

            # Проверка: если ссылка уже есть в базе данных
            if full_link in existing_data:
                # Если цена отличается от сохраненной, добавляем запись с новой ценой
                if price != existing_data[full_link]:
                    today_data.append((current_date, title, number, price, image, full_link))
                    print(f"Новая цена для {title}: добавляем в базу данных.")
            else:
                # Если товара по ссылке нет в базе, добавляем его как новый
                today_data.append((current_date, title, number, price, image, full_link))

        except Exception as e:
            print(f"Ошибка при обработке товара: {e}")

# Добавляем данные о товарах с новыми ценами и новыми товарами в `productsV2`
if today_data:
    cursor.executemany('''
        INSERT INTO productsV2 (date_parsed, title, number, price, image, link)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', today_data)
def ensure_connection():
    if not conn.is_connected():
        conn.reconnect()


# Сохранение изменений и закрытие соединения
conn.commit()
cursor.close()
conn.close()
driver.quit()
