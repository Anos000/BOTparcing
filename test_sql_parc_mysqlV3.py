from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import mysql.connector
from datetime import datetime
import pytz
import re
# Настройка для работы с Chrome
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Запуск браузера в фоновом режиме
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Устанавливаем драйвер для Chrome с использованием webdriver_manager
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Основной URL страницы
base_url = "https://www.autoopt.ru/catalog/otechestvennye_gruzoviki?pageSize=100&PAGEN_1="

# Подключение к базе данных MySQL
db_config = {
    'host': 'krutskuy.beget.tech',  # Замените на ваше имя хоста
    'user': 'krutskuy_parc',         # Ваше имя пользователя
    'password': 'AnosVoldigod0',     # Ваш пароль
    'database': 'krutskuy_parc',     # Имя вашей базы данных
}

# Подключение к базе данных
try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    print("Подключение успешно!")
except mysql.connector.Error as err:
    print(f"Ошибка подключения: {err}")

# Создаем таблицу для всех продуктов, если она не существует
cursor.execute(''' 
CREATE TABLE IF NOT EXISTS productsV3 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date_parsed DATETIME,
    title VARCHAR(255),
    number VARCHAR(255),
    price VARCHAR(255),
    image VARCHAR(255),
    link VARCHAR(255)
)
''')

# Создаем таблицу для актуальных данных на текущий день, если она не существует
cursor.execute('''
CREATE TABLE IF NOT EXISTS today_productsV3 (
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

# Извлечение всех ссылок и последних цен из базы данных
cursor.execute(''' 
    SELECT link, price FROM productsV3
''')
existing_data = cursor.fetchall()

# Преобразуем данные в словарь для быстрой проверки (link -> price)
existing_data_dict = {item[0]: item[1] for item in existing_data}

# Очищаем таблицу актуальных данных перед добавлением новых
cursor.execute('DELETE FROM today_productsV3')

# Функция для извлечения общего количества товаров
def get_total_products():
    driver.get(base_url + "1")
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'lxml')

    total_products_element = soup.find('div', class_='row mt-4 mb-4')
    if total_products_element:
        span_element = total_products_element.find('span', class_='bold')
        if span_element:
            total_products = int(span_element.text.strip())
            print(f"Всего товаров: {total_products}")
            return total_products
        else:
            print("Не удалось найти элемент 'span' с классом 'bold'.")
            return 0
    else:
        print("Не удалось найти элемент 'div' с классом 'row mt-4 mb-4'.")
        return 0

total_products = get_total_products()

# Рассчитываем количество страниц
products_per_page = 100
total_pages = (total_products // products_per_page) + (1 if total_products % products_per_page > 0 else 0)
print(f"Страниц для парсинга: {total_pages}")

# Функция для парсинга одной страницы
def parse_page(page_number):
    url = f"{base_url}{page_number}"
    print(f"Парсим страницу {page_number}: {url}")

    try:
        # Открываем страницу
        driver.get(url)
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'lxml')

        # Находим все товары на странице
        products = soup.find_all('div', class_='n-catalog-item relative grid-item n-catalog-item__product')

        if not products:
            print(f"Товары на странице {page_number} не найдены.")
            return []

        parsed_data_page = []
        for product in products:
            try:
                # Название товара
                title_elem = product.find('a', class_='n-catalog-item__name-link')
                title = title_elem.text.strip() if title_elem else 'Название не найдено'

                # Цена товара
                price_elements = product.find_all('span', class_=re.compile(r'bold price-item.*'))
                price = price_elements[0].text.strip() if price_elements else 'Необходимо уточнять'
                price = re.sub(r'\D', '', price)[:-2]

                # Артикул товара
                articule = product.find('div', class_='n-catalog-item__article')
                number_elem = articule.find('span', class_='string bold nowrap n-catalog-item__click-copy n-catalog-item__ellipsis') if articule else None
                number = number_elem.text.strip() if number_elem else 'Артикул не найден'

                # Ссылка на товар
                link_elem = product.find('a', class_='n-catalog-item__name-link')
                link = f"https://www.autoopt.ru{link_elem['href']}" if link_elem else 'Ссылка не найдена'

                # URL изображения
                thumbnail_div = product.find('div', class_='lightbox__thumbnail-img')
                style = thumbnail_div['style'] if thumbnail_div else ''
                start_index = style.find('url(') + len('url(')
                end_index = style.find(')', start_index)
                image_url = style[start_index:end_index].strip(' &quot;') if start_index >= 0 and end_index >= 0 else None

                if image_url:
                    image_url = f"https://www.autoopt.ru{image_url.strip('\"')}"
                else:
                    image_url = 'Нет изображения'

                parsed_data_page.append((current_date, title, number, price, image_url, link))
            except Exception as e:
                print(f"Ошибка при обработке товара на странице {page_number}: {e}")

        return parsed_data_page

    except Exception as e:
        print(f"Ошибка при загрузке страницы {page_number}: {e}")
        return []

# Список для хранения данных о товарах
parsed_data = []
def ensure_connection():
    if not conn.is_connected():
        conn.reconnect()
# Проходим по всем страницам
for page_number in range(1, total_pages + 1):
    ensure_connection()
    page_data = parse_page(page_number)
    parsed_data.extend(page_data)

# Проверка на новые товары или изменение цены
new_entries = []

for current_date, title, number, price, image, link in parsed_data:
    if link in existing_data_dict:
        last_price = existing_data_dict[link]
        if price != last_price:  # Цена изменилась
            new_entries.append((current_date, title, number, price, image, link))
    else:
        new_entries.append((current_date, title, number, price, image, link))

# Добавление новых товаров и товаров с измененной ценой в базу данных
if new_entries:
    print("Найдены новые товары или изменения в цене, добавляем в базу данных.")
    cursor.executemany('''
        INSERT INTO productsV3 (date_parsed, title, number, price, image, link)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', new_entries)
else:
    print("Изменений нет, данные не будут добавлены.")

# Обновляем таблицу актуальных данных новыми данными текущего дня
cursor.executemany('''
    INSERT INTO today_productsV3 (date_parsed, title, number, price, image, link)
    VALUES (%s, %s, %s, %s, %s, %s)
''', parsed_data)



# Сохранение и закрытие соединения
conn.commit()
cursor.close()
conn.close()
driver.quit()
