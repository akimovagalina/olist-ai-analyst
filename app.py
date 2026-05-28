import os
import sqlite3
import pandas as pd
import streamlit as st
import urllib.request
from litellm import completion  # Используем чистый и стабильный вызов модели

# Настройка внешнего вида страницы Streamlit
st.set_page_config(page_title="AI Olist Investigator", page_icon="🕵️‍♂️", layout="wide")

st.title("🕵️‍♂️ AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Прямой высокоскоростной ad-hoc аудит e-commerce данных с помощью Groq & Llama 3")

# Безопасное считывание API Ключа из Streamlit Secrets
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# АВТОМАТИЧЕСКАЯ ЗАГРУЗКА БАЗЫ ДАННЫХ
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://github.com/akimovagalina/olist-ai-analyst/releases/download/v1.0.0/olist.db"

if not os.path.exists(DB_PATH):
    with st.spinner("📦 База данных Olist не найдена. Скачиваю датасет маркетплейса (65 MB)..."):
        try:
            urllib.request.urlretrieve(DB_URL, DB_PATH)
            st.success("✅ База данных успешно загружена и подключена!")
        except Exception as e:
            st.error(f"❌ Не удалось автоматически скачать базу данных: {e}")

# Карта схемы базы данных для ИИ
DATABASE_SCHEMA = """
Table orders_dataset { order_id string, customer_id string, order_status string }
Table order_items_dataset { order_id string, order_item_id int, product_id string, seller_id string, price float }
Table review_dataset { review_id string, order_id string, review_score int }
Table products_dataset { product_id string, product_category_name string }
"""

def run_sql_query(sql_code: str) -> pd.DataFrame:
    """Выполняет SQL-запрос и возвращает DataFrame"""
    conn = sqlite3.connect(DB_PATH)
    # Создаем индексы для моментального выполнения JOIN на сервере
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_id ON order_items_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_order_id ON review_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_id ON order_items_dataset(product_id);")
    
    df = pd.read_sql_query(sql_code, conn)
    conn.close()
    return df

# Интерфейс ввода вопроса
default_query = "Find top 5 product categories with the highest number of worst reviews (review_score = 1), given that the category has more than 50 items sold in total."
user_query = st.text_area("✍️ Введите любой ваш бизнес-вопрос к базе Olist на английском языке:", value=default_query, height=100)

if st.button("🚀 Запустить расследование"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Пожалуйста, укажите валидный GROQ_API_KEY в настройках Secrets!")
    else:
        with st.status("🕵️‍♂️ ИИ-аналитик изучает хранилище данных...", expanded=True) as status:
            try:
                               st.write("🤖 Шаг 1: Генерация SQL-кода на основе схемы таблиц...")
                
                system_prompt = f"You are a Senior SQL Developer. Your task is to write a valid SQLite query based on this database schema:\n{DATABASE_SCHEMA}\nReturn ONLY the raw SQL query. Do not wrap it in markdown code blocks, do not write any explanations or extra text."
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Write an SQL query to answer this question: {user_query}"}
                ]
                
                # Попытка №1: Генерируем и пробуем выполнить код
                response = completion(model="groq/llama-3.1-8b-instant", messages=messages, temperature=0.1)
                generated_sql = response.choices.message.content.strip().replace("```sql", "").replace("```", "").strip()
                
                try:
                    st.code(generated_sql, language="sql")
                    result_df = run_sql_query(generated_sql)
                except Exception as sql_error:
                    st.warning("⚠️ Обнаружена ошибка в структуре SQL. Запускаю цикл самоисправления...")
                    
                    # Добавляем в историю переписки ошибочный запрос и ответ базы данных
                    messages.append({"role": "assistant", "content": generated_sql})
                    messages.append({"role": "user", "content": f"Your previous SQL query failed with this error: {str(sql_error)}. Please analyze the database schema carefully, correct the table names or columns (ensure you JOIN order_payments_dataset if you need payment info), and provide the fixed SQLite query. Return ONLY the raw SQL."})
                    
                    # Попытка №2: Модель анализирует свою ошибку и исправляет код
                    response = completion(model="groq/llama-3.1-8b-instant", messages=messages, temperature=0.1)
                    generated_sql = response.choices.message.content.strip().replace("```sql", "").replace("```", "").strip()
                    
                    st.markdown("**Исправленный SQL-запрос:**")
                    st.code(generated_sql, language="sql")
                    result_df = run_sql_query(generated_sql)

                
                generated_sql = response.choices[0].message.content.strip()
                # Очищаем от возможных кавычек маркдауна, если модель их все-таки добавила
                generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
                
                st.code(generated_sql, language="sql")
                
                st.write("🔍 Шаг 2: Выполнение запроса в olist.db и извлечение точных метрик...")
                
                # Выполняем сгенерированный SQL-код напрямую в базе данных
                result_df = run_sql_query(generated_sql)
                
                st.write("✍️ Шаг 3: Формирование аналитического отчета на русском языке...")
                
                # Отдаем полученные цифры модели, чтобы она красиво расписала выводы для директора
                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Ты Главный бизнес-аналитик маркетплейса. Твоя задача — взять сырую таблицу данных, проанализировать её и составить краткий executive summary СТРОГО НА РУССКОМ ЯЗЫКЕ. Формат отчета: 1. Суть проблемы (Главный инсайт), 2. Цифры и факты (Доказательства из таблицы с точными значениями), 3. Бизнес-рекомендация (Что делать руководству?)."},
                        {"role": "user", "content": f"Вопрос пользователя: {user_query}\n\nПолученные данные из базы:\n{result_df.to_string(index=False)}"}
                    ],
                    temperature=0.2
                )
                
                final_report = report_response.choices[0].message.content
                status.update(label="✅ Анализ успешно завершен!", state="complete", expanded=False)
                
                # Выводим точную таблицу на экран
                st.success("📊 Точные цифры из базы данных маркетплейса Olist:")
                st.dataframe(result_df, use_container_width=True)
                
                # Выводим текстовый отчет
                st.subheader("🎯 Финальный бизнес-отчет аналитика:")
                st.markdown(final_report)
                
            except Exception as e:
                status.update(label="❌ Ошибка выполнения", state="error", expanded=False)
                st.error(f"Произошел технический сбой: {e}")
