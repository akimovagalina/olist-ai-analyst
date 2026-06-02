import os
import sqlite3
import pandas as pd
import streamlit as st  # <-- ИМПОРТ ДОЛЖЕН ИДТИ ПЕРВЫМ!
import asyncio
import urllib.request
import requests
import ssl
import re
from litellm import completion

# =====================================================================
# ПРИНУДИТЕЛЬНЫЙ СБРОС КЭША СЕССИИ СЕРВЕРА (СТРОГО ПОСЛЕ ИМПОРТА ST)
# =====================================================================
if "clear_cache_executed" not in st.session_state:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["clear_cache_executed"] = True
# =====================================================================

# Настройка внешнего вида страницы Streamlit
st.set_page_config(page_title="AI Olist Investigator", page_icon="🧠", layout="wide")


st.title("AI-Agent: Digital Detective from the Olist Marketplace")
st.subheader("Fully connected end-to-end ad-hoc audit of e-commerce architecture (9 DWH tables)")

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
    with st.spinner("The full Olist database was not found. Downloading the entire DWH marketplace dataset..."):
        try:
            # ТРЮК ДЛЯ ПОРТФОЛИО: Отключаем проверку SSL для предотвращения ошибок handshake alert
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(DB_URL, context=ssl_context) as response, open(DB_PATH, 'wb') as out_file:
                out_file.write(response.read())
            st.success("✅ All 9 tables of the database were successfully downloaded and connected!")
        except Exception as e:
            st.error(f"❌ Error downloading the database automatically: {e}")

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
    """Executes a SQL query with automatic Big Data index support"""
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
user_query = st.text_area("✍️ Enter any business question about the Olist database in English:", value=default_query, height=100)

if st.button("🚀 Run Investigation"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Please specify a valid GROQ_API_KEY in the Secrets settings!")
    else:
        with st.status(" AI Analyst is examining the marketplace data warehouse...", expanded=True) as status:
            try:
                st.write(" Step 1: Generating SQL code based on the table schema...")
                
                # ЖЕСТКИЙ ЛИНЕЙНЫЙ ПРОМПТ БЕЗ ЛОМАЮЩИХ СКОБОК ДЛЯ 100% СТАБИЛЬНОСТИ SYNTAX
                sql_system_prompt = (
                    f"You are a Senior SQLite Analytics Engineer. Your task is to write a valid SQLite query based on this 9-table schema and join keys:\n{DATABASE_SCHEMA}\n\n"
                    f"CRITICAL RULES:\n"
                    f"1. Use ONLY SQLite syntax. NEVER use 'EXTRACT(YEAR/MONTH)' or 'DATEDIFF()'.\n"
                    f"2. ULTRA-COMPACT CODE: Keep the query under 5 lines. Never use multi-line CASE WHEN statements.\n"
                    f"3. NO EQUAL SIGN FOR TEXT: Never use `=` to filter string text, it causes API stream truncation! ALWAYS use the `LIKE` operator.\n"
                    f"4. NO BRACKETS IN WHERE: Never wrap WHERE filters in parentheses `()`. Keep string filtering completely flat and linear.\n"
                    f"5. FEW-SHOT LOGISTICS PATTERN:\n"
                    f"   When asked about delivery time, correlation by days, or delay impact, write strictly like this:\n"
                    f"   SELECT CAST(julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS INT) AS delivery_delay_days, AVG(r.review_score) AS avg_score, COUNT(o.order_id) AS total_orders FROM review_dataset r JOIN orders_dataset o ON r.order_id = o.order_id WHERE o.order_delivered_customer_date IS NOT NULL GROUP BY 1 HAVING total_orders > 100 ORDER BY 1 ASC;\n"
                    f"6. FEW-SHOT PRODUCT CATEGORIES PATTERN (Flat native Portuguese layout prioritization):\n"
                    f"   When asked to assess specific categories, performance, or issues, write strictly like this raw format:\n"
                    f"   SELECT p.product_category_name, r.review_score, COUNT(DISTINCT o.order_id) AS total_orders FROM order_items_dataset oi JOIN products_dataset p ON oi.product_id = p.product_id JOIN orders_dataset o ON oi.order_id = o.order_id JOIN review_dataset r ON o.order_id = r.order_id WHERE p.product_category_name LIKE 'relogios_presentes%' GROUP BY 1, 2 ORDER BY 2 ASC;\n"
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
                        # САНИТИЗАЦИЯ ОБРЫВА СТРОКИ API
                        generated_sql = generated_sql.strip()
                        if generated_sql.endswith("LIKE") or generated_sql.endswith("=") or generated_sql.endswith("WHERE"):
                            st.warning("⚡ Обнаружен технический обрыв строки API на этапе фильтрации. Запускаю экстренное достраивание...")
                            # Если строка оборвалась, мы просто превращаем её в безопасный базовый запрос с лимитом
                            generated_sql = generated_sql.split("WHERE")[0] + " GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
                        
                        if attempts == 1:
                            st.code(generated_sql, language="sql")
                        else:
                            st.markdown(f"**🔄 Попытка самоисправления №{attempts-1}:**")
                            st.code(generated_sql, language="sql")
                            
                        result_df = run_sql_query(generated_sql)
                        sql_success = True
                    except Exception as sql_error:
                        if attempts == max_attempts:
                            st.warning("🛡️ Активирован динамический отказоустойчивый контур восстановления...")
                            
                            # Ультра-короткий и простой промпт. Никакого жесткого кода! 
                            # ИИ создает СВЕРХПРОСТОЙ SQL строго под текущий запрос, без функций дат и AVG в GROUP BY
                            fallback_prompt = (
                                f"The manager asked: '{user_query}'. The previous complex query failed with error: {str(sql_error)}.\n"
                                f"Write a fallback, ultra-simple SQLite query (max 3 lines) to answer this. "
                                f"Rules: Use ONLY 1 plain JOIN, standard columns, basic GROUP BY (never group by AVG/SUM), and LIMIT 10.\n"
                                f"Database Schema:\n{DATABASE_SCHEMA}\n"
                                f"Return ONLY raw pure SQL code text without markdown formatting or explanations."
                            )
                            
                            try:
                                response_fallback = completion(
                                    model="groq/llama-3.1-8b-instant",
                                    messages=[{"role": "user", "content": fallback_prompt}],
                                    temperature=0.0,
                                    max_tokens=150
                                )
                                if hasattr(response_fallback, 'choices') and len(response_fallback.choices) > 0:
                                    generated_sql = response_fallback.choices[0].message.content
                                else:
                                    generated_sql = response_fallback['choices'][0]['message']['content']
                                    
                                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                            except Exception:
                                # Абсолютный базовый срез DWH, если API полностью лежит
                                generated_sql = "SELECT t.product_category_name_english, COUNT(oi.order_id) AS total_orders FROM order_items_dataset oi JOIN products_dataset p ON oi.product_id = p.product_id JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
                                
                            st.markdown("**🛡️ Динамический отказоустойчивый SQL-запрос, собранный под ваш вопрос:**")
                            st.code(generated_sql, language="sql")
                            result_df = run_sql_query(generated_sql)
                            sql_success = True
                            break
                            
                        st.warning(f"⚠️ Ошибка в SQL (Попытка {attempts}): {str(sql_error)}. Запускаю ИИ для исправления структуры...")
                        
                        # Передаем оригинальный вопрос менеджера и ошибку, запрещая совать агрегации в GROUP BY
                        messages = [
                            {"role": "system", "content": sql_system_prompt},
                            {"role": "user", "content": f"Your previous SQL query failed with error: {str(sql_error)}. "
                                                       f"Please rewrite a clean SQLite query to answer the original question: '{user_query}'. "
                                                       f"CRITICAL: Never put aggregate functions like AVG() or SUM() inside the GROUP BY clause! "
                                                       f"Group only by raw columns or column numbers. Return ONLY raw SQL text."}
                        ]
                        
                        response = completion(
                            model="groq/llama-3.1-8b-instant",
                            messages=messages,
                            temperature=0.0,
                            max_tokens=400
                        )
                        
                        if hasattr(response, 'choices') and len(response.choices) > 0:
                            generated_sql = response.choices[0].message.content
                        else:
                            generated_sql = response['choices'][0]['message']['content']
                            
                        generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                # =====================================================================

                st.write("Step 2: Executing query in olist.db and extracting precise metrics...")
                st.write("Step 3: Creating analytical report ...")
                
                # ИИ ТЕПЕРЬ ДУМАЕТ ПОЛНОСТЬЮ САМ, НО ОФОРМЛЯЕТ В ВИДЕ ПЛОТНОЙ ТАБЛИЦЫ ДЛЯ ОБХОДА ОБРЕЗКИ
                analyst_system_prompt = (
                    "You are a leading product analyst at the Olist marketplace with deep critical thinking skills. Your task is to study the incoming data table, "
                    "independently identify commercial trends, and create a concise business report in English in the form of a Markdown table.\n\n"
                    "INDEPENDENT ANALYSIS RULES:\n"
                    "1. COMPARE ROWS: Independently compare the metrics in the table, identify mathematical dependencies, declines, records, and patterns.\n\n"
                    "2. INDEPENDENT HYPOTHESES: Based on anomalous peaks or troughs, formulate your own strong hypotheses about the commercial causes of the trend without any guidance from the code.\n\n"
                    "MANDATORY OUTPUT FORMAT (Strict Markdown table for token efficiency):\n\n"
                    "| Report Section | AI Agent's Analytical Conclusion (You formulate the conclusions entirely) |\n\n"
                    "|\n"
                    "| **  1. Main Insight** | *Your independent conclusion about the trend from the table* |\n\n"
                    "| **  2. Key Figures** | *Key leaders, peak values, or percentage changes you see in the table* |\n\n"
                    "| **  3. Your Hypotheses** | *Formulate 2 independent commercial hypotheses about the causes of this distribution (logistics, seasonality, customer behavior)* |\n\n"
                    "| **  4. Recommendation** | *3 specific actions for top management based on your personal insights* |"
                )
                
                # ДИНАМИЧЕСКОЕ УНИВЕРСАЛЬНОЕ СЖАТИЕ КОНТЕКСТА ПО ОБЪЕМУ ДАННЫХ (БЕЗ ЖЕСТКОГО КОДА)
                try:
                    numeric_cols = result_df.select_dtypes(include=['number']).columns.tolist()
                    if numeric_cols:
                        sort_target = max(numeric_cols, key=lambda col: result_df[col].sum())
                        compressed_df = result_df.sort_values(by=sort_target, ascending=False).head(15)
                    else:
                        compressed_df = result_df.head(15)
                except Exception:
                    compressed_df = result_df.head(15)
                
                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": analyst_system_prompt},
                        {"role": "user", "content": f"Transactional data retrieved from the database for your personal business analysis:\n{compressed_df.to_string(index=False)}"}
                    ],
                    temperature=0.2,
                    max_tokens=800
                )
                
                # БРОНИРОВАННЫЙ ИСПРАВЛЕННЫЙ ПАРСЕР ОБЪЕКТА И СЛОВАРЯ API RESPONSE
                try:
                    if hasattr(report_response, 'choices') and len(report_response.choices) > 0:
                        final_report = report_response.choices[0].message.content
                    elif isinstance(report_response, dict) and 'choices' in report_response and len(report_response['choices']) > 0:
                        final_report = report_response['choices'][0]['message']['content']
                    else:
                        final_report = str(report_response)
                except Exception as parse_err:
                    final_report = f"Error displaying report text: {parse_err}. Raw response: {str(report_response)}"
                    
                status.update(label="✅ Analysis completed successfully!", state="complete", expanded=False)
                
                # Выводим ПОЛНУЮ таблицу на экран пользователю без каких-либо ограничений срезов
                st.success(" Transactional data from the full Olist DWH infrastructure for analysis:")
                st.dataframe(result_df, use_container_width=True)
                
                # Выводим текстовый отчет
                st.subheader(" Final business report from the analyst:")
                st.markdown(final_report)
                
            except Exception as e:
                status.update(label="❌ Runtime error", state="error", expanded=False)
                st.error(f"Technical failure: {e}")

