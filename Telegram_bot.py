import threading
import telebot
from telebot import types
from mysql.connector import pooling
from poisk_tovara import plot_price_history_by_articul, search_products
from reges_users import register_user, add_product_to_user_list

# Инициализация бота
bot = telebot.TeleBot('7982540414:AAFyhjCUzdsFB0SR42rHH3yjsjcgCCnFO0w')  # Замените на ваш токен

# Параметры подключения к базе данных MySQL
file = open('settings.txt', "r")
connection_pool = pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=30,  # Настройте в зависимости от нагрузки
    host=f'{file.readline().strip()}',
    user=f'{file.readline().strip()}',
    password=f'{file.readline().strip()}',
    database=f'{file.readline().strip()}'
)


@bot.message_handler(commands=['start', 'restart'])
def send_welcome(message):
    register_user(message, connection_pool)  # Регистрация пользователя
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("Поиск товара", "Вывести список", "Очистить список")
    bot.send_message(message.chat.id, "Выберите опцию из меню:", reply_markup=markup)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "Поиск товара":
        search_loop(message)
    elif message.text == "Назад":
        send_welcome(message)
    elif message.text == "Вывести список":
        show_user_products(message)
    elif message.text == "Очистить список":
        clear_user_products(message)


def search_loop(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("Назад")
    bot.send_message(message.chat.id, "Введите запрос для поиска или нажмите 'Назад' для возврата.",
                     reply_markup=markup)
    bot.register_next_step_handler(message, search_product_by_title_handler)


def search_product_by_title_handler(message):
    if message.text == "Назад":
        send_welcome(message)
    else:
        bot.send_message(message.chat.id, "Выполняю поиск …")
        search_products(message.text, message.chat.id, bot, connection_pool)  # Здесь происходит поиск
        search_loop(message)  # Возвращаемся к поиску после завершения


@bot.callback_query_handler(func=lambda call: call.data.startswith("grapic_"))
def callback_query(call):
    index = call.data.find("_")
    product_id = call.data[index + 1:]
    print(product_id)
    plot_price_history_by_articul(bot, call.message.chat.id, product_id, connection_pool)  # Построение графика по артикулу


@bot.callback_query_handler(func=lambda call: call.data.startswith("add_product_"))
def add_product_callback(call):
    product_id = call.data.split("_", 2)[2]  # Извлекаем ID продукта
    user_id = call.message.chat.id  # Получаем ID пользователя
    add_product_to_user_list(user_id, product_id, connection_pool)  # Добавляем товар в список пользователя
    bot.answer_callback_query(call.id, "Товар добавлен в ваш список!")  # Ответ на запрос, подтверждающий добавление


def show_user_products(message):
    user_id = message.chat.id  # Получаем ID пользователя
    products = get_user_products_from_db(user_id)  # Извлекаем товары пользователя из БД

    if products:
        product_list = "\n".join([
                                     f"{idx + 1}. {product[0]}\nАртикул: {product[1]}\nЦена:{product[2]}\nИзображение:{product[3]}\nСсылка:{product[4]}"
                                     for idx, product in enumerate(products)])
        bot.send_message(message.chat.id, f"Ваши товары:\n{product_list}")
    else:
        bot.send_message(message.chat.id, "Ваш список товаров пуст.")


def get_user_products_from_db(user_id):  # Функция для извлечения списка товаров пользователя из базы данных
    conn = connection_pool.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT product_link FROM user_products WHERE user_id = %s", (user_id,))
    links = cursor.fetchall()

    # Список таблиц для проверки
    table_names = ['All_today_products']
    products = []

    # Выполняем поиск в каждой таблице и добавляем результаты в общий список
    for table_name in table_names:
        for product_id in links:
            cursor.execute(f"SELECT title, number, price, image, link FROM {table_name} WHERE link LIKE %s",
                           (f"%{product_id[0]}%",))
            products.extend(cursor.fetchall())

    cursor.close()
    conn.close()
    return products


def clear_user_products(message):  # Функция для очищения списка товаров пользователя
    user_id = message.chat.id  # Получаем ID пользователя
    conn = connection_pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_products WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    bot.send_message(message.chat.id, "Ваш список товаров был очищен.")


def run_bot():
    bot.polling(none_stop=True)


bot_thread = threading.Thread(target=run_bot)
bot_thread.start()
