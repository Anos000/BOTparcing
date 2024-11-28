from datetime import datetime
from fuzzywuzzy import fuzz
from io import BytesIO
import matplotlib.pyplot as plt
from telebot import types
import matplotlib
import pytz
matplotlib.use('Agg')


# Функция для проверки артикула в базе данных
def articul_in_database(query, table_names, connection_pool):
    for table_name in table_names:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE number = %s)", (query,))
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        if bool(result):
            return True
    return False

# Функция для получения всех продуктов из таблиц
def fetch_all_products(cursor, table_names):
    all_products = []
    for table_name in table_names:
        cursor.execute(f"SELECT id, date_parsed, title, number, price, image, link FROM {table_name}")
        all_products.extend(cursor.fetchall())
    return all_products

# Функция для поиска продуктов по названию
def search_products_title(products, query):
    found_products = []
    query_lower = query.lower().strip()

    for product in products:
        title_score = fuzz.partial_ratio(query_lower, product[2].lower())
        if title_score >= 81:
            found_products.append(product)

    found_products.sort(key=lambda x: float(x[4]) if x[4].replace('.', '', 1).isdigit() else 0, reverse=False)
    del found_products[100:]
    found_products.reverse()
    return found_products

# Функция для поиска продуктов по артикулу
def search_products_articul(products, query):
    found_products = []
    for product in products:
        if query.strip() == product[3].strip():
            found_products.append(product)

    found_products.sort(key=lambda x: float(x[4]) if x[4] and x[4].replace('.', '', 1).isdigit() else 999999999, reverse=False)
    del found_products[100:]
    found_products.reverse()
    return found_products

# Основная функция для поиска продуктов
def search_products(query, chat_id, bot, connection_pool):
    table_names = ['All_today_products']

    conn = connection_pool.get_connection()
    cursor = conn.cursor()
    all_products = fetch_all_products(cursor, table_names)

    if articul_in_database(query, table_names, connection_pool):
        found_products = search_products_articul(all_products, query)
    else:
        found_products = search_products_title(all_products, query)

    if found_products:
        message = "Найденные товары (по убыванию цены):\n"
        for i, product in enumerate(found_products, start=1):
            price = product[4] if product[4] and product[4].replace('.', '', 1).isdigit() and int(
                product[4]) < 999999999 else 'Необходимо уточнять'
            site = 'Автобат36' if product[6].startswith('https://avtobat36.ru') else 'Воронеж Комплект' if product[6].startswith('https://vapkagro.ru') else 'Авто Альянс'

            message += (
                f"{i}. \n"
                f"Название сайта: {site}; \n"
                f"Название: {product[2]}; \n"
                f"Артикул: {product[3]}; \n"
                f"Цена: {price}; \n"
                f"Переход на сайт: [Переход на сайт]({product[6]})\n"
            )

            markup = types.InlineKeyboardMarkup()  # Создаем объект для клавиатуры
            if product[6].startswith('https://www.autoopt.ru'):
                button_link = product[6].split("/", 4)[4][:55]  # Формируем уникальный ID кнопки для графика
                button_graph = types.InlineKeyboardButton("Динамика цен", callback_data=f"grapic_{button_link}")
            else:
                button_graph = types.InlineKeyboardButton("Динамика цен", callback_data=f"grapic_{product[6][-55:]}")

            # Добавляем кнопку для добавления товара в список
            if product[6].startswith('https://www.autoopt.ru'):
                button_link = product[6].split("/", 4)[4][:50]  # Формируем уникальный ID кнопки для графика
                button_add = types.InlineKeyboardButton("Добавить в список", callback_data=f"add_product_{button_link}")
            else:
                button_add = types.InlineKeyboardButton("Добавить в список", callback_data=f"add_product_{product[6][-50:]}")

            markup.add(button_graph, button_add)

            # Отправляем сообщение с кнопкой
            bot.send_message(chat_id, message, reply_markup=markup, parse_mode='Markdown')
            message = ""  # Очищаем сообщение для следующих товаров

        # Отправляем последнее сообщение, если оно осталось
        if message:
            bot.send_message(chat_id, message, parse_mode='Markdown')

    else:
        message = f"Товары по вашему запросу '{query}' не найдены."
        bot.send_message(chat_id, message)

    cursor.close()
    conn.close()

# Функция для построения графика изменения цены
def plot_price_history_by_articul(bot, chat_id, product_id, connection_pool):
    conn = connection_pool.get_connection()
    cursor = conn.cursor()

    # Список таблиц для проверки
    table_names = ['All_products']
    data = []

    # Выполняем поиск в каждой таблице и добавляем результаты в общий список
    for table_name in table_names:
        cursor.execute(f"SELECT date_parsed, price, title FROM {table_name} WHERE link LIKE %s", (f"%{product_id}%",))
        data.extend(cursor.fetchall())

    cursor.close()
    conn.close()

    if not data:
        bot.send_message(chat_id, f"Извините, данные по товару не были найдены.")
        print(f"Запрос для ссылки {product_id} не дал результатов.")
        return

    dates = [row[0] if isinstance(row[0], datetime) else datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S') for row in data]
    tz = pytz.timezone("Europe/Moscow")
    dates.append(datetime.now(tz))

    prices = []
    last_row = 0
    for row in data:
        if row[1] is not None and row[1].replace('.', '', 1).isdigit():
            prices.append(float(row[1]))
            last_row = float(row[1])
        else:
            prices.append(0)
            last_row = 0
    prices.append(last_row)

    plt.figure(figsize=(10, 5))
    plt.plot(dates, prices, marker='o', linestyle='-', color='b')
    plt.title(f"Изменение цены для товара {data[0][2]}")
    plt.xlabel("Дата")
    plt.ylabel("Цена")
    plt.grid()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    bot.send_photo(chat_id=chat_id, photo=buffer)
    plt.close()
    buffer.close()
