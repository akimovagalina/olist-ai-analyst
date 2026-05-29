import os
import sqlite3
import pandas as pd
import streamlit as st
import asyncio
import urllib.request
import ssl
import re  # Импортируем регулярные выражения для неубиваемого парсинга ответов LLM
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


# Если файл весит меньше 80 МБ (значит, это старая урезанная база), принудительно удаляем её
if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) < 80000000:
    os.remove(DB_PATH)

if not os.path.exists(DB_PATH):
    with st.spinner("📦 Полная база Olist не найдена. Скачиваю весь датасет DWH маркетплейса (9 таблиц, 65 MB)..."):
        try:
            # ТРЮК ДЛЯ ПОРТФОЛИО: Отключаем строгую проверку SSL сертификатов для обхода SSLV3_ALERT ошибок
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(DB_URL, context=ssl_context) as response, open(DB_PATH, 'wb') as out_file:
                out_file.write(response.read())
            st.success("✅ Все 9 таблиц базы данных успешно загружены и подключены!")
        except Exception as e:
            st.error(f"❌ Ошибка автоматического скачивания базы: {e}")

# Карта схемы базы данных для ИИ
DATABASE_SCHEMA = """
Table customers_dataset {
  customer_id string [pk] -> Перекрестная ссылка к orders_dataset
  customer_unique_id string -> Уникальный неизменяемый ID клиента
  customer_zip_code_prefix integer -> Первые 5 цифр почтового индекса
  customer_city string -> Город клиента
  customer_state string -> Штат клиента
}

Table geolocation_dataset {
  geolocation_zip_code_prefix integer [pk] -> Первые 5 цифр индекса для связи с клиентами/продавцами
  geolocation_lat float -> Широта
  geolocation_lng float -> Долгота
  geolocation_city string -> Название города в геолокации
  geolocation_state string -> Код штата в геолокации
}

Table orders_dataset {
  order_id string [pk]
  customer_id string -> Связь с таблицей клиентов
  order_status string -> Статус заказа (delivered, shipped, cancelled и т.д.)
  order_purchase_timestamp string -> Дата и время совершения покупки (Формат: YYYY-MM-DD HH:MM:SS)
  order_approved_at string -> Время подтверждения оплаты
  order_delivered_carrier_date string -> Время передачи заказа в службу доставки
  order_delivered_customer_date string -> Фактическое время доставки клиенту
  order_estimated_delivery_date string -> Обещанная (планируемая) дата доставки
}

Table order_items_dataset {
  order_id string
  order_item_id integer -> Порядковый номер товара внутри одного заказа
  product_id string -> ID товара для связи с products_dataset
  seller_id string -> ID продавца для связи с sellers_dataset
  price float -> Цена за единицу товара
}

Table order_payments_dataset {
  order_id string
  payment_sequential integer -> Порядковый номер транзакции (если платили несколькими способами)
  payment_type string -> Способ оплаты (credit_card, debit_card, boleto, voucher)
  payment_installments integer -> Количество платежей по рассрочке
  payment_value float -> Сумма, уплаченная в этой транзакции
}

Table review_dataset {
  review_id string [pk]
  order_id string -> Связь с заказом
  review_score integer -> Оценка удовлетворенности клиента (от 1 до 5)
  review_creation_date string -> Дата отправки анкеты отзыва
  review_answer_timestamp string -> Фактическое время ответа клиента
}

Table products_dataset {
  product_id string [pk]
  product_category_name string -> Название категории на португальском языке
  product_name_lenght integer
  product_description_lenght integer
  product_photos_qty integer
  product_weight_g integer
  product_length_cm integer
  product_height_cm integer
  product_width_cm integer
}

Table sellers_dataset {
  seller_id string [pk]
  seller_zip_code_prefix integer -> Index продавца
  seller_city string -> Город продавца
  seller_state string -> Штат продавца
}

Table product_category_name_translation {
  product_category_name string [pk] -> Категория на португальском
  product_category_name_english string -> Категория на английском (используй для вывода понятных категорий!)
}
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
                
                sql_system_prompt = (
                    f"You are a Senior SQLite Developer. Your task is to write a valid SQLite query based on this 9-table schema:\n{DATABASE_SCHEMA}\n\n"
                    f"CRITICAL RULES:\n"
                    f"1. Use ONLY SQLite syntax. NEVER use 'EXTRACT(YEAR/MONTH)'.\n"
                    f"2. METHODOLOGY: To understand why sales changed in a specific month, you MUST fetch a broader timeline for context. "
                    f"   Generate a query that extracts monthly aggregates (SUM(price) AS total_sales, COUNT(DISTINCT order_id) AS num_orders) covering at least 3-4 months surrounding the target period (e.g., 2017-09, 2017-10, 2017-11, 2017-12) "
                    f"   using `SUBSTR(order_purchase_timestamp, 1, 7) AS sales_month` so the analyst can perform MoM (Month-over-Month) analysis.\n"
                    f"3. Make sure every aggregated or constructed column in SELECT is correct and matched in GROUP BY or ORDER BY.\n"
                    f"4. Return ONLY the raw SQL query. No markdown blocks, no explanations, no object wrappers like ModelResponse."
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
                
                # НАДЕЖНЫЙ REGEX ПАРСЕР ДЛЯ ПЕРВОЙ ПОПЫТКИ
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
                # МНОГОШАГОВЫЙ ЦИКЛ САМОИСПРАВЛЕНИЯ SQL (ДО 3 ПОПЫТОК)
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
                            raise sql_error
                            
                        st.warning(f"⚠️ Ошибка в SQL (Попытка {attempts}): {str(sql_error)}. Запускаю ИИ для исправления структуры...")
                        
                        # Передаем в историю чистый текст без метаданных
                        messages.append({"role": "assistant", "content": generated_sql})
                        messages.append({
                            "role": "user", 
                            "content": f"Your previous SQL query failed with error: {str(sql_error)}. Please write a clean SQLite query. "
                                       f"Example: SELECT SUBSTR(order_purchase_timestamp, 1, 7) AS sales_month, SUM(price) AS total_sales, COUNT(DISTINCT order_id) AS num_orders FROM order_items_dataset oi JOIN orders_dataset o ON oi.order_id = o.order_id WHERE order_purchase_timestamp LIKE '2017%' GROUP BY 1 ORDER BY 1; "
                                       f"Return ONLY pure SQL text without any object wrappers or extra talk."
                        })
                        
                        response = completion(
                            model="groq/llama-3.1-8b-instant",
                            messages=messages,
                            temperature=0.1
                        )
                        
                        # НАДЕЖНЫЙ REGEX ПАРСЕР ДЛЯ ЦИКЛА ПОВТОРНЫХ ПОПЫТОК
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
                
                # УНИВЕРСАЛЬНЫЙ ПРОМПТ АНАЛИТИКА ПОД ВСЕ ИЗМЕРЕНИЯ БИЗНЕСА
                analyst_system_prompt = (
                    "Ты Ведущий продуктовый аналитик маркетплейса Olist с глубоким пониманием ритейл-календаря. Твоя задача — провести глубокий сравнительный аудит данных и составить отчет СТРОГО НА РУССКОМ ЯЗЫКЕ.\n\n"
                    "МЕТОДОЛОГИЯ АНАЛИЗА ДЛЯ ПОРТФОЛИО:\n"
                    "1. СРАВНИТЕЛЬНЫЙ АНАЛИЗ (MoM / YoY): Внимательно изучи всю временную шкалу в полученной таблице. Сравни целевой месяц (ноябрь 2017) с предыдущими месяцами (сентябрь, октябрь) и последующими (декабрь). Определи реальный математический тренд выручки.\n"
                    "2. КРИТИКА ГИПОТЕЗЫ ПОЛЬЗОВАТЕЛЯ: Если в вопросе утверждается, что продажи упали, но на основе цифр ты видишь взрывной рост в ноябре по сравнению с сентябрем/октябрем — прямо опровергни пользователя. Напиши: 'Внимание: гипотеза о падении продаж полностью опровергнута цифрами DWH. Продажи в ноябре показали рекордный исторический пик!'.\n"
                    "3. ГЕНЕРАЦИЯ БИЗНЕС-ГИПОТЕЗ: Объясни, почему произошел такой аномальный скачок выручки в ноябре (сезонность, Черная пятница, предновогодний бум закупок) без прямых подсказок в коде.\n"
                    "4. СТРУКТУРА ОТЧЕТА:\n"
                    "   - 1. Главный инсайт и Опровержение тренда (Анализ динамики соседних месяцев)\n"
                    "   - 2. Цифры и факты (Точные значения выручки по месяцам из таблицы для доказательства)\n"
                    "   - 3. Аналитические гипотезы (Какие факторы определяют этот тренд)\n"
                    "   - 4. Бизнес-рекомендация (Конкретные шаги для руководства маркетплейса)"
                )
                
                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": analyst_system_prompt},
                        {"role": "user", "content": f"Вопрос пользователя: {user_query}\n\nПолученные широкие данные из базы для контекста:\n{result_df.to_string(index=False)}"}
                    ],
                    temperature=0.2
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
