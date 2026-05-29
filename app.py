import os
import sqlite3
import pandas as pd
import streamlit as st
import asyncio
import urllib.request
import ssl
from litellm import completion

# Настройка внешнего вида страницы Streamlit
st.set_page_config(page_title="AI Olist Investigator", page_icon="🕵️‍♂️", layout="wide")

st.title(" AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Высокоскоростной ad-hoc аудит e-commerce данных с системой самоисправления SQL")

# Безопасное считывание API Ключа из Streamlit Secrets
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# НАДЕЖНАЯ АВТОМАТИЧЕСКАЯ ЗАГРУЗКА БАЗЫ ДАННЫХ (БЕЗ SSL-ОШИБОК)
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://github.com/akimovagalina/olist-ai-analyst/releases/download/v1.0.0/olist.db"

if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) < 1000000:
    os.remove(DB_PATH)

if not os.path.exists(DB_PATH):
    with st.spinner("📦 База данных Olist не найдена. Скачиваю оригинальный датасет маркетплейса (65 MB)..."):
        try:
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(DB_URL, context=ssl_context) as response, open(DB_PATH, 'wb') as out_file:
                out_file.write(response.read())
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
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_id ON order_items_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_order_id ON review_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_id ON order_items_dataset(product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order_id ON order_payments_dataset(order_id);")
    
    df = pd.read_sql_query(sql_code, conn)
    conn.close()
    return df

# Интерфейс ввода вопроса (Возвращаем ваш оригинальный чистый вопрос без подсказок!)
default_query = "Find out why sales fell in November 2017?"
user_query = st.text_area("✍️ Введите любой ваш бизнес-вопрос к базе Olist на английском языке:", value=default_query, height=100)

if st.button("🚀 Запустить расследование"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Пожалуйста, укажите валидный GROQ_API_KEY в настройках Secrets!")
    else:
        with st.status("🕵️‍♂️ ИИ-аналитик изучает хранилище данных маркетплейса...", expanded=True) as status:
            try:
                st.write("🤖 Шаг 1: Генерация SQL-кода на основе схемы таблиц...")
                
                # ПРОФЕССИОНАЛЬНЫЙ SQL-ПРОМПТ: Учим ИИ вытаскивать широкий контекст для сравнения периодов
                sql_system_prompt = (
                    f"You are a Senior SQLite Developer. Your task is to write a valid SQLite query based on this schema:\n{DATABASE_SCHEMA}\n\n"
                    f"CRITICAL RULES:\n"
                    f"1. Use ONLY SQLite syntax. NEVER use 'EXTRACT(YEAR/MONTH)'.\n"
                    f"2. METHODOLOGY: To understand why sales changed in a specific month/period, you MUST fetch a broader timeline for context. "
                    f"   Generate a query that extracts monthly or daily aggregates (SUM(price), COUNT(order_id)) covering at least 3-4 months surrounding the target period, "
                    f"   and if possible, the same period of the previous year, so the analyst can perform MoM (Month-over-Month) and YoY (Year-over-Year) analysis.\n"
                    f"3. Use format `SUBSTR(order_purchase_timestamp, 1, 7)` for monthly groupings or `SUBSTR(order_purchase_timestamp, 1, 10)` for daily groupings.\n"
                    f"4. Return ONLY the raw SQL query. No markdown blocks, no explanations."
                )
                
                messages = [
                    {"role": "system", "content": sql_system_prompt},
                    {"role": "user", "content": f"Write an SQL query to answer this question: {user_query}"}
                ]
                
                response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.1
                )
                
                # УНИВЕРСАЛЬНЫЙ ПАРСЕР ОТВЕТА ИИ ДЛЯ ШАГА 1 (Защита от 'list indices' ошибок)
                try:
                    if hasattr(response, 'choices') and hasattr(response.choices, 'message'):
                        generated_sql = response.choices.message.content
                    elif isinstance(response, list):
                        generated_sql = response[0]['message']['content']
                    else:
                        generated_sql = response['choices']['message']['content']
                except Exception:
                    generated_sql = str(response)
                
                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                
                try:
                    st.code(generated_sql, language="sql")
                    result_df = run_sql_query(generated_sql)
                except Exception as sql_error:
                    st.warning("⚠️ Обнаружена ошибка в структуре SQL. Запускаю цикл самоисправления...")
                    messages.append({"role": "assistant", "content": generated_sql})
                    messages.append({
                        "role": "user", 
                        "content": f"Your query failed: {str(sql_error)}. Write a clean SQLite query that aggregates sales revenue by months using SUBSTR(order_purchase_timestamp, 1, 7) as sales_month for the entire year of 2017 to provide full context. Return ONLY pure SQL."
                    })
                    
                    response = completion(
                        model="groq/llama-3.1-8b-instant",
                        messages=messages,
                        temperature=0.1
                    )
                    
                    # УНИВЕРСАЛЬНЫЙ ПАРСЕР ДЛЯ ПОВТОРНОЙ ПОПЫТКИ ШАГА 1
                    try:
                        if hasattr(response, 'choices') and hasattr(response.choices, 'message'):
                            generated_sql = response.choices.message.content
                        elif isinstance(response, list):
                            generated_sql = response[0]['message']['content']
                        else:
                            generated_sql = response['choices']['message']['content']
                    except Exception:
                        generated_sql = str(response)
                        
                    generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                    st.markdown("**Исправленный SQL-запрос:**")
                    st.code(generated_sql, language="sql")
                    result_df = run_sql_query(generated_sql)
                
                st.write("🔍 Шаг 2: Выполнение запроса в olist.db и извлечение точных метрик...")
                st.write("✍ {🖨️} Шаг 3: Формирование аналитического отчета на русском языке...")
                
                # МЕТОДОЛОГИЧЕСКИЙ ПРОМПТ АНАЛИТИКА: Требуем глубокого сравнительного анализа и генерации гипотез
                analyst_system_prompt = (
                    "Ты Ведущий продуктовый аналитик маркетплейса Olist с глубоким пониманием ритейл-календаря. Твоя задача — провести глубокий сравнительный аудит данных и составить отчет СТРОГО НА РУССКОМ ЯЗЫКЕ.\n\n"
                    "МЕТОДОЛОГИЯ АНАЛИЗА ДЛЯ ПОРТФОЛИО:\n"
                    "1. СРАВНИТЕЛЬНЫЙ АНАЛИЗ (MoM / YoY): Внимательно изучи всю временную шкалу в таблице. Сравни целевой месяц (ноябрь 2017) с предыдущими месяцами (сентябрь, октябрь) и последующими (декабрь), а также с прошлым годом, если эти данные есть. Определи реальный математический тренд.\n"
                    "2. КРИТИКА ГИПОТЕЗЫ ПОЛЬЗОВАТЕЛЯ: Если в вопросе утверждается, что продажи упали, но на основе сравнения с сентябрем/октябрем ты видишь взрывной рост — прямо опровергни пользователя. Напиши: 'Внимание: гипотеза о падении продаж не подтвердилась. Данные доказывают обратное...'.\n"
                    "3. ГЕНЕРАЦИЯ БИЗНЕС-ГИПОТЕЗ: Опираясь на точные даты или характер скачка выручки (например, если продажи выросли в разы в конце ноября), выдвини сильные аналитические гипотезы о причинах (сезонность, крупные глобальные распродажи вроде Черной пятницы, маркетинговые акции) без прямых подсказок в коде.\n"
                    "4. СТРУКТУРА ОТЧЕТА:\n"
                    "   - 1. Главный инсайт и Опровержение/Подтверждение тренда (Анализ динамики соседних месяцев)\n"
                    "   - 2. Цифры и факты (Точные значения выручки по месяцам/периодам для доказательства)\n"
                    "   - 3. Аналитические гипотезы (Почему произошел такой аномальный скачок/спад? Какие внешние факторы могли повлиять?)\n"
                    "   - 4. Бизнес-рекомендация (Что делать менеджменту на основе этих выводов)"
                )
                
                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": analyst_system_prompt},
                        {"role": "user", "content": f"Вопрос пользователя: {user_query}\n\nПолученные широкие данные из базы для контекста:\n{result_df.to_string(index=False)}"}
                    ],
                    temperature=0.2
                )
                
                # УНИВЕРСАЛЬНЫЙ ПАРСЕР ОТВЕТА ИИ ДЛЯ ШАГА 3 (Защита от 'list indices' ошибок)
                try:
                    if hasattr(report_response, 'choices') and hasattr(report_response.choices, 'message'):
                        final_report = report_response.choices.message.content
                    elif isinstance(report_response, list):
                        final_report = report_response[0]['message']['content']
                    else:
                        final_report = report_response['choices']['message']['content']
                except Exception:
                    final_report = str(report_response)
                    
                status.update(label="✅ Анализ успешно завершен!", state="complete", expanded=False)
                
                st.success("📊 Исторические данные из базы данных маркетплейса Olist для контекст-анализа:")
                st.dataframe(result_df, use_container_width=True)
                
                st.subheader("🎯 Финальный бизнес-отчет аналитика:")
                st.markdown(final_report)
                
            except Exception as e:
                status.update(label="❌ Ошибка выполнения", state="error", expanded=False)
                st.error(f"Произошел технический сбой: {e}")
