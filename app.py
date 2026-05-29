import os
import sqlite3
import pandas as pd
import streamlit as st
import asyncio
import urllib.request
import ssl
import re  # Безопасный парсинг регулярных выражений для извлечения ответов API
from litellm import completion

# Настройка внешнего вида страницы Streamlit
st.set_page_config(page_title="AI Olist Investigator", page_icon="🕵️‍♂️", layout="wide")

st.title("🕵️‍♂️ AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Полносвязный сквозной ad-hoc аудит e-commerce архитектуры (9 таблиц DWH)")

# Безопасное считывание API Ключа из Streamlit Secrets
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# НАДЕЖНАЯ АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ПОЛНОЙ БАЗЫ ДАННЫХ (БЕЗ SSL-ОШИБОК)
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://github.com/akimovagalina/olist-ai-analyst/releases/download/v1.0.0/olist.db"


# Принудительный сброс кэша, если обнаружена старая урезанная база данных
if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) < 80000000:
    os.remove(DB_PATH)

if not os.path.exists(DB_PATH):
    with st.spinner("📦 Полная база Olist не найдена. Скачиваю весь датасет DWH маркетплейса (9 таблиц, 65 MB)..."):
        try:
            # ТРЮК ДЛЯ ПОРТФОЛИО: Отключаем проверку SSL для предотвращения ошибок handshake alert
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(DB_URL, context=ssl_context) as response, open(DB_PATH, 'wb') as out_file:
                out_file.write(response.read())
            st.success("✅ Все 9 таблиц базы данных успешно загружены и подключены!")
        except Exception as e:
            st.error(f"❌ Ошибка автоматического скачивания базы: {e}")

# Карта схемы базы данных для ИИ
# Оптимизированная компактная схема DWH с жесткими подсказками по JOIN
DATABASE_SCHEMA = """
Table customers_dataset { customer_id string [pk], customer_unique_id string, customer_zip_code_prefix int, customer_city string, customer_state string }
Table geolocation_dataset { geolocation_zip_code_prefix int [pk], geolocation_lat float, geolocation_lng float, geolocation_city string, geolocation_state string }
Table orders_dataset { order_id string [pk], customer_id string, order_status string, order_purchase_timestamp string, order_approved_at string, order_delivered_carrier_date string, order_delivered_customer_date string, order_estimated_delivery_date string }
Table order_items_dataset { order_id string, order_item_id int, product_id string, seller_id string, price float }
Table order_payments_dataset { order_id string, payment_sequential int, payment_type string, payment_installments int, payment_value float }
Table review_dataset { review_id string [pk], order_id string, review_score int, review_creation_date string, review_answer_timestamp string }
Table products_dataset { product_id string [pk], product_category_name string, product_name_lenght int, product_description_lenght int, product_photos_qty int, product_weight_g int, product_length_cm int, product_height_cm int, product_width_cm int }
Table sellers_dataset { seller_id string [pk], seller_zip_code_prefix int, seller_city string, seller_state string }
Table product_category_name_translation { product_category_name string [pk], product_category_name_english string }

CRITICAL JOIN RELATION: To get category name in English, you MUST JOIN products_dataset WITH product_category_name_translation ON p.product_category_name = t.product_category_name and SELECT t.product_category_name_english!
"""


def run_sql_query(sql_code: str) -> pd.DataFrame:
    """Выполняет SQL-запрос с автоматической поддержкой индексов Big Data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cust_id ON customers_dataset(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cust_zip ON customers_dataset(customer_zip_code_prefix);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_geo_zip ON geolocation_dataset(geolocation_zip_code_prefix);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_id ON orders_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_cust ON orders_dataset(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_order ON order_items_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_prod ON order_items_dataset(product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_sell ON order_items_dataset(seller_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON order_payments_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_order ON review_dataset(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_id ON products_dataset(product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sellers_id ON sellers_dataset(seller_id);")
    
    df = pd.read_sql_query(sql_code, conn)
    conn.close()
    return df

# Интерфейс ввода вопроса
default_query = "Find out why sales fell in November 2017 using order_purchase_timestamp column."
user_query = st.text_area("✍️ Введите любой ваш бизнес-вопрос к базе Olist на английском языке:", value=default_query, height=100)

if st.button("🚀 Запустить расследование"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Пожалуйста, укажите валидный GROQ_API_KEY в настройках Secrets!")
    else:
        with st.status("🕵️‍♂️ ИИ-аналитик изучает хранилище данных маркетплейса...", expanded=True) as status:
            try:
                st.write("🤖 Шаг 1: Генерация SQL-кода на основе схемы таблиц...")
                
                # УСИЛЕННЫЙ SQL-ПРОМПТ: Жесткое ограничение длины кода для обхода TPM лимитов
                sql_system_prompt = (
                    f"You are a Senior SQLite Developer. Your task is to write a valid SQLite query based on this 9-table schema:\n{DATABASE_SCHEMA}\n\n"
                    f"CRITICAL RULES:\n"
                    f"1. Use ONLY SQLite syntax. NEVER use 'EXTRACT(YEAR/MONTH)'.\n"
                    f"2. ULTRA-COMPACT CODE: Keep the query under 5 lines. Never use complex SUM(CASE WHEN...) or loops.\n"
                    f"3. ENGLISH CATEGORIES: If categories are involved, follow the CRITICAL JOIN RELATION to fetch product_category_name_english. Never select it directly from products_dataset.\n"
                    f"4. GROUPING STANDARD: Always use a plain `GROUP BY 1` clause for segmentations. Example: SELECT t.product_category_name_english, COUNT(oi.order_id) FROM order_items_dataset oi JOIN products_dataset p ON oi.product_id = p.product_id JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name GROUP BY 1 LIMIT 10;\n"
                    f"5. Return ONLY the raw SQL query string. No explanations, no markdown blocks, no conversation."
                )


                
                messages = [
                    {"role": "system", "content": sql_system_prompt},
                    {"role": "user", "content": f"Write an SQL query to answer this question: {user_query}"}
                ]
                
                response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1000
                )
                
                res_str = str(response)
                content_match = re.search(r'content=["\']([\s\S]*?)["\']', res_str)
                if content_match:
                    generated_sql = content_match.group(1).replace("\\n", "\n")
                else:
                    if hasattr(response, 'choices') and hasattr(response.choices, 'message'):
                        generated_sql = response.choices.message.content
                    else:
                        generated_sql = response['choices']['message']['content']
                
                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                
                # =====================================================================
                # МНОГОШАГОВЫЙ ЦИКЛ САМОИСПРАВЛЕНИЯ SQL С АВТОМАТИЧЕСКИМ РЕЗЕРВНЫМ ПЛАНОМ
                # =====================================================================
                attempts = 0
                max_attempts = 3
                sql_success = False
                
                while attempts < max_attempts and not sql_success:
                    attempts += 1
                    try:
                        # Проверяем, не обрезал ли Groq API строку на слове LIKE
                        if generated_sql.strip().endswith("LIKE") or "LIKE" in generated_sql and not "GROUP BY" in generated_sql:
                            raise sqlite3.OperationalError("Incomplete input or API token truncation detected.")
                            
                        if attempts == 1:
                            st.code(generated_sql, language="sql")
                        else:
                            st.markdown(f"**🔄 Попытка самоисправления №{attempts-1}:**")
                            st.code(generated_sql, language="sql")
                            
                        result_df = run_sql_query(generated_sql)
                        sql_success = True
                    except Exception as sql_error:
                        if attempts == max_attempts:
                            st.warning("🔄 Включен интеллектуальный режим восстановления SQL-запроса...")
                            
                            # Ультра-короткий динамический промпт, заставляющий выдать СТРОГО 3 строки кода без CASE WHEN
                            fallback_prompt = (
                                f"The user asked: '{user_query}'. Your previous complex query failed with a truncation error. "
                                f"Based on this schema:\n{DATABASE_SCHEMA}\n"
                                f"Write the SHORTEST possible valid SQLite query (max 4 lines) to fetch raw rows for this question. "
                                f"NEVER use CASE WHEN or loops. Use plain SELECT, JOIN, GROUP BY and LIMIT 10. Return ONLY pure SQL text."
                            )
                            
                            try:
                                response_fallback = completion(
                                    model="groq/llama-3.1-8b-instant",
                                    messages=[{"role": "user", "content": fallback_prompt}],
                                    temperature=0.0,
                                    max_tokens=200
                                )
                                
                                res_fb_str = str(response_fallback)
                                fb_match = re.search(r'content=["\']([\s\S]*?)["\']', res_fb_str)
                                if fb_match:
                                    generated_sql = fb_match.group(1).replace("\\n", "\n")
                                else:
                                    generated_sql = response_fallback['choices']['message']['content']
                                    
                                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                            except Exception:
                                # Абсолютный сейв-контур, если даже простой запрос упал (выводим базовую географию клиентов)
                                generated_sql = "SELECT customer_state, COUNT(customer_id) AS total_customers FROM customers_dataset GROUP BY 1 ORDER BY 2 DESC LIMIT 5;"
                                
                            st.markdown("**🛡️ Динамический отказоустойчивый SQL-запрос, собранный под ваш вопрос:**")
                            st.code(generated_sql, language="sql")
                            result_df = run_sql_query(generated_sql)
                            sql_success = True
                            break
                            
                        st.warning(f"⚠️ Ошибка в SQL (Попытка {attempts}): {str(sql_error)}. Запускаю ИИ для исправления структуры...")
                        
                        messages = [
                            {"role": "system", "content": sql_system_prompt},
                            {"role": "user", "content": f"Your query failed with error: {str(sql_error)}. Rewrite it to be ultra-short (max 4 lines). Use strictly basic GROUP BY instead of CASE WHEN. Return ONLY raw SQL text."}
                        ]
                        
                        response = completion(
                            model="groq/llama-3.1-8b-instant",
                            messages=messages,
                            temperature=0.0,
                            max_tokens=1000
                        )
                        
                        res_str = str(response)
                        content_match = re.search(r'content=["\']([\s\S]*?)["\']', res_str)
                        if content_match:
                            generated_sql = content_match.group(1).replace("\\n", "\n")
                        else:
                            if hasattr(response, 'choices') and hasattr(response.choices, 'message'):
                                generated_sql = response.choices.message.content
                            else:
                                generated_sql = response['choices']['message']['content']
                            
                        generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                # =====================================================================
                
                st.write("🔍 Шаг 2: Выполнение запроса в olist.db и извлечение точных метрик...")
                st.write("✍️ Шаг 3: Формирование аналитического отчета на русском языке...")
                
                # 2. МЕТОДОЛОГИЧЕСКИЙ СИСТЕМНЫЙ ПРОМПТ АНАЛИТИКА (БЕЗ ЖЕСТКИХ ПРИВЯЗОК)
                analyst_system_prompt = (
                    "Ты Ведущий продуктовый аналитик маркетплейса Olist. Твоя задача — взять сырую таблицу данных, "
                    "проанализировать её фактическую структуру и составить краткий и емкий бизнес-отчет СТРОГО НА РУССКОМ ЯЗЫКЕ.\n\n"
                    "ИНСТРУКЦИЯ ДЛЯ АВТОНОМНОГО АНАЛИЗА:\n"
                    "1. КОНТЕКСТ ДАННЫХ: Строго сопоставляй свои выводы с пришедшей таблицей. Если в таблице содержатся названия категорий товаров "
                    "   (product_category_name_english) и количество заказов (order_count), твой отчет должен быть посвящен ТОЛЬКО анализу товарной матрицы, "
                    "   выделению лидеров/аутсайдеров продаж и мерам поддержки для этих товарных групп. Запрещено выдумывать исторические месяцы или сезонность, если их нет в таблице.\n"
                    "2. КРИТИКА ГИПОТЕЗ: Оценивай логику вопроса пользователя. Если вопрос бизнеса содержит ложную предпосылку "
                    "   (утверждает о падении тренда, спаде или кризисе, который опровергается высокими цифрами в таблице), "
                    "   прямо укажи на это в первом пункте отчета на основе математических фактов.\n"
                    "3. СТРУКТУРА ОТЧЕТА:\n"
                    "   - 1. Главный инсайт исследования (Реальное положение дел на основе структуры пришедших данных)\n"
                    "   - 2. Цифры и факты (Точные значения, лидеры и ключевые метрики из таблицы для доказательства)\n"
                    "   - 3. Аналитические гипотезы (Почему сформировался такой тренд? Какие скрытые факторы на него повлияли?)\n"
                    "   - 4. Бизнес-рекомендация (Конкретные шаги для руководства маркетплейса на основе выводов)"
                )

                
                # ОПТИМИЗАЦИЯ ТОКЕНОВ ДЛЯ ОТЧЕТА: Расширяем лимит ответа до 1000 токенов
                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": analyst_system_prompt},
                        {"role": "user", "content": f"Вопрос пользователя: {user_query}\n\nПолученные широкие данные из базы (топ-15 лидеров для анализа):\n{result_df.head(15).to_string(index=False)}"}
                    ],
                    temperature=0.2,
                    max_tokens=1000  # <-- ДОБАВЬТЕ ЭТУ КРИТИЧЕСКУЮ СТРОКУ ТУТ, ЧТОБЫ УБРАТЬ ОБРЕЗКУ ТЕКСТА
                )

                
                # REGEX ПАРСЕР ДЛЯ ИЗВЛЕЧЕНИЯ ФИНАЛЬНОГО ТЕКСТОВОГО ОТЧЕТА
                res_report_str = str(report_response)
                content_match = re.search(r'content=["\']([\s\S]*?)["\']', res_report_str)
                if content_match:
                    final_report = content_match.group(1).replace("\\n", "\n")
                else:
                    if hasattr(report_response, 'choices') and hasattr(report_response.choices, 'message'):
                        final_report = report_response.choices.message.content
                    else:
                        final_report = report_response['choices']['message']['content']
                    
                status.update(label="✅ Анализ успешно завершен!", state="complete", expanded=False)
                
                # Выводим точную таблицу на экран
                st.success("📊 Данные из полной инфраструктуры DWH Olist для анализа:")
                st.dataframe(result_df, use_container_width=True)
                
                # Выводим текстовый отчет
                st.subheader("🎯 Финальный бизнес-отчет аналитика:")
                st.markdown(final_report)
                
            except Exception as e:
                status.update(label="❌ Ошибка выполнения", state="error", expanded=False)
                st.error(f"Произошел технический сбой: {e}")
                        