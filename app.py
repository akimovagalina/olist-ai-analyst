import os
import sqlite3
import pandas as pd
import streamlit as st
import asyncio
import urllib.request  # Добавьте этот импорт для скачивания файла
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# =====================================================================
# АВТОМАШТАБИРОВАНИЕ: АВТОМАТИЧЕСКАЯ ЗАГРУЗКА БАЗЫ ДАННЫХ
# =====================================================================
DB_PATH = "olist.db"
# Прямая ссылка на готовую и сжатую базу данных olist.db в репозитории
DB_URL = "https://github.com" 
# Примечание: Если вы решите залить базу в свой другой репозиторий или Dropbox, укажите ссылку здесь.
# Для стабильности мы можем скачать оригинальный Olist файл (65MB) с проверенного CDN:
DB_URL = "https://huggingface.co"

if not os.path.exists(DB_PATH):
    with st.spinner("📦 База данных Olist не найдена. Скачиваю датасет маркетплейса с облачного сервера (65 MB)..."):
        try:
            urllib.request.urlretrieve(DB_URL, DB_PATH)
            st.success("✅ База данных успешно загружена и подключена!")
        except Exception as e:
            st.error(f"❌ Не удалось автоматически скачать базу данных: {e}")
            st.info("Пожалуйста, убедитесь, что файл olist.db загружен вручную.")
# =====================================================================


# Настройка внешнего вида страницы Streamlit
st.set_page_config(page_title="AI Olist Investigator", page_icon="🕵️‍♂️", layout="wide")

st.title("🕵️‍♂️ AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Автономный сквозной аудит e-commerce данных с помощью Multi-Agent Crew & Gemini 2.5")

# Ввод API Ключа (можно зашить жестко или оставить ввод пользователю)
o# Безопасное чтение ключа из настроек окружения
if "GEMINI_API_KEY" not in os.environ:
    if "gemini" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["gemini"]["api_key"]


# Карта схемы базы данных
DATABASE_SCHEMA = """
Table orders_dataset { order_id string, customer_id string, order_status string }
Table order_items_dataset { order_id string, order_item_id int, product_id string, seller_id string, price float }
Table review_dataset { review_id string, order_id string, review_score int }
Table products_dataset { product_id string, product_category_name string }
"""

def run_sql_query(sql_code: str) -> str:
    try:
        conn = sqlite3.connect('olist.db')
        df = pd.read_sql_query(sql_code, conn)
        conn.close()
        if df.empty: return "Запрос выполнен, но данных не найдено."
        return df.head(10).to_string(index=False)
    except Exception as e:
        return f"Ошибка SQL-синтаксиса: {str(e)}. Перепиши запрос."

@tool("SQL Database Query Tool")
def sql_tool(sql_code: str) -> str:
    """Выполняет SQL-запрос к базе данных olist.db и возвращает результат в виде текста."""
    return run_sql_query(sql_code)

# Инициализация LLM
gemini_llm = LLM(model="google/gemini-2.5-flash", temperature=0.1)

# Создание интерфейса ввода вопроса
default_query = "Найди топ-5 категорий товаров, по которым клиенты чаще всего оставляют худшие отзывы (оценка 1), при условии, что товаров в этой категории было куплено больше 50 штук."
user_query = st.text_area("✍️ Введите ваш бизнес-вопрос к базе Olist на человеческом языке:", value=default_query, height=100)

if st.button("🚀 Запустить расследование"):
    if not os.environ.get("GEMINI_API_KEY"):
        st.error("Пожалуйста, укажите валидный GEMINI_API_KEY!")
    else:
        # Создаем контейнеры для отображения мыслей агентов в реальном времени
        with st.status("🕵️‍♂️ Команда агентов приступила к работе...", expanded=True) as status:
            
            st.write("🤖 Шаг 1: Сборка команды роботов и планирование...")
            
            sql_developer = Agent(
                role="Старший SQL-разработчик маркетплейса",
                goal="Писать точные SQL-запросы к базе olist.db для извлечения бизнес-данных.",
                backstory=f"Ты эксперт по SQLite. Пиши только чистый код без кавычек markdown. Схема:\n{DATABASE_SCHEMA}",
                tools=[sql_tool], llm=gemini_llm
            )

            business_analyst = Agent(
                role="Главный бизнес-аналитик Olist",
                goal="Изучать сырые таблицы данных и находить скрытые коммерческие проблемы маркетплейса.",
                backstory="Ты анализируешь цифры, ищешь аномалии и выявляешь причинно-следственные связи.",
                llm=gemini_llm
            )

            cmo_reporter = Agent(
                role="Директор по маркетингу маркетплейса",
                goal="Переводить сложную аналитику на понятный русский язык для топ-менеджмента Olist.",
                backstory="Ты готовишь емкие отчеты без «воды» на русском языке с четкими бизнес-рекомендациями.",
                llm=gemini_llm
            )

            task_write_sql = Task(
                description="Посмотри на вопрос: '{user_question}'. Напиши и выполни SQL-запрос через инструмент 'SQL Database Query Tool'.",
                expected_output="Сырые текстовые таблицы из базы данных.", agent=sql_developer
            )

            task_analyze_data = Task(
                description="Изучи цифры из базы. Найди ключевые коммерческие аномалии и сделай выводы.",
                expected_output="Аналитический разбор найденных проблем.", agent=business_analyst
            )

            task_write_report = Task(
                description="Оформи финальный отчет строго НА РУССКОМ ЯЗЫКЕ в формате: 1. Суть проблемы, 2. Цифры и факты, 3. Бизнес-рекомендация.",
                expected_output="Готовый Markdown отчет на русском языке.", agent=cmo_reporter
            )

            crew = Crew(
                agents=[sql_developer, business_analyst, cmo_reporter],
                tasks=[task_write_sql, task_analyze_data, task_write_report],
                process=Process.sequential
            )
            
            st.write("🔍 Шаг 2: Написание SQL-запроса и извлечение данных из olist.db...")
            
            # Запускаем асинхронную логику CrewAI внутри Streamlit
            final_result = asyncio.run(crew.kickoff_async(inputs={"user_question": user_query}))
            
            status.update(label="✅ Анализ успешно завершен!", state="complete", expanded=False)
        
        # Вывод красивого финального отчета на экран
        st.success("🎯 Результат расследования готов:")
        st.markdown(final_result)
