import os
import sqlite3
import pandas as pd
import streamlit as st
import asyncio
import urllib.request
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# Настройка внешнего вида страницы Streamlit
st.set_page_config(page_title="AI Olist Investigator", page_icon="🕵️‍♂️", layout="wide")

st.title("🕵️‍♂️ AI-Агент: Цифровой Детектив Маркетплейса Olist")
st.subheader("Автономный сквозной аудит e-commerce данных с помощью Multi-Agent Crew & Groq / Llama 3")

# Безопасное считывание API Ключа из Streamlit Secrets
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# АВТОМАТИЧЕСКАЯ ЗАГРУЗКА БАЗЫ ДАННЫХ
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://huggingface.co"

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

def run_sql_query(sql_code: str) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        # Оптимизация: создаем индексы на лету для моментального выполнения JOIN
        cursor = conn.cursor()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_id ON order_items_dataset(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_order_id ON review_dataset(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_id ON order_items_dataset(product_id);")
        
        df = pd.read_sql_query(sql_code, conn)
        conn.close()
        if df.empty: 
            return "Query executed successfully, but no rows were returned."
        return df.head(10).to_string(index=False)
    except Exception as e:
        return f"SQL Error: {str(e)}. Please rewrite your query."

@tool("SQL Database Query Tool")
def sql_tool(sql_code: str) -> str:
    """Executes a SQLite query against olist.db and returns the data as text. Input must be pure SQL text."""
    return run_sql_query(sql_code)

# Инициализация сверхбыстрой модели Groq Llama 3 с отключением несовместимого кэша
groq_llm = LLM(
    model="groq/llama3-8b-8192", 
    temperature=0.1,
    cache=False  # Принудительно отключаем внутреннее кэширование CrewAI для обхода бага Groq
)


# Интерфейс ввода вопроса
default_query = "Find top 5 product categories with the highest number of worst reviews (review_score = 1), given that the category has more than 50 items sold in total."
user_query = st.text_area("✍️ Введите ваш бизнес-вопрос к базе Olist (для стабильности ИИ рекомендуется вводить на английском):", value=default_query, height=100)

if st.button("🚀 Запустить расследование"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Пожалуйста, укажите валидный GROQ_API_KEY в настройках Secrets!")
    else:
        with st.status("🕵️‍♂️ Команда агентов Groq приступила к работе...", expanded=True) as status:
            try:
                st.write("🤖 Шаг 1: Инициализация агентов...")
                
                sql_developer = Agent(
                    role="Senior SQL Developer",
                    goal="Write precise SQL queries to extract business data from olist.db based on user questions.",
                    backstory=f"You are a database expert. You write pure SQLite code. If a query fails, you rewrite it. Schema:\n{DATABASE_SCHEMA}",
                    tools=[sql_tool], llm=groq_llm
                )

                business_analyst = Agent(
                    role="Lead Business Analyst",
                    goal="Analyze raw data tables to identify hidden operational or commercial issues.",
                    backstory="You are a data interpreter. You look for anomalies, calculate aggregates, and find root causes.",
                    llm=groq_llm
                )

                cmo_reporter = Agent(
                    role="Chief Marketing Officer",
                    goal="Translate complex analytical findings into a clean business summary for executive leadership.",
                    backstory="You specialize in writing clear executive summaries. You must deliver the final report in RUSSIAN language.",
                    llm=groq_llm
                )

                task_write_sql = Task(
                    description="Look at the user request: '{user_question}'. Write and execute a SQL query using the 'SQL Database Query Tool' to fetch relevant data rows.",
                    expected_output="Raw text tables from the database.", agent=sql_developer
                )

                task_analyze_data = Task(
                    description="Examine the numbers fetched by the SQL developer. Identify the key business anomalies, trends, or problematic metrics.",
                    expected_output="An analytical breakdown of the data.", agent=business_analyst
                )

                task_write_report = Task(
                    description=(
                        "Take the analyst's findings and format them as an executive summary for top management.\n"
                        "CRITICAL: The final report MUST be written strictly in RUSSIAN language.\n"
                        "Format requirements:\n"
                        "1. Суть проблемы (Main Insight)\n"
                        "2. Цифры и факты (Data Proofs с точными значениями из базы)\n"
                        "3. Бизнес-рекомендация (Actionable Advice)"
                    ),
                    expected_output="A well-formatted Markdown executive summary completely written in RUSSIAN.", agent=cmo_reporter
                )

                crew = Crew(
                    agents=[sql_developer, business_analyst, cmo_reporter],
                    tasks=[task_write_sql, task_analyze_data, task_write_report],
                    process=Process.sequential
                )
                
                st.write("🔍 Шаг 2: Глубокое сканирование DWH маркетплейса...")
                
                final_result = asyncio.run(crew.kickoff_async(inputs={"user_question": user_query}))
                
                status.update(label="✅ Расследование успешно завершено!", state="complete", expanded=False)
                
                st.success("🎯 Финальный аналитический отчет готов:")
                st.markdown(final_result)
                
            except Exception as e:
                status.update(label="❌ Ошибка выполнения", state="error", expanded=False)
                st.error(f"Произошел технический сбой: {e}")
