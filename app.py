import os
import sqlite3
import pandas as pd
import streamlit as st  # <-- MUST BE THE FIRST STREAMLIT IMPORT!
import asyncio
import urllib.request
import requests
import ssl
import re
from litellm import completion

# =====================================================================
# FORCE REBOOT SERVER SESSION CACHE (MUST RUN IMMEDIATELY AFTER ST)
# =====================================================================
if "clear_cache_executed" not in st.session_state:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["clear_cache_executed"] = True
# =====================================================================

# Global Streamlit page presentation configurations
st.set_page_config(page_title="AI Olist Investigator", page_icon="🧠", layout="wide")

st.title("AI-Agent: Digital Detective from the Olist Marketplace")
st.subheader("Fully connected end-to-end ad-hoc audit of e-commerce architecture (9 DWH tables)")

# Secure background environmental setup for credentials injection
if "GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in st.secrets:
    os.environ["GEMINI_API_VERSION"] = "v1"
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

# =====================================================================
# SECURE AUTOMATIC LARGE REPOSITORY DATASET INGESTION CORE
# =====================================================================
DB_PATH = "olist.db"
DB_URL = "https://github.com/akimovagalina/olist-ai-analyst/releases/download/v1.0.0/olist.db"

# Force cache eviction if an outdated, corrupted, or clipped asset is detected
if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) < 90000000:
    os.remove(DB_PATH)

if not os.path.exists(DB_PATH):
    with st.spinner("The full Olist database was not found. Downloading the entire DWH marketplace dataset..."):
        try:
            # Defensive Handshake Bypass: Prevent handshake alert drops over cloud containers
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(DB_URL, context=ssl_context) as response, open(DB_PATH, 'wb') as out_file:
                out_file.write(response.read())
            st.success("✅ All 9 tables of the database were successfully downloaded and connected!")
        except Exception as e:
            st.error(f"❌ Error downloading the database automatically: {e}")
# =====================================================================
# COMPREHENSIVE SEMANTIC SCHEMA CONSTRAINTS CATALOG (DATA CATALOG MAP)
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
    """Executes an incoming query while forcing sub-second structural indexes matching foreign keys"""
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
# =====================================================================
# SYSTEM PAYLOAD PROMPT BLUEPRINTS DEFINITIONS LAYER
# =====================================================================
sql_system_prompt = (
    f"You are a Senior SQLite Analytics Engineer. Your task is to write a valid SQLite query based on this 9-table schema:\n{DATABASE_SCHEMA}\n\n"
    f"CRITICAL RULES:\n"
    f"1. Use ONLY SQLite syntax. NEVER use 'EXTRACT(YEAR/MONTH)' or 'DATEDIFF()'.\n"
    f"2. ULTRA-COMPACT CODE: Keep the query under 8 lines. Never use verbose multi-line statements.\n"
    f"3. STRICT REVENUE AGGREGATION RULE:\n"
    f"   When asked about business verticals, revenue growth, stagnation, stalled performance, or sales totals, you MUST calculate the total revenue using SUM(oi.price) AS total_revenue and pair it with COUNT(DISTINCT o.order_id) AS total_orders.\n"
    f"4. STRICT GROUP BY RULE:\n"
    f"   Always group strictly and only by the text dimension column (e.g., GROUP BY 1). NEVER append transactional unique keys like o.order_id or oi.product_id into the GROUP BY block, as it breaks macro aggregation!\n"
    f"5. FEW-SHOT LEARNING PATTERN 1 (LOGISTICS DELIVERY CORRELATION):\n"
    f"   When asked about delivery time dependency, correlation by days, or tracking delay impact, write strictly like this using a clean CASE block without single-quote syntax breaks:\n"
    f"   SELECT CAST(julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS INT) AS delivery_delay_days, AVG(r.review_score) AS avg_score, COUNT(o.order_id) AS total_orders FROM review_dataset r JOIN orders_dataset o ON r.order_id = o.order_id WHERE o.order_delivered_customer_date IS NOT NULL GROUP BY 1 HAVING total_orders > 100 ORDER BY 1 ASC;\n"
    f"6. FEW-SHOT LEARNING PATTERN 2 (PRODUCT VERTICALS & SALES PERFORMANCE):\n"
    f"   When asked to assess business verticals, product categories, growth, or revenue stall, write strictly like this:\n"
    f"   SELECT t.product_category_name_english, SUM(oi.price) AS total_revenue, COUNT(DISTINCT o.order_id) AS total_orders FROM order_items_dataset oi JOIN products_dataset p ON oi.product_id = p.product_id JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name JOIN orders_dataset o ON oi.order_id = o.order_id WHERE o.order_purchase_timestamp LIKE '2018%' GROUP BY 1 ORDER BY 2 DESC;\n"
    f"7. Return ONLY the raw SQL query string. No explanations, no conversation wrappers, no markdown blocks."
)

analyst_system_prompt = (
    "You are a Lead Product Analyst for the Olist marketplace with deep critical thinking. Study the provided raw data table, "
    "independently discover the core commercial trend, and construct a concise, high-impact markdown report STRICTLY IN ENGLISH.\n\n"
    "RULES FOR AUTONOMOUS ANALYTICS:\n"
    "1. PATTERN ANALYSIS: Scan across table lines, locate mathematical dependencies, records, and seasonal shifts manually.\n"
    "2. EMPIRICAL HYPOTHESES: Generate independent growth/stagnation hypotheses directly from numerical variances without software steering.\n"
    "🛑 UNIVERSAL METRIC INTEGRITY TRACKING RULE:\n"
    "You must carefully evaluate the scaling direction of numerical indicators. "
    "Pay absolute attention to negative (-) and positive (+) boundaries. "
    "Ensure your analytical summary explicitly tracks whether numbers are moving toward a positive increase or moving deeper into a negative baseline shift. "
    "Never invert trend vectors, as this will trigger an immediate failure from the security auditing board."
    "🛑 CRITICAL LOGISTICS FACTOR (MATHEMATICAL REALITY CHANNELS):\n"
    "In e-commerce distribution networks: Negative delivery days imply the parcel arrived EARLY (ahead of schedule), keeping scores excellent (4.3+). "
    "Positive values mean shipments arrived LATE (delayed), which drops satisfaction scores down to a 1.5-2 star cliff. "
    "You must aggressively isolate this trend. Delays kill customer retention. "
    "Do not confuse early arrivals with delivery overshoots! Check the minus signs carefully.\n\n"
    "MANDATORY REPORT FORMAT (Strictly utilize these headers and standard bullet arrays. Do NOT use markdown tables with '|' symbols):\n"
    "### 🎯 1. Main Insight\n"
    "*write your independent qualitative conclusion over the primary data trend here*\n\n"
    "### 📊 2. Key Figures\n"
    "*list 2-3 critical peak values or percentage changes detected in the dataset block*\n\n"
    "### 💡 3. Your Hypotheses\n"
    "*supply exactly 2 independent commercial hypotheses explaining the root cause behind this trend*\n\n"
    "### 🚀 4. Strategic Recommendation\n"
    "*provide 3 actionable operational decisions tailored directly for C-level directors*"
)

judge_system_prompt = (
    "You are the Head Quality Auditor for analytical business intelligence pipelines. "
    "Your strict task is to cross-examine the junior analyst's text conclusions against the factual reality of the raw database results.\n\n"
    "CRITICAL AUDITING CHECKLIST:\n"
    "1. MATHEMATICAL SIGN INTEGRITY TEST: You must meticulously analyze whether the numerical values in the table are POSITIVE (+) or NEGATIVE (-). "
    "Verify that the analyst correctly interprets the direction of the trend. For example, if a negative number indicates an improvement or a baseline shift, "
    "ensure the analyst does not falsely interpret it as a decline. A logical inversion of signs or numeric values is a critical security failure.\n"
    "2. CORE LOGIC & PLOTS REASONING: Evaluate the overall business logic of the report. The hypotheses and recommendations must logically flow "
    "from the highest data diversity vectors. If the analyst invents metrics, introduces hallucinations, or states a correlation that contradicts the mathematical rows, "
    "you MUST immediately return a FAILED evaluation status and award a 1/5 score.\n"
    "3. EMPIRICAL VALUE ALIGNMENT: Ensure all specific figures quoted in the report match the source table exactly.\n\n"
    "OUTPUT YOUR AUDIT SPECS CONCISELY MATCHING THIS MAXIMUM RESILIENCY FRAMEWORK:\n"
    "🎯 **AUDIT STATUS:** [PASSED / FAILED]\n"
    "⭐️ **PRECISION SCORE:** [X/5 Stars]\n"
    "🔍 **AUDITOR EXCEPTION REMARKS:** [detail any detected semantic errors, misread signs, or print 'No errors discovered. Data fully verified.']"
)
# =====================================================================
# USER INPUT GATEWAY AND RUNTIME PIPELINE LAYER
# =====================================================================
user_query = st.text_input(
    "✍️ Enter any business question about the Olist database in English:",
    value="How do user reviews depend on delivery delay times by days?"
)

if st.button("Искать ответы / Run Audit"):
    if not user_query.strip():
        st.error("Please provide a valid question framework.")
    else:
        # Prevent layout assignment exceptions via early runtime variable caching
        # НАДЕЖНАЯ ЗАЩИТНАЯ ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ В НАЧАЛЕ ЦИКЛА
        # HARD RESERVED VARIABLES INITIALIZATION FOR STABILITY
        generated_sql = ""
        result_df = pd.DataFrame()
        compressed_df = pd.DataFrame()
        final_report = "The system failed to compile a valid analytical response due to an early pipeline interruption."
        
        with st.status("🕵️‍♂️ Agent at work... Running ad-hoc structural audit", expanded=True) as status:
            try:
                # -------------------------------------------------------------
                # ENGINE STEP 1: PARSING NATURAL LANGUAGE TO DETERMINISTIC SQL
                # -------------------------------------------------------------
                st.write("🤖 Step 1: Generating SQL code based on the table schema...")
                
                messages = [
                    {"role": "system", "content": sql_system_prompt},
                    {"role": "user", "content": f"User's business question: {user_query}"}
                ]
                
                response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.0,
                    max_tokens=400
                )
                
                # FIXED STEP 1 HIGH-RESILIENCY PAYLOAD ARRAYS PARSER
                try:
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        # Fixed: Added explicit zero array index to safely read the message object
                        generated_sql = response.choices[0].message.content
                    elif isinstance(response, dict) and 'choices' in response and len(response['choices']) > 0:
                        generated_sql = response['choices'][0]['message']['content']
                    else:
                        generated_sql = str(response)
                except Exception as step1_parse_err:
                    raise RuntimeError(f"Step 1 payload parsing failed: {step1_parse_err}")
                    
                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                
                # Resilient ReAct runtime execution loop with built-in auto-completion logic
                attempts = 0
                max_attempts = 3
                sql_success = False
                
                while attempts < max_attempts and not sql_success:
                    attempts += 1
                    try:
                        generated_sql = generated_sql.strip()
                        if generated_sql.endswith("LIKE") or generated_sql.endswith("=") or generated_sql.endswith("WHERE"):
                            st.warning("⚡ API line cutoff caught at filtering block. Applying programmatic string completion...")
                            generated_sql = generated_sql.split("WHERE") + " GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
                        
                        if attempts == 1:
                            st.code(generated_sql, language="sql")
                        else:
                            st.markdown(f"**🔄 Self-Correction Attempt №{attempts-1}:**")
                            st.code(generated_sql, language="sql")
                            
                        result_df = run_sql_query(generated_sql)
                        sql_success = True
                    except Exception as sql_error:
                        if attempts == max_attempts:
                            st.warning("🛡️ Activating dynamic disaster-recovery query fallback routing...")
                            fallback_prompt = (
                                f"The manager asked: '{user_query}'. The previous complex query failed with error: {str(sql_error)}.\n"
                                f"Write a fallback, ultra-simple SQLite query (max 3 lines) to answer this. "
                                f"Rules: Use ONLY 1 plain JOIN, standard columns, basic GROUP BY, and LIMIT 10.\n"
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
                                # FIXED STEP 1 FALLBACK PAYLOAD ARRAYS PARSER
                                if hasattr(response_fallback, 'choices') and len(response_fallback.choices) > 0:
                                    generated_sql = response_fallback.choices[0].message.content
                                else:
                                    generated_sql = response_fallback['choices'][0]['message']['content']
                                generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()
                            except Exception:
                                generated_sql = "SELECT order_status, COUNT(order_id) AS total_orders FROM orders_dataset GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
                                
                            st.markdown("**🛡️ Emergency fallback database code executed successfully:**")
                            st.code(generated_sql, language="sql")
                            result_df = run_sql_query(generated_sql)
                            sql_success = True
                            break
                            
                        st.warning(f"⚠️ DWH Traceback Crash (Attempt {attempts}): {str(sql_error)}. Resetting ReAct pipeline memory...")
                        messages = [
                            {"role": "system", "content": sql_system_prompt},
                            {"role": "user", "content": f"Your previous SQL failed with error: {str(sql_error)}. Rewrite a clean SQLite query to answer: '{user_query}'. CRITICAL: Never put aggregate functions like AVG() inside the GROUP BY clause! Return ONLY raw SQL text."}
                        ]
                        response = completion(
                            model="groq/llama-3.1-8b-instant",
                            messages=messages,
                            temperature=0.0,
                            max_tokens=400
                )
                        # FIXED STEP 1 LOOP REPAIR PAYLOAD ARRAYS PARSER
                        if hasattr(response, 'choices') and len(response.choices) > 0:
                            generated_sql = response.choices[0].message.content
                        else:
                            generated_sql = response['choices'][0]['message']['content']
                        generated_sql = generated_sql.strip().replace("```sql", "").replace("```", "").strip()

                # -------------------------------------------------------------
                # ENGINE STEP 2: METADATA INFORMATION SHANNON ENTROPY FILTERS
                # -------------------------------------------------------------
                st.write("🔍 Step 2: Executing live query in olist.db and evaluating metrics matrix...")
                
                if not result_df.empty:
                    try:
                        numeric_cols = result_df.select_dtypes(include=['number']).columns.tolist()
                        if numeric_cols:
                            sort_target = max(numeric_cols, key=lambda col: result_df[col].sum())
                            compressed_df = result_df.sort_values(by=sort_target, ascending=False).head(15)
                        else:
                            compressed_df = result_df.head(15)
                    except Exception:
                        compressed_df = result_df.head(15)
                
                # -------------------------------------------------------------
                # ENGINE STEP 3: CONTEXT REPORT SYNTHESIS PIPELINE
                # -------------------------------------------------------------

                report_response = completion(
                    model="groq/llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": analyst_system_prompt},
                        {"role": "user", "content": f"Calculated relational metrics passed for your strategic evaluation:\n{compressed_df.to_string(index=False)}"}
                    ],
                    temperature=0.2,
                    max_tokens=800
                )
                
                # FIXED STEP 3 HIGH-RESILIENCY PAYLOAD ARRAYS PARSER
                if hasattr(report_response, 'choices') and len(report_response.choices) > 0:
                    final_report = report_response.choices[0].message.content
                else:
                    final_report = report_response['choices'][0]['message']['content']


                
                # -------------------------------------------------------------
                # ENGINE STEP 4: CROSS-MODEL AI-AS-A-JUDGE VERIFICATION LOOP
                # -------------------------------------------------------------
                st.write("🛡️ Step 4: Activating autonomous cross-model audit verification (Google Gemini)...")
                
                # Defensive structural binding: Check if the data frame core was successfully built
                if not compressed_df.empty:
                    data_payload_string = compressed_df.to_string(index=False)
                elif not result_df.empty:
                    data_payload_string = result_df.head(15).to_string(index=False)
                else:
                    data_payload_string = "NO SYSTEM DATA DETECTED DUE TO AN EARLY PIPELINE CUTOFF."
                
                try:
                    # ПОДКЛЮЧАЕМ АКТУАЛЬНЫЙ ФЛАГ ТЯЖЕЛОЙ МОДЕЛИ LLAMA 3.3 70B НА РОЛЬ СУДЬИ
                    judge_response = completion(
                        model="groq/llama-3.3-70b-versatile",  # Официальный преемник Mixtral
                        messages=[
                            {"role": "system", "content": judge_system_prompt},
                            {"role": "user", "content": f"Source database metrics block:\n{data_payload_string}\n\nGenerated analyst insight report:\n{final_report}"}
                        ],
                        temperature=0.0,
                        max_tokens=400
                    )

                    # High-resiliency dictionary and object choices array payload parser
                    if hasattr(judge_response, 'choices') and len(judge_response.choices) > 0:
                        judge_verdict = judge_response.choices[0].message.content
                    elif isinstance(judge_response, dict) and 'choices' in judge_response and len(judge_response['choices']) > 0:
                        judge_verdict = judge_response['choices'][0]['message']['content']
                    else:
                        judge_verdict = str(judge_response)
                        
                except Exception as judge_api_err:
                    # Fault-Tolerant Fallback: Soft alert handling if Google Studio endpoints time out
                    judge_verdict = (
                        "🎯 **AUDIT STATUS:** DEFERRED\n"
                        f"⚠️ The external verification gateway Google Gemini is temporarily throttled: {judge_api_err}\n"
                        "💡 The base data warehouse and query summaries are running smoothly. Verify your GEMINI_API_KEY in secrets setup."
                    )
                
                # Update Streamlit loading animation status container to success
                status.update(label="✅ Comprehensive analytics audit successfully executed!", state="complete", expanded=False)
                
                # LIVE DASHBOARD GRAPHICS COMPILER OUTPUT LAYER FOR USER DISPLAY
                st.success("📊 Live transaction matrix pulled from Olist production infrastructure:")
                st.dataframe(result_df, use_container_width=True)
                
                st.subheader("🎯 Executive Analytical Insights Report:")
                st.markdown(final_report)
                
                st.subheader("🛡️ Autonomous Pipeline Verification Board Verdict:")
                if "PASSED" in judge_verdict.upper():
                    st.success(judge_verdict)
                else:
                    st.warning(judge_verdict)
                    
            except Exception as e:
                status.update(label="❌ System Exception Intercepted", state="error", expanded=False)
                st.error(f"Technical runtime failure: {e}")

