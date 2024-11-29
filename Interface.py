import tkinter as tk
import requests
import base64
from dotenv import load_dotenv
import os
import mysql.connector
from tkinter import messagebox, filedialog
import zipfile
from datetime import datetime
import csv

# Загрузка конфигурации из .env
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN не найден. Проверьте файл .env.")

# Конфигурация репозитория
REPO_OWNER = "Anos000"
REPO_NAME = "BOTparcing"
WORKFLOW_FILE = ".github/workflows/All_my_sql.yml"
FILE_NAME = "settings.txt"
BRANCH_NAME = "main"

# API URLs
GET_FILE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{WORKFLOW_FILE}"
UPDATE_FILE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{WORKFLOW_FILE}"

GET_FILE_URL_SETTINGS = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_NAME}"
UPDATE_FILE_URL_SETTINGS = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_NAME}"


# Заголовки для авторизации
headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


def get_current_file_content(FILE_URL):
    response = requests.get(FILE_URL, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Не удалось получить файл: {response.text}")

    file_data = response.json()
    file_content = base64.b64decode(file_data['content']).decode('utf-8')
    return file_content, file_data['sha']


def load_settings():
    if os.path.exists("settings.txt"):
        try:
            with open("settings.txt", "r") as file:
                lines = file.read().splitlines()
                if len(lines) == 4:
                    return lines
        except Exception as e:
            print(f"Ошибка при чтении настроек: {e}")
    return ["", "", "", ""]  # Возвращаем пустые значения, если файл не найден или ошибка


saved_host, saved_user, saved_password, saved_database = load_settings()


def disable_parser_on_github(parser_name, enable):
    try:
        file_content, sha = get_current_file_content(GET_FILE_URL)
        lines = file_content.split('\n')
        new_lines = []
        skip_block = False
        for line in lines:
            if f"- name: Run Python parser {parser_name}" in line:
                if enable:
                    # Убираем `#` перед строкой с учетом отступов
                    stripped_line = line.lstrip()
                    if stripped_line.startswith("#"):
                        new_lines.append(line[:line.index("#")] + stripped_line[1:].strip())
                    else:
                        new_lines.append(line)
                else:
                    # Добавляем `#` в начало строки с сохранением отступов
                    new_lines.append(f"{line[:line.find('- name')]}# {line.strip()}")
                skip_block = True
                continue
            if skip_block:
                # Комментируем или восстанавливаем блок, относящийся к парсеру
                if line.strip().startswith("- name:") and not line.strip().startswith("#"):
                    skip_block = False
                else:
                    if enable:
                        # Убираем `#` с учетом отступов
                        stripped_line = line.lstrip()
                        if stripped_line.startswith("#"):
                            new_lines.append(line[:line.index("#")] + stripped_line[1:].strip())
                        else:
                            new_lines.append(line)
                    else:
                        # Добавляем `#` с сохранением текущего отступа
                        leading_spaces = len(line) - len(line.lstrip())
                        new_lines.append(f"{' ' * leading_spaces}# {line.strip()}")
                    continue
            new_lines.append(line)

        updated_content = '\n'.join(new_lines)
        encoded_content = base64.b64encode(updated_content.encode('utf-8')).decode('utf-8')
        update_payload = {
            "message": f"Disable parser {parser_name}" if not enable else f"Enable parser {parser_name}",
            "content": encoded_content,
            "sha": sha,
            "branch": BRANCH_NAME
        }
        update_response = requests.put(UPDATE_FILE_URL, headers=headers, json=update_payload)
        if update_response.status_code == 200:
            messagebox.showinfo("Успех", f"Парсер {parser_name} {'включен' if enable else 'выключен'}!")
        else:
            raise Exception(f"Ошибка обновления файла: {update_response.text}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")


def update_cron_schedule(new_cron_expression):
    try:
        file_content, sha = get_current_file_content(GET_FILE_URL)
        lines = file_content.split('\n')
        updated_lines = []

        cron_pattern = "cron:"
        cron_found = False

        for line in lines:
            if cron_pattern in line and not cron_found:
                updated_lines.append(
                    f"    - cron: '{new_cron_expression}'  # Запуск ежедневно в {new_cron_expression} UTC")
                cron_found = True
            else:
                updated_lines.append(line)

        if not cron_found:
            updated_lines.append(f"{cron_pattern}  # Добавить cron выражение если оно не было найдено")

        updated_content = '\n'.join(updated_lines)

        encoded_content = base64.b64encode(updated_content.encode('utf-8')).decode('utf-8')
        update_payload = {
            "message": f"Обновить расписание парсера на {new_cron_expression}",
            "content": encoded_content,
            "sha": sha,
            "branch": BRANCH_NAME
        }

        update_response = requests.put(UPDATE_FILE_URL, headers=headers, json=update_payload)
        if update_response.status_code == 200:
            messagebox.showinfo("Успех", f"Время запуска парсера обновлено на {new_cron_expression}!")
        else:
            raise Exception(f"Ошибка обновления файла: {update_response.text}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")


def update_checkbuttons_state():
    try:
        file_content, _ = get_current_file_content(GET_FILE_URL)
        lines = file_content.splitlines()
        parser1_disabled = False
        parser2_disabled = False
        parser3_disabled = False
        for line in lines:
            if line.strip().startswith('#'):
                if 'Run Python parser 1' in line:
                    parser1_disabled = True
                if 'Run Python parser 2' in line:
                    parser2_disabled = True
                if 'Run Python parser 3' in line:
                    parser3_disabled = True
        var_parser1.set(0 if parser1_disabled else 1)
        var_parser2.set(0 if parser2_disabled else 1)
        var_parser3.set(0 if parser3_disabled else 1)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось обновить состояние чекбоксов: {e}")


# Интерфейс Tkinter
root = tk.Tk()
root.title("Управление парсерами на GitHub")
root.geometry("600x400")  # Увеличиваем размер окна

# Контейнер для чекбоксов
checkbox_frame = tk.Frame(root)

# Переменные для чекбоксов
var_parser1 = tk.IntVar()
var_parser2 = tk.IntVar()
var_parser3 = tk.IntVar()

chk_parser1 = tk.Checkbutton(checkbox_frame, text="Parser 1", variable=var_parser1, onvalue=1, offvalue=0,
                             command=lambda: disable_parser_on_github(1, var_parser1.get() == 1), width=25)
chk_parser2 = tk.Checkbutton(checkbox_frame, text="Parser 2", variable=var_parser2, onvalue=1, offvalue=0,
                             command=lambda: disable_parser_on_github(2, var_parser2.get() == 1), width=25)
chk_parser3 = tk.Checkbutton(checkbox_frame, text="Parser 3", variable=var_parser3, onvalue=1, offvalue=0,
                             command=lambda: disable_parser_on_github(3, var_parser3.get() == 1), width=25)

# Добавление недостающих элементов интерфейса
label_cron = tk.Label(root, text="Введите время запуска парсера:")
label_hours = tk.Label(root, text="Часы:")
label_minutes = tk.Label(root, text="Минуты:")
entry_hours = tk.Entry(root, width=5)
entry_minutes = tk.Entry(root, width=5)
btn_update_cron = tk.Button(root, text="Обновить время", command=lambda: change_cron_time(), width=30)


# Функция для показа чекбоксов
def show_checkboxes():
    select_site_btn.pack_forget()  # Скрываем кнопку "Выбрать парсеры"
    btn_change_cron_time.pack_forget()  # Скрываем кнопку "Изменить время"
    clear_base_btn.pack_forget()
    download_show_btn.pack_forget()
    update_show_btn.pack_forget()

    checkbox_frame.pack(pady=10)
    chk_parser1.pack(pady=10)
    chk_parser2.pack(pady=10)
    chk_parser3.pack(pady=10)
    update_checkbuttons_state()
    back_btn.pack(pady=10)


# Функция для изменения cron выражения
def change_cron_time():
    try:
        # Получаем значения из полей для часов и минут
        hours = entry_hours.get()
        minutes = entry_minutes.get()

        # Проверка на то, что введены числа
        if not hours.isdigit() or not minutes.isdigit():
            messagebox.showerror("Ошибка", "Время должно быть числом!")
            return

        hours = int(hours)
        minutes = int(minutes)

        # Проверка на допустимые значения
        if hours < 0 or hours >= 24:
            messagebox.showerror("Ошибка", "Часы должны быть в пределах от 0 до 23!")
            return

        if minutes < 0 or minutes >= 60:
            messagebox.showerror("Ошибка", "Минуты должны быть в пределах от 0 до 59!")
            return

        # Если все значения корректны, создаем cron выражение
        new_cron_expression = f"{minutes} {hours} * * *"  # Минуты и часы на своих местах
        update_cron_schedule(new_cron_expression)

    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")


# Функция для показа поля ввода и кнопки для изменения времени
def show_cron_input():
    # Скрываем все кнопки и элементы предыдущего экрана
    select_site_btn.pack_forget()  # Скрываем кнопку "Выбрать парсеры"
    btn_change_cron_time.pack_forget()  # Скрываем кнопку "Изменить время"
    clear_base_btn.pack_forget()
    download_show_btn.pack_forget()
    update_show_btn.pack_forget()

    # Показываем компоненты для изменения cron
    label_cron.pack(pady=10)
    label_hours.pack(pady=5)
    entry_hours.pack(pady=5)
    label_minutes.pack(pady=5)  # Показываем метку минут
    entry_minutes.pack(pady=5)  # Показываем поле ввода минут
    btn_update_cron.pack(pady=10)
    back_btn.pack(pady=10)

    # Сбрасываем значения в поля для часов и минут
    entry_hours.delete(0, tk.END)
    entry_minutes.delete(0, tk.END)

    entry_hours.insert(0, '0')
    entry_minutes.insert(0, '0')


def clear_database():
    host, user, password, database = load_settings()
    date = date_entry.get()

    # Проверяем, выбраны ли сайты для очистки
    selected_sites = []
    if site1_var.get():
        selected_sites.append(1)
    if site2_var.get():
        selected_sites.append(2)
    if site3_var.get():
        selected_sites.append(3)

    if not selected_sites:
        messagebox.showwarning("Предупреждение", "Пожалуйста, выберите хотя бы один сайт для очистки.")
        return

    if not date:
        messagebox.showwarning("Предупреждение", "Пожалуйста, введите дату!")
        return

    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        if connection.is_connected():
            cursor = connection.cursor()
            # Проверка существования таблицы products
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'All_products';
            """, (database,))
            if cursor.fetchone()[0] == 1:
                # Формируем строку для параметризованного IN-запроса
                site_ids_placeholder = ', '.join(['%s'] * len(selected_sites))
                delete_query = f"""
                    DELETE FROM All_products
                    WHERE date_parsed <= %s AND site_id IN ({site_ids_placeholder});
                """
                cursor.execute(delete_query, [date] + selected_sites)
                connection.commit()
                messagebox.showinfo("Успех",
                                    f"Удалены записи из 'products', старше {date}, для сайтов: {', '.join(map(str, selected_sites))}.")
            else:
                messagebox.showwarning("Внимание", "Таблица 'products' не найдена в базе данных.")
            cursor.close()
            connection.close()
    except mysql.connector.Error as err:
        messagebox.showerror("Ошибка", f"Не удалось очистить таблицу: {err}")


# Функция для подменю очистки базы
def show_clear():
    # Скрываем все кнопки и элементы предыдущего экрана
    select_site_btn.pack_forget()  # Скрываем кнопку "Выбрать парсеры"
    btn_change_cron_time.pack_forget()  # Скрываем кнопку "Изменить время"
    clear_base_btn.pack_forget()
    download_show_btn.pack_forget()
    update_show_btn.pack_forget()

    label_date.pack(pady=5)
    date_entry.pack(pady=5)
    chk_site_clear1.pack(pady=5)
    chk_site_clear2.pack(pady=5)
    chk_site_clear3.pack(pady=5)
    clear_button.pack(pady=5)
    back_btn.pack(pady=10)


def get_all_tables():
    host, user, password, database = load_settings()
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        cursor.close()
        connection.close()
        return tables
    except mysql.connector.Error as e:
        messagebox.showerror("Ошибка", f"Не удалось подключиться к базе данных: {e}")
        return []


# Экспорт таблицы в CSV
def export_table_to_csv(table_name, output_folder):
    host, user, password, database = load_settings()
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        cursor = connection.cursor()

        # Преобразуем имя таблицы в строку, если оно передано как байтовая строка
        if isinstance(table_name, (bytes, bytearray)):
            table_name = table_name.decode("utf-8")

        cursor.execute(f"SELECT * FROM `{table_name}`")  # Используем обратные кавычки для имени таблицы

        # Определяем путь для сохранения CSV
        csv_path = os.path.join(output_folder, f"{table_name}.csv")

        # Записываем данные в CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([i[0] for i in cursor.description])  # Заголовки столбцов
            writer.writerows(cursor.fetchall())  # Данные
        cursor.close()
        connection.close()
        return csv_path
    except mysql.connector.Error as e:
        messagebox.showerror("Ошибка", f"Не удалось экспортировать таблицу {table_name}: {e}")
        print("Ошибка", f"Не удалось экспортировать таблицу {table_name}: {e}")
        return None



# Создание ZIP архива с таблицами
def create_zip_archive(file_paths, output_folder):
    # Генерируем имя ZIP файла с текущей датой
    today_date = datetime.now().strftime("%Y-%m-%d")
    zip_path = os.path.join(output_folder, f"{today_date}.zip")

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file_path in file_paths:
            zipf.write(file_path, os.path.basename(file_path))
            os.remove(file_path)  # Удаляем временные файлы CSV
    return zip_path


# Экспорт всех таблиц базы данных
def export_all_tables():
    # Выбор папки для сохранения
    output_folder = filedialog.askdirectory(title="Выберите папку для сохранения")
    if not output_folder:
        return

    # Получение списка таблиц
    tables = get_all_tables()
    if not tables:
        return

    # Экспортируем все таблицы
    csv_files = []
    for table in tables:
        csv_path = export_table_to_csv(table, output_folder)
        if csv_path:
            csv_files.append(csv_path)

    if csv_files:
        # Упаковываем в ZIP
        zip_path = create_zip_archive(csv_files, output_folder)
        messagebox.showinfo("Успех", f"Данные базы экспортированы в архив: {zip_path}")
    else:
        messagebox.showwarning("Предупреждение", "Не удалось экспортировать таблицы.")


def show_download():
    # Скрываем все кнопки и элементы предыдущего экрана
    select_site_btn.pack_forget()  # Скрываем кнопку "Выбрать парсеры"
    btn_change_cron_time.pack_forget()  # Скрываем кнопку "Изменить время"
    clear_base_btn.pack_forget()
    download_show_btn.pack_forget()
    update_show_btn.pack_forget()

    download_btn.pack(pady=10)
    back_btn.pack(pady=10)


# Функция для проверки подключения к базе данных
def check_database_connection(host, user, password, db):
    try:
        # Пробуем подключиться к базе данных
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=db
        )
        connection.close()
        return True
    except mysql.connector.Error as err:
        print(f"Ошибка подключения к базе данных: {err}")
        return False


# Функция для обновления параметров базы данных на GitHub
def update_database_params_in_github(new_params):
    try:
        file_content, sha = get_current_file_content(GET_FILE_URL_SETTINGS)

        # Разбиваем содержимое файла на строки
        lines = file_content.splitlines()

        # Обновляем параметры
        lines[0] = new_params['host']
        lines[1] = new_params['user']
        lines[2] = new_params['password']
        lines[3] = new_params['name']

        # Собираем обновленное содержимое файла
        updated_content = "\n".join(lines)
        encoded_content = base64.b64encode(updated_content.encode('utf-8')).decode('utf-8')

        update_payload = {
            "message": "Обновление параметров базы данных",
            "content": encoded_content,
            "sha": sha,
            "branch": BRANCH_NAME
        }

        update_response = requests.put(UPDATE_FILE_URL_SETTINGS, headers=headers, json=update_payload)
        if update_response.status_code == 200:
            print("Параметры базы данных обновлены на GitHub!")
            messagebox.showinfo("Success", "Параметры базы данных успешно обновлены на GitHub!")
        else:
            raise Exception(f"Ошибка обновления файла: {update_response.text}")
    except Exception as e:
        print(f"Ошибка при обновлении файла: {e}")
        messagebox.showerror("Error", f"Ошибка при обновлении файла: {e}")


# Функция для подключения и изменения параметров на локальной машине
def update_local_settings(new_params):
    file_name = 'settings.txt'
    try:
        with open(file_name, "w") as file:
            file.write(f"{new_params['host']}\n")
            file.write(f"{new_params['user']}\n")
            file.write(f"{new_params['password']}\n")
            file.write(f"{new_params['name']}\n")
        messagebox.showinfo("Success", "Параметры базы данных успешно обновлены локально!")
    except Exception as e:
        print(f"Ошибка при обновлении локальных настроек: {e}")
        messagebox.showerror("Error", f"Ошибка при обновлении локальных настроек: {e}")


# Функция для обработки отправки данных
def on_submit():
    host = entry_host.get()
    user = entry_user.get()
    password = entry_password.get()
    db = entry_db.get()

    # Проверяем подключение к базе данных
    if check_database_connection(host, user, password, db):
        print("Подключение к базе данных успешно!")

        # Новые параметры для базы данных
        new_db_params = {
            'host': host,
            'user': user,
            'password': password,
            'name': db
        }

        # Обновляем параметры как локально, так и на GitHub
        update_local_settings(new_db_params)
        update_database_params_in_github(new_db_params)
    else:
        messagebox.showerror("Connection Error", "Ошибка подключения к базе данных. Проверьте данные.")


def show_update():
    # Скрываем все кнопки и элементы предыдущего экрана
    select_site_btn.pack_forget()  # Скрываем кнопку "Выбрать парсеры"
    btn_change_cron_time.pack_forget()  # Скрываем кнопку "Изменить время"
    clear_base_btn.pack_forget()
    download_show_btn.pack_forget()
    update_show_btn.pack_forget()

    label_host.grid(row=0, column=0)
    entry_host.grid(row=0, column=1)
    label_user.grid(row=1, column=0)
    entry_user.grid(row=1, column=1)
    label_password.grid(row=2, column=0)
    entry_password.grid(row=2, column=1)
    label_db.grid(row=3, column=0)
    entry_db.grid(row=3, column=1)
    submit_button.grid(row=4, column=0, columnspan=2)

    back_btn.grid(row=5, column=0, columnspan=2)


# Функция для возврата в главное меню
def back_to_main_menu():
    # Скрываем блоки, связанные с выбором парсеров и cron
    checkbox_frame.pack_forget()  # Скрываем блок чекбоксов
    label_cron.pack_forget()  # Скрываем поле для cron
    label_hours.pack_forget()  # Скрываем поле для ввода
    entry_hours.pack_forget()  # Скрываем поле для ввода
    entry_minutes.pack_forget()  # Скрываем поле для ввода
    btn_update_cron.pack_forget()  # Скрываем кнопку обновления
    back_btn.pack_forget()  # Скрываем кнопку возврата
    label_minutes.pack_forget()

    label_date.pack_forget()
    date_entry.pack_forget()
    chk_site_clear1.pack_forget()
    chk_site_clear2.pack_forget()
    chk_site_clear3.pack_forget()
    clear_button.pack_forget()

    download_btn.pack_forget()

    label_host.grid_forget()
    entry_host.grid_forget()
    label_user.grid_forget()
    entry_user.grid_forget()
    label_password.grid_forget()
    entry_password.grid_forget()
    label_db.grid_forget()
    entry_db.grid_forget()
    submit_button.grid_forget()
    back_btn.grid_forget()

    # Показываем элементы главного меню
    update_show_btn.pack(pady=10)
    select_site_btn.pack(pady=10)  # Показываем кнопку "Выбрать парсеры"
    btn_change_cron_time.pack(pady=10)  # Показываем кнопку "Изменить время"
    clear_base_btn.pack(pady=10)
    download_show_btn.pack(pady=10)



label_date = tk.Label(root, text="Дата (YYYY-MM-DD)")
date_entry = tk.Entry(root, width=30)
site1_var = tk.BooleanVar()
site2_var = tk.BooleanVar()
site3_var = tk.BooleanVar()
chk_site_clear1 = tk.Checkbutton(root, text="Сайт 1 (site_id = 1)", variable=site1_var)
chk_site_clear2 = tk.Checkbutton(root, text="Сайт 2 (site_id = 2)", variable=site2_var)
chk_site_clear3 = tk.Checkbutton(root, text="Сайт 3 (site_id = 3)", variable=site3_var)
clear_button = tk.Button(root, text="Очистить таблицу 'All_products'", command=clear_database, width=30)

download_btn = tk.Button(root, text="Скачать всю базу данных", command=export_all_tables, width=30)

# Создание меток и полей для ввода для обновления данных
label_host = tk.Label(root, text="Хост базы данных:")
entry_host = tk.Entry(root)
entry_host.insert(0, saved_host)

label_user = tk.Label(root, text="Имя пользователя:")
entry_user = tk.Entry(root)
entry_user.insert(0, saved_user)

label_password = tk.Label(root, text="Пароль:")
entry_password = tk.Entry(root, show="☭")

label_db = tk.Label(root, text="Имя базы данных:")
entry_db = tk.Entry(root)
entry_db.insert(0, saved_database)

# Кнопка для обновления базы
update_show_btn = tk.Button(root, text='Обновить данные базы', command=show_update, width=30)

# Кнопка для отправки данных
submit_button = tk.Button(root, text="Подключиться и обновить", command=on_submit)

# Кнопка для изменения времени запуска парсера
btn_change_cron_time = tk.Button(root, text="Изменить время запуска парсера", command=show_cron_input, width=30)

# Кнопка для выбора парсеров
select_site_btn = tk.Button(root, text="Выбрать парсеры", command=show_checkboxes, width=30)

# Кнопка для очищения базы
clear_base_btn = tk.Button(root, text='Очистить данные', command=show_clear, width=30)

# Кнопка для скачивания базы
download_show_btn = tk.Button(root, text="Скачать всю базу данных", command=show_download, width=30)



# Кнопка для возврата в главное меню
back_btn = tk.Button(root, text="Вернуться в главное меню", command=back_to_main_menu, width=30)

# Начальная установка кнопок
update_show_btn.pack(pady=10)
select_site_btn.pack(pady=10)
btn_change_cron_time.pack(pady=10)
clear_base_btn.pack(pady=10)
download_show_btn.pack(pady=10)


root.mainloop()
