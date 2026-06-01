# AI-Driven E-Commerce Decision Support System (DSS)
### Autonomous Intelligent Agent Core & Ad-Hoc DWH Audit Pipeline for Olist Marketplace

An enterprise-grade, fault-tolerant Business Intelligence (BI) routing network that automates the first layer of data analytics over a complex 9-table Relational Data Warehouse (DWH) containing 100K+ transaction rows. The platform enables C-level management (CMO, CPO, Product Leads) to query live relational architecture using simple natural language, completely removing manual SQL scripting barriers.

## Live Production Link
**Explore the Live AI Agent Tool on Streamlit Cloud:** `https://olist-ai-analyst-ynao5ntbnividq2katfsir.streamlit.app/`

---

## Core Business Value & Problem Statement
In scaling e-commerce ecosystems, up to 60% of data science and analytics bandwidth is consumed by repetitive, operational ad-hoc queries from business divisions (e.g., extracting regional conversion drops, mapping toxic category delivery overshoots). 

This system completely automates the top of the analytical funnel:
1. **Instant Time-to-Value (TTV):** Compresses the timeline between a commercial hypothesis and data retrieval from hours of manual script-writing down to **3–5 seconds**.
2. **Mitigating Confirmation Bias:** The Analytical Agent possesses built-in critical thinking guardrails. If a manager submits a prompt containing a false business assumption (*"Why did revenue crash in November 2017?"*), the agent halts, executes a DWH audit, and counters with empirical data: *"Warning: The hypothesis is completely disproven. November 2017 established the historical revenue peak of the marketplace (1,153,528 R$, +54% MoM) due to Black Friday surge mechanics."*

---

## Technical Architecture & LLMOps Patterns
The system is engineered as an isolated, two-step agentic execution chain using **Python, SQLite, LiteLLM (Llama 3.1 8B), and Streamlit Cloud**. To maintain an entirely free, zero-overhead production footprint, the stack implements highly resilient software engineering patterns to bypass strict hardware thresholds (6,000 TPM Cloud API limits):
The system is engineered as an isolated, two-step agentic execution chain using **Python, SQLite, LiteLLM (Llama 3.1 8B), and Streamlit Cloud** [2.2, 2.3]. To maintain an entirely free, zero-overhead production footprint, the stack implements highly resilient software engineering patterns to bypass strict hardware thresholds (6,000 TPM Cloud API limits) [2.2, 2.3]:

```
[User Input: Natural Language] 
       │
       ▼
 ┌───────────┐       [Error Logs intercepted via Python Loop]
 │  Step 1   │ ◄──────────────────────────────────────────────────┐
 │  LLM SQL  │                                                    │
 │  Engine   │ ───► [Query Verification in SQLite Storage]        │
 └─────┬─────┘                        │                           │
       │                              ▼ (Syntax Crash or Cutoff)   │
       │                       ┌─────────────┐                    │
       │                       │  ReAct Loop │ ───────────────────┘
       │                       │   Handler   │ (Dynamic Auto-Completion/Memory Flush)
       │                       └─────────────┘
       ▼ (Valid DataFrame)
 ┌───────────┐
 │  Step 2   │ ───► [Dynamic DataFrame Core Volume Matrix Slicing]
 │  Python   │
 └─────┬─────┘
       │
       ▼ (Compressed Context: Top 15 Representative Rows Only)
 ┌───────────┐
 │  Step 3   │
 │ Analytical│ ───► [Final Business Summary: Clean Markdown Matrix Output]
 │  Agent    │
 └───────────┘
```

### 🧠 Key Engineering Implementation Highlights:
*   **Enterprise Semantic Data Catalog Map:** To stop table relation hallucinations, a strict DBML relational constraints catalog is injected into the LLM system layer [2.2, 2.3]. The agent successfully executes multi-table recursive `JOIN` actions across 5+ data tables (reviews, transactional timelines, localized category translation lookups) on its first attempt [2.2].
*   **Few-Shot Temporal Query Training:** The SQL engineering prompt features a pre-trained contextual template teaching the model to index and isolate date operations via integer conversions using native SQLite `julianday()` calculations [2.2, 2.3]. This supports complex day-by-day business tracking [2.2].
*   **Fault-Tolerant Query Self-Completion Loop:** Free-tier inference providers regularly truncate long-form SQL queries right at text filters (`LIKE` or `=` boundaries) [2.2]. The application intercepts these truncation exceptions inside a Python `try-except` structure, dynamically evaluates the user's initial intention, auto-completes the missing syntax operators in-memory, and safely executes the code without dropping the system runtime [2.2, 2.3].
*   **Context Memory Flush Engine:** Successive LLM iteration loops cause context history bloating, which rapidly triggers TPM rate-limiting errors [2.2]. The app triggers a forced memory pure inside the correction loop handlers, reducing error retrieval payload sizes from 5500 down to 400 tokens per call [2.2, 2.3].
*   **Dynamic Data Core DataFrame Compression:** To ensure the final analytical model never runs out of output tokens or drops text mid-sentence, Python dynamically reads the query response matrix, auto-detects the numeric core displaying the highest data weight volume (e.g. revenue sums or order velocity counts), and forwards a concentrated top-15 row summary block to the report prompt while preserving 100% of the raw table data for the end-user display layer [2.2].

---

## 📊 Proven Analytical Showcase (The 'Beleza Saude' Audit)
When fed an abstract business inquiry like: *"Find the worst issues for beleza_saude category. Group by review_score and count orders."*, the autonomous engine orchestrated the following workflow sequence [2.2]:
1. **Step 1 Generation:** Autocomplete routines caught a truncation freeze and safely structured a valid multi-table query [2.2].
2. **Step 2 Processing:** Swept the entire raw production storage array and computed exact volume sets: **5,398 items** matching a flawless 5-star score versus **898 orders** tracking a pure 1-star delivery failure matrix [2.2].
3. **Step 3 Reporting:** The Business Analyst model parsed the compressed array and instantly rendered a clean, uncensored Markdown report, isolating logistical pipeline friction coefficients, predicting seasonal hub delays, and mapping strategic mitigation blueprints for the warehouse directory board [2.2].

---

## ⚙️ Local Development Installation Layout
To set up the database infrastructure locally and inspect the indexing pipelines, execute the following commands in your local workspace terminal:

```bash
# Clone the repository layout
git clone https://github.com
cd olist-ai-analyst-dss

# Install core runtime dependencies
pip install -r requirements.txt

# Run the system interface locally
streamlit run app.py
```
*Note: Make sure to configure your environmental path keys by supplying a valid `GROQ_API_KEY` credential.*

