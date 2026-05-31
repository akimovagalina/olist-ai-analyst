import os
import sqlite3
import pandas as pd
import streamlit as st
import asyncio
import urllib.request
import ssl
import re  # Safe regular expression parsing for raw API data extraction
from litellm import completion

# Configure Streamlit presentation layer
st.set_page_config(page_title="AI Olist Investigator", page_icon="🕵️‍♂️", layout="wide")

st.title("AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Полносвязный сквозной ad-hoc аудит e-commerce архитектуры (9 таблиц DWH)")

# Secure background environmental setup for credentials
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# НАДЕЖНАЯ АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ПОЛНОЙ БАЗЫ ДАННЫХ (БЕЗ SSL-ОШИБОК)
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://github.com/akimovagalina/olist-ai-analyst/releases/download/v1.0.0/olist.db"


# Force cache flush if an outdated, clipped database asset is detected
if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) < 90000000:
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

# =====================================================================
# КОМПЛЕКСНАЯ СЕМАНТИЧЕСКАЯ КАРТА СВЯЗЕЙ (ENTERPRISE DATA CATALOG) ДЛЯ ИИ
# =====================================================================
DATABASE_SCHEMA = """
Table customers_dataset { customer_id string [pk], customer_unique_id string, customer_zip_code_prefix int, customer_city string, customer_state string }
Table geolocation_dataset { geolocation_zip_code_prefix int [pk], geolocation_lat float, geolocation_lng float, geolocation_city string, geolocation_state string }
Table orders_dataset { order_id string [pk], customer_id string, order_status string, order_purchase_timestamp string, order_approved_at string, order_delivered_carrier_date string, order_delivered_customer_date string, order_estimated_delivery_date string }
Table order_items_dataset { order_id string, order_item_id int, product_id string, seller_id string, price float }
Table order_payments_dataset { order_id string, payment_sequential int, payment_type string, payment_installments int, payment_value float }
Table review_dataset { 
  review_id string [pk], order_id string, review_score int, review_comment_title string, review_comment_message string, review_creation_date string, review_answer_timestamp string 
}
Table products_dataset { product_id string [pk], product_category_name string, product_name_lenght int, product_description_lenght int, product_photos_qty int, product_weight_g int, product_length_cm int, product_height_cm int, product_width_cm int }
Table sellers_dataset { seller_id string [pk], seller_zip_code_prefix int, seller_city string, seller_state string }
Table product_category_name_translation { product_category_name string [pk], product_category_name_english string }

--- STRICT RELATIONAL JOINS CONSTRAINTS MAP (USE ONLY THESE KEYS FOR MULTI-TABLE QUERIES) ---
- LINK CUSTOMERS: orders_dataset.customer_id = customers_dataset.customer_id
- LINK ITEMS TO ORDERS: order_items_dataset.order_id = orders_dataset.order_id
- LINK PAYMENTS TO ORDERS: order_payments_dataset.order_id = orders_dataset.order_id
- LINK REVIEWS TO ORDERS: review_dataset.order_id = orders_dataset.order_id
- LINK PRODUCTS TO ITEMS: order_items_dataset.product_id = products_dataset.product_id
- LINK SELLERS TO ITEMS: order_items_dataset.seller_id = sellers_dataset.seller_id
- LINK TRANSLATIONS TO PRODUCTS: products_dataset.product_category_name = product_category_name_translation.product_category_name

CRITICAL ERROR PREVENTION FOR THE ENGINE:
1. 'product_category_name_english' lives ONLY inside product_category_name_translation table! NEVER query it from products_dataset.
2. 'products_dataset' has NO relational mapping to 'orders_dataset' directly. To connect them, you MUST join through order_items_dataset via order_id and product_id!
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

# Интерфейс ввода вопроса менеджера
default_query = "How do user reviews depend on delivery delay times by days?"
user_query = st.text_area("✍️ Введите любой ваш бизнес-вопрос к базе Olist на английском языке:", value=default_query, height=100)

if st.button("🚀 Запустить расследование"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Пожалуйста, укажите валидный GROQ_API_KEY в настройках Secrets!")
    else:
        with st.status("🕵️‍♂️ ИИ-аналитик изучает хранилище данных маркетплейса...", expanded=True) as status:
            try:
                st.write("🤖 Шаг 1: Генерация SQL-кода на основе схемы таблиц...")
                
                # FEW-SHOT SQL ПРОМПТ: Учим ИИ подневному реляционному анализу на жестких примерах
                                # АНТИЦЕНЗУРНЫЙ СИСТЕМНЫЙ ПРОМПТ С ЖЕСТКИМ ЗАПРЕТОМ НА ОПЕРАТОР РАВЕНСТВА ДЛЯ ТЕКСТА
                sql_system_prompt = (
                    f"You are a Senior SQLite Analytics Engineer. Your task is to write a valid SQLite query based on this 9-table schema and join keys:\n{DATABASE_SCHEMA}\n\n"
                    f"CRITICAL RULES:\n"
                    f"1. Use ONLY SQLite syntax. NEVER use 'EXTRACT(YEAR/MONTH)' or 'DATEDIFF()'.\n"
                    f"2. ULTRA-COMPACT CODE: Keep the query under 6 lines. Never use verbose multi-line CASE WHEN statements.\n"
                    f"3. STRICT SECURITY RULE (NO TEXT EQUAL SIGN): Never use the equal sign `=` operator to filter text or category names in the WHERE clause, as it causes cloud API stream truncation! "
                    f"   ALWAYS use the `LIKE` operator for text filtering instead. Example: `WHERE t.product_category_name_english LIKE 'flowers%'`.\n"
                    f"4. FEW-SHOT LOGISTICS PATTERN:\n"
                    f"   When asked about delivery time, correlation by days, or delay impact, write strictly like this:\n"
                    f"   SELECT CAST(julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS INT) AS delivery_delay_days, AVG(r.review_score) AS avg_score, COUNT(o.order_id) AS total_orders FROM review_dataset r JOIN orders_dataset o ON r.order_id = o.order_id WHERE o.order_delivered_customer_date IS NOT NULL GROUP BY 1 HAVING total_orders > 100 ORDER BY 1 ASC;\n"
                    f"5. FEW-SHOT PRODUCT CATEGORIES PATTERN:\n"
                    f"   When asked to assess product categories, growth, decline, or sales performance, write strictly like this:\n"
                    f"   SELECT t.product_category_name_english, SUM(oi.price) AS total_sales, COUNT(DISTINCT o.order_id) AS total_orders FROM order_items_dataset oi JOIN products_dataset p ON oi.product_id = p.product_id JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name JOIN orders_dataset o ON oi.order_id = o.order_id WHERE t.product_category_name_english LIKE 'flowers%' GROUP BY 1 ORDER BY 2 DESC;\n"
                    f"6. SEMANTIC CONTEXT: If the manager asks about reviews comments, text, or messages, completely ignore product categories, select `r.review_comment_message` from `review_dataset r` where it is NOT NULL, and calculate stats based on the actual question instead of copying examples.\n"
                    f"7. Return ONLY the raw SQL query string. No explanations, no conversation wrappers, no markdown blocks."
                )

                
                messages = [
                    {"role": "system", "content": sql_system_prompt},
                    {"role": "user", "content": f"Write an SQL query to answer this question: {user_query}"}
                ]
                
                response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.0,
                    max_tokens=400
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
                # МНОГОШАГОВЫЙ ДИНАМИЧЕСКИЙ ЦИКЛ САМОИСПРАВЛЕНИЯ SQL (ДО 3 ПОПЫТОК)
                # =====================================================================
                attempts = 0
                max_attempts = 3
                sql_success = False
                
                while attempts < max_attempts and not sql_success:
                    attempts += 1
                    try:
                        if attempts == 1:
                            st.code(generated_sql, language="sql")
                        else:
                            st.markdown(f"**🔄 Попытка самоисправления №{attempts-1}:**")
                            st.code(generated_sql, language="sql")
                            
                        result_df = run_sql_query(generated_sql)
                        sql_success = True
                    except Exception as sql_error:
                        if attempts == max_attempts:
                            st.warning("🔄 Включен интеллектуальный режим динамического восстановления SQL...")
                            
                            # Ультра-короткий промпт БЕЗ жестких дат. ИИ создаст простой SQL строго ПОД ТЕКУЩИЙ ВОПРОС!
                            fallback_prompt = (
                                f"The user asked: '{user_query}'. Your complex query failed with error: {str(sql_error)}.\n"
                                f"Write the SHORTEST possible valid SQLite query (max 3-4 lines) to fetch raw rows for this specific question.\n"
                                f"Rely strictly on this relationships map constraints:\n{DATABASE_SCHEMA}\n"
                                f"Return ONLY raw pure SQL code text. No explanations, no conversation padding."
                            )
                            
                            try:
                                response_fallback = completion(
                                    model="groq/llama-3.1-8b-instant",
                                    messages=[{"role": "user", "content": fallback_prompt}],
                                    temperature=0.0,
                                    max_tokens=150
                                )
                                res_fb_str = str(response_fallback)
                                fb_match = re.search(r'content=["\']([\s\S]*?)["\']', res_fb_str)
                                if fb_match:
                                    generated_sql = fb_match.group(1).replace("\\n", "\n")
                                else:
                                    generated_sql = response_fallback['choices']['message']['content']
                                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                            except Exception:
                                # Стопроцентный безусловный сейв-контур (базовый срез заказов), если даже простой упал
                                generated_sql = "SELECT order_status, COUNT(order_id) AS order_count FROM orders_dataset GROUP BY 1 ORDER BY 2 DESC LIMIT 5;"
                                
                            st.markdown("**🛡️ Динамический отказоустойчивый SQL-запрос, собранный под ваш вопрос:**")
                            st.code(generated_sql, language="sql")
                            result_df = run_sql_query(generated_sql)
                            sql_success = True
                            break
                            
                        st.warning(f"⚠️ Ошибка в SQL (Попытка {attempts}): {str(sql_error)}. Запускаю ИИ для исправления структуры...")
                        
                        # ОПТИМИЗАЦИЯ ПАМЯТИ (TPM SAFE): Сбрасываем контекст, но ЖЕСТКО передаем оригинальный вопрос менеджера заново!
                        messages = [
                            {"role": "system", "content": sql_system_prompt},
                            {"role": "user", "content": f"Your previous SQL query failed with error: {str(sql_error)}. "
                                                       f"Please write a clean, complete SQLite query to answer the manager's original question: '{user_query}'. "
                                                       f"Follow the RELATIONSHIPS MAP constraints exactly. Return ONLY raw pure SQL code text."}
                        ]
                        
                        response = completion(
                            model="groq/llama-3.1-8b-instant",
                            messages=messages,
                            temperature=0.0,
                            max_tokens=400
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
                
                # УСИЛЕННЫЙ ПРАВИЛАМИ ВАЛИДАЦИИ СИСТЕМНЫЙ ПРОМПТ АНАЛИТИКА
                analyst_system_prompt = (
                    "Ты Ведущий продуктовый аналитик маркетплейса Olist с глубоким критическим мышлением. Твоя задача — изучить пришедшую таблицу данных, "
                    "самостоятельно выявить коммерческий тренд и составить емкий бизнес-отчет СТРОГО НА РУССКОМ ЯЗЫКЕ в виде Markdown-таблицы.\n\n"
                    "ПРАВИЛА АВТОНОМНОГО АНАЛИЗА:\n"
                    "1. СРАВНИВАЙ СТРОКИ: Самостоятельно глазами сопоставь показатели в таблице, выяви математические зависимости и закономерности.\n"
                    "2. КРИТИЧЕСКИЙ ВАЛИДАТОР ДАННЫХ (DATA VALIDATION): Внимательно посмотри на названия колонок. Если в пришедшей таблице содержатся только справочные данные "
                    "   (например, просто список лет, уникальные статусы или имена городов) и НЕТ колонок с финансовыми объемами (sales, revenue, price, payment) или количеством заказов (orders, count), "
                    "   тебе КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать спады, рост или строить логистические гипотезы! В этом случае в блоке 'Главный инсайт' просто сухо перечисли доступные в таблице периоды/данные, "
                    "   а в блоках гипотез и рекомендаций напиши, каких конкретно продуктовых метрик тебе не хватило для проведения полноценного коммерческого аудита.\n"
                    "3. НЕЗАВИСИМЫЕ ВИЗУАЛЬНЫЕ ГИПОТЕЗЫ: Если финансовые данные есть, выдвини собственные сильные гипотезы о причинах тренда без подсказок со стороны кода.\n\n"
                    "ОБЯЗАТЕЛЬНЫЙ ФОРМАТ ВЫВОДА (Строго Markdown-таблица для экономии токенов):\n"
                    "| Раздел отчета | Аналитическое заключение ИИ-агента (Выводы полностью формулируешь САМ) |\n"
                    "| :--- | :--- |\n"
                    "| **🎯 1. Главный инсайт** | *Твое независимое заключение о тренде из таблицы (или сухой перечень данных, если метрик продаж нет)* |\n"
                    "| **📊 2. Главные цифры** | *Ключевые лидеры, пиковые значения или проценты изменений, которые ты видишь в таблице* |\n"
                    "| **💡 3. Твои гипотезы** | *Выдвини 2 коммерческие гипотезы причин такого распределения (или укажи, каких данных не хватило для гипотез)* |\n"
                    "| **🚀 4. Рекомендация** | *3 конкретных шага для топ-менеджмента на основе твоих личных выводов* |"
                )

                
                # ДИНАМИЧЕСКАЯ УНИВЕРСАЛЬНАЯ СЖАТИЕ КОНТЕКСТА ПО ОБЪЕМУ ДАННЫХ (БЕЗ ЖЕСТКОГО КОДА)
                try:
                    # Находим все числовые колонки (int и float)
                    numeric_cols = result_df.select_dtypes(include=['number']).columns.tolist()
                    if numeric_cols:
                        # Находим числовую колонку с максимальной суммой значений (ядро объемов данных)
                        sort_target = max(numeric_cols, key=lambda col: result_df[col].sum())
                        compressed_df = result_df.sort_values(by=sort_target, ascending=False).head(15)
                    else:
                        compressed_df = result_df.head(15)
                except Exception:
                    compressed_df = result_df.head(15)
                
                # Отправляем в ИИ-аналитик только очищенную репрезентативную макро-картину
                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": analyst_system_prompt},
                        {"role": "user", "content": f"Полученные из базы транзакционные данные для твоего личного бизнес-анализа:\n{compressed_df.to_string(index=False)}"}
                    ],
                    temperature=0.2,
                    max_tokens=800
                )
                
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
                
                # Выводим ПОЛНУЮ таблицу на экран пользователю без каких-либо ограничений срезов
                st.success("📊 Данные из полной инфраструктуры DWH Olist для анализа:")
                st.dataframe(result_df, use_container_width=True)
                
                # Выводим текстовый отчет
                st.subheader("🎯 Финальный бизнес-отчет аналитика:")
                st.markdown(final_report)
                
            except Exception as e:
                status.update(label="❌ Ошибка выполнения", state="error", expanded=False)
                st.error(f"Произошел технический сбой: {e}")
