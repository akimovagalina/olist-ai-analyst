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

st.title("AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Полносвязный сквозной ad-hoc аудит e-commerce архитектуры (9 таблиц DWH)")

# Безопасное считывание API Ключа из Streamlit Secrets
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# НАДЕЖНАЯ АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ПОЛНОЙ БАЗЫ ДАННЫХ
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://github.com/akimovagalina/olist-ai-analyst/releases/download/v1.0.0/olist.db"


if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) < 8000000:
    os.remove(DB_PATH)

if not os.path.exists(DB_PATH):
    with st.spinner("📦 Полная база Olist не найдена. Скачиваю весь датасет DWH маркетплейса (9 таблиц, 65 MB)..."):
        try:
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(DB_URL, context=ssl_context) as response, open(DB_PATH, 'wb') as out_file:
                out_file.write(response.read())
            st.success("✅ Все 9 таблиц базы данных успешно загружены и подключена!")
            
        except Exception as e:
            st.error(f"❌ Ошибка автоматического скачивания базы: {e}")

# =====================================================================
# ПОЛНАЯ СХЕМА ВСЕХ 9 ТАБЛИЦ СТРУКТУРЫ OLIST ДЛЯ ИИ
# =====================================================================
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
    # Индексируем ключи связи для мгновенного выполнения JOIN
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
default_query = "Define the geographic distribution of customers by states. Show the top 5 states with the highest total sales volume and count of unique customers."
user_query = st.text_area("✍️ Введите любой ваш бизнес-вопрос к базе Olist на английском языке:", value=default_query, height=100)
if hasattr(response, 'choices') and hasattr(response.choices, 'message'):
                            generated_sql = response.choices.message.content
                        else:
                            generated_sql = response['choices'][0]['message']['content']
                        
                    generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                    st.markdown("**Исправленный SQL-запрос:**")
                    st.code(generated_sql, language="sql")
                    result_df = run_sql_query(generated_sql)
                
                st.write("🔍 Шаг 2: Выполнение запроса в olist.db и извлечение точных метрик...")
                st.write("✍️ Шаг 3: Формирование аналитического отчета на русском языке...")
                
                # УНИВЕРСАЛЬНЫЙ ПРОМПТ АНАЛИТИКА ПОД ВСЕ ИЗМЕРЕНИЯ БИЗНЕСА
                analyst_system_prompt = (
                    "Ты Главный бизнес-аналитик маркетплейса Olist. Твоя задача — провести глубокий аудит данных и составить отчет СТРОГО НА РУССКОМ ЯЗЫКЕ.\n\n"
                    "МЕТОДОЛОГИЯ АВТОНОМНОГО АНАЛИЗА:\n"
                    "1. ДИНАМИЧЕСКИЙ ОХВАТ: Определи контекст данных. Если в таблице города/штаты — делай глубокий географический разбор (где ядро клиентов, где дефицит). Если там даты — делай MoM/YoY анализ трендов. Если категории — анализируй структуру продаж.\n"
                    "2. КРИТИКА И ГИПОТЕЗЫ: Внимательно сопоставляй вопрос бизнеса с полученными цифрами. Опровергай ложные гипотезы пользователя, если они противоречат математическим фактам. Выдвигай сильные коммерческие гипотезы о скрытых причинах такого распределения.\n"
                    "3. СТРУКТУРА ОТЧЕТА:\n"
                    "   - 1. Главный инсайт исследования (Реальное положение дел из цифр)\n"
                    "   - 2. Цифры и факты (Точные значения, лидеры и аутсайдеры из таблицы для доказательства)\n"
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
                
                res_report_str = str(report_response)
                if "content=" in res_report_str:
                    final_report = res_report_str.split("content=")[1].split(", role=")[0].strip("'\"").replace("\\n", "\n")
                else:
                    if hasattr(report_response, 'choices') and hasattr(report_response.choices, 'message'):
                        final_report = report_response.choices.message.content
                    else:
                        final_report = report_response['choices'][0]['message']['content']
                    
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