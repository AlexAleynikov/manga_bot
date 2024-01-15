import telebot
import json
import requests
from bs4 import BeautifulSoup
import config
import threading
import schedule
import time

bot = telebot.TeleBot(config.TOKEN)


@bot.message_handler(commands=['start'])
def handle_start(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    button = telebot.types.KeyboardButton(text="Поделиться контактом", request_contact=True)
    keyboard.add(button)

    bot.send_message(message.chat.id, "Добро пожаловать! Нажмите кнопку, чтобы поделиться контактом.", reply_markup=keyboard)


@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact

    # Загружаем текущий файл user.json, если он существует
    try:
        with open('user.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    # Проверяем, зарегистрирован ли уже пользователь с таким user_id
    registered_user = next((user for user in data if user.get("contact", {}).get("user_id") == contact.user_id), None)

    if registered_user:
        # Создаем клавиатуру для зарегистрированных пользователей
        registered_keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        show_list_button = telebot.types.KeyboardButton(text="Показать список манги")
        add_manga_button = telebot.types.KeyboardButton(text="Добавить мангу в список")
        registered_keyboard.row(show_list_button, add_manga_button)

        # Отправляем сообщение с клавиатурой
        bot.send_message(message.chat.id, f"Вы уже зарегистрированы, {contact.first_name}!", reply_markup=registered_keyboard)
    else:
        # Создаем структуру для нового пользователя
        user_data = {
            "contact": {
                "user_id": contact.user_id,
                "first_name": contact.first_name
            },
            "adding_manga": True,
            "manga_name": [],
            "manga_link": [],
            "manga_chapter": []
        }

        # Если данные уже существуют в файле, добавляем нового пользователя в список
        if isinstance(data, list):
            data.append(user_data)
        else:
            # Если данных еще нет, создаем новый список с одним пользователем
            data = [user_data]

        # Сохраняем обновленные данные в файл user.json
        with open('user.json', 'w') as file:
            json.dump(data, file)

        bot.send_message(message.chat.id, f"Вы успешно зарегистрированы, {contact.first_name}!")


@bot.message_handler(func=lambda message: message.text == "Показать список манги")
def handle_show_manga_list(message):
    try:
        # Загружаем данные пользователя из user.json
        with open('user.json', 'r') as file:
            data = json.load(file)

        # Находим пользователя в данных
        user = next((user for user in data if user.get("contact", {}).get("user_id") == message.from_user.id), None)

        if user and "manga_name" in user:
            # Получаем список манги из данных пользователя
            manga_list = user["manga_name"]

            if manga_list:
                # Отправляем сообщение со списком манги
                bot.send_message(message.chat.id, f"Ваш список манги: {', '.join(manga_list)}")
            else:
                # Отправляем сообщение, если список манги пуст
                bot.send_message(message.chat.id, "Ваш список манги пуст.")
        else:
            bot.send_message(message.chat.id, "Ошибка: Данные пользователя не найдены или отсутствует список манги.")
    except FileNotFoundError:
        bot.send_message(message.chat.id, "Ошибка: Файл с данными пользователя не найден.")


@bot.message_handler(func=lambda message: message.text == "Добавить мангу в список")
def handle_add_manga(message):
    try:
        # Загружаем данные пользователя из user.json
        with open('user.json', 'r') as file:
            data = json.load(file)

        # Находим пользователя в данных
        user = next((user for user in data if user.get("contact", {}).get("user_id") == message.from_user.id), None)

        if user:
            # Получаем название манги от пользователя
            bot.send_message(message.chat.id, 'Введите название манги')
            bot.register_next_step_handler(message, process_manga_name, user, data)
        else:
            bot.send_message(message.chat.id, "Ошибка: Данные пользователя не найдены.")
    except FileNotFoundError:
        bot.send_message(message.chat.id, "Ошибка: Файл с данными пользователя не найден.")


def process_manga_name(message, user, data):
    # Обрабатываем введенное название манги и сохраняем в user.json
    manga_name = message.text
    user["manga_name"].append(manga_name)

    # Запрашиваем у пользователя ссылку на мангу
    bot.send_message(message.chat.id, 'Введите ссылку на мангу')
    bot.register_next_step_handler(message, process_manga_link, user, data)


def process_manga_link(message, user, data):
    # Обрабатываем введенную ссылку на мангу и сохраняем в user.json
    manga_link = message.text + "/chapter/"
    user["manga_link"].append(manga_link)

    # Запрашиваем у пользователя номер главы для манги
    bot.send_message(message.chat.id, 'Введите номер главы для манги:')
    bot.register_next_step_handler(message, process_manga_chapter, user, data)


def process_manga_chapter(message, user, data):
    # Обрабатываем введенный номер главы для манги и сохраняем в user.json
    manga_chapter = message.text
    user["manga_chapter"].append(manga_chapter)

    # Сохраняем обновленные данные в файл user.json
    with open('user.json', 'w') as file:
        json.dump(data, file)

    bot.send_message(message.chat.id, 'Манга успешно добавлена в ваш список.')


def check_updates():
    try:
        # Загружаем данные пользователя из user.json
        with open('user.json', 'r') as file:
            data = json.load(file)

        # Перебираем пользователей и проверяем обновления
        for user in data:
            if "manga_name" in user:
                for i, manga_name in enumerate(user["manga_name"]):
                    manga_link = user["manga_link"][i]
                    manga_chapter = user["manga_chapter"][i]

                    # Собираем полную ссылку на главу манги
                    url = manga_link + manga_chapter
                    print(url)

                    # Отправляем запрос на сайт манги
                    response = requests.get(url)

                    # Парсим HTML-код страницы
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Проверяем наличие элемента 'div' с классом 'pt-4 mx-auto outline-0 cursor-auto w-full'
                    chapter_updated = soup.find('div', class_='pt-4 mx-auto outline-0 cursor-auto w-full')

                    if chapter_updated:
                        # Отправляем сообщение о новой главе манги
                        new_number = int(manga_chapter.split('-')[-1]) if "-" in manga_chapter else int(manga_chapter)
                        new_chapter_link = manga_link + str(new_number)
                        message_text = f"Вышла новая глава манги {manga_name}!\nСсылка на главу: {new_chapter_link}"
                        bot.send_message(user["contact"]["user_id"], message_text)

                        # Увеличиваем номер главы на 1 (если это возможно)
                        if "-" in manga_chapter:
                            try:
                                new_number = int(manga_chapter.split('-')[-1]) + 1
                                manga_chapter = manga_chapter.split('-')[0] + f"-{new_number}"
                            except ValueError:
                                bot.send_message(user["contact"]["user_id"], f"Ошибка: Невозможно определить номер главы для манги {manga_name}.")
                                continue
                        else:
                            try:
                                new_number = int(manga_chapter) + 1
                                manga_chapter = str(new_number)
                            except ValueError:
                                bot.send_message(user["contact"]["user_id"], f"Ошибка: Невозможно определить номер главы для манги {manga_name}.")
                                continue

                        # Обновляем номер главы в данных пользователя
                        user["manga_chapter"][i] = manga_chapter

                        # Сохраняем обновленные данные в файл user.json
                        with open('user.json', 'w') as file:
                            json.dump(data, file)

                    else:
                        bot.send_message(user["contact"]["user_id"], f"Новых глав для манги {manga_name} не найдено.")
    except FileNotFoundError:
        bot.send_message(user["contact"]["user_id"], "Ошибка: Файл с данными пользователя не найден.")


schedule.every(0.5).minutes.do(check_updates)


def polling_worker():
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Бот упал с ошибкой: {e}")
        time.sleep(5)


if __name__ == "__main__":
    # Создаем и запускаем отдельный поток для bot.polling
    polling_thread = threading.Thread(target=polling_worker, daemon=True)
    polling_thread.start()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        print(f"Бот упал с ошибкой: {e}")
        time.sleep(5)
