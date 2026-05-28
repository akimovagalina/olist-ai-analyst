import os
import sqlite3
import pandas as pd
import streamlit as st
import asyncio
import urllib.request
from litellm import completion

# Настройка внешнего вида страницы Streamlit
st.set_page_config(page_title="AI Olist Investigator", page_icon="🕵️‍♂️", layout="wide")

st.title("🕵️‍♂️ AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Высокоскоростной ad-hoc аудит e-commerce данных с системой самоисправления SQL")

# Безопасное считывание API Ключа из Streamlit Secrets
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# НАДЕЖНАЯ АВТОМАТИЧЕСКАЯ ЗАГРУЗКА БАЗЫ ДАННЫХ
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://github.com/akimovagalina/olist-ai-analyst/releases/download/v1.0.0/olist.db"

# Если на прошлых шагах скачался сломанный файл HTML-страницы (меньше 1 МБ), удаляем его
if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) < 1000000:
    os.remove(DB_PATH)

if not os.path.exists(DB_PATH):
    with st.spinner("📦 База данных Olist не найдена. Скачиваю оригинальный датасет маркетплейса (65 MB)..."):
        try:
            urllib.request.urlretrieve(DB_URL, DB_PATH)
            st.success("✅ База данных Olist успешно загружена и подключена!")
        except Exception as e:
            st.error(f"❌ Ошибка автоматического скачивания базы: {e}")

# Карта схемы базы данных для ИИ
DATABASE_SCHEMA = """
Table orders_dataset { 
  order_id string [pk]
  customer_id string
  order_status string 
  order_purchase_timestamp string
}
Table order_items_dataset { 
  order_id string 
  order_item_id int 
  product_id string 
  seller_id string 
  price float 
}
Table order_payments_dataset {
  order_id string
  payment_sequential integer
  payment_value float
  payment_type string
  payment_installments integer
}
Table review_dataset { 
  review_id string [pk]
  order_id string 
  review_score int 
}
Table products_dataset { 
  product_id string [pk]
  product_category_name string 
}
"""

def run_sql_query(sql_code: str) -> pd.DataFrame:
    """Выполняет SQL-запрос и возвращает DataFrame"""
    conn = sqlite3.connect(DB_PATH)
    # Оптимизация Big Data: создаем индексы для моментального выполнения JOIN на сервере
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_id ON order_items_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_order_id ON review_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_id ON order_items_dataset(product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order_id ON order_payments_dataset(order_id);")
    
    df = pd.read_sql_query(sql_code, conn)
    conn.close()
    return df

# Интерфейс ввода вопроса
default_query = "Find top 3 payment types where customers use installments more than 6 times (payment_installments > 6). What is the average payment value for these orders, and does this financial behavior correlate with low review scores?"
user_query = st.text_area("✍️ Введите любой ваш бизнес-вопрос к базе Olist на английском языке:", value=default_query, height=100)

if st.button("🚀 Запустить расследование"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Пожалуйста, укажите валидный GROQ_API_KEY в настройках Secrets!")
    else:
        with st.status("🕵️‍♂️ ИИ-аналитик изучает хранилище данных маркетплейса...", expanded=True) as status:
            try:
                st.write("🤖 Шаг 1: Генерация SQL-кода на основе схемы таблиц...")
                
                # Системный промпт, заставляющий модель выдать ТОЛЬКО чистый SQL-код
                # Усиленный системный промпт с жестким ограничением диалекта SQLite
                system_prompt = (
                    f"You are a Senior SQLite Developer. Your task is to write a valid SQLite query based on this schema:\n{DATABASE_SCHEMA}\n\n"
                    f"CRITICAL RULES:\n"
                    f"1. Use ONLY SQLite syntax. NEVER use 'EXTRACT(YEAR FROM ...)' or 'EXTRACT(MONTH FROM ...)'.\n"
                    f"2. To filter or group by dates/months/years in SQLite, ALWAYS use the 'strftime' function or 'LIKE' operator.\n"
                    f"   Examples for November 2017:\n"
                    f"   - WHERE order_purchase_timestamp LIKE '2017-11%'\n"
                    f"   - WHERE strftime('%Y', order_purchase_timestamp) = '2017' AND strftime('%m', order_purchase_timestamp) = '11'\n"
                    f"3. Return ONLY the raw SQL query. No markdown blocks, no explanations."
                )                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Write an SQL query to answer this question: {user_query}"}
                ]
                
                # Попытка №1: Генерируем и пробуем выполнить код
                response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.1
                )
                
                # Универсальное извлечение текста (совместимость с объектами и словарями)
                if hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
                    generated_sql = response.choices[0].message.content
                else:
                    generated_sql = response['choices'][0]['message']['content']
                
                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                
                try:
                    st.code(generated_sql, language="sql")
                    result_df = run_sql_query(generated_sql)
                except Exception as sql_error:
                    st.warning("⚠️ Обнаружена ошибка или галлюцинация в структуре SQL. Запускаю цикл самоисправления...")
                    
                    # Добавляем в историю переписки ошибочный запрос и ответ базы данных
                    messages.append({"role": "assistant", "content": generated_sql})
                    messages.append({
                        "role": "user", 
                        "content": f"Your previous SQL query failed with this error: {str(sql_error)}. Please analyze the database schema carefully, correct the table names or columns (ensure you JOIN order_payments_dataset if you need payment details like type or installments), and provide the fixed SQLite query. Return ONLY the raw SQL without any extra text."
                    })
                    
                    # Попытка №2: Модель анализирует свою ошибку и исправляет код
                    response = completion(
                        model="groq/llama-3.1-8b-instant",
                        messages=messages,
                        temperature=0.1
                    )
                    
                    if hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
                        generated_sql = response.choices[0].message.content
                    else:
                        generated_sql = response['choices'][0]['message']['content']
                        
                    generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                    
                    st.markdown("**Исправленный SQL-запрос:**")
                    st.code(generated_sql, language="sql")
                    result_df = run_sql_query(generated_sql)
                
                st.write("🔍 Шаг 2: Выполнение запроса в olist.db и извлечение точных метрик...")
                
                st.write("✍️ Шаг 3: Формирование аналитического отчета на русском языке...")
                
                # Отдаем полученные точные цифры модели, чтобы она красиво расписала выводы для директора
                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Ты Главный бизнес-аналитик маркетплейса Olist. Твоя задача — взять сырую таблицу данных, проанализировать её и составить краткий и емкий бизнес-отчет СТРОГО НА РУССКОМ ЯЗЫКЕ. Формат отчета: 1. Суть проблемы (Главный инсайт), 2. Цифры и факты (Доказательства из таблицы с точными значениями), 3. Бизнес-рекомендация (Что делать руководству компании?)."},
                        {"role": "user", "content": f"Вопрос пользователя: {user_query}\n\nПолученные точные данные из базы:\n{result_df.to_string(index=False)}"}
                    ],
                    temperature=0.2
                )
                
                # Универсальное извлечение текста отчета
                if hasattr(report_response, 'choices') and hasattr(report_response.choices[0], 'message'):
                    final_report = report_response.choices[0].message.content
                else:
                    final_report = report_response['choices'][0]['message']['content']
                    
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
