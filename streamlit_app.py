# streamlit_app.py

import streamlit as st
from pathlib import Path
import pandas as pd
import time
from datetime import date

# Import new components
from services.duty_calculator import DutyCalculator
from utils.countries import COUNTRY_LIST

# Existing imports
from chains.hts_chain import HTSOrchestrator
from agents.query_agent import QueryAgent

# NOTE: The direct import of build_vectorstore is no longer needed here
# from utils.vectorstore import build_vectorstore

# Configuration
BASE = Path(__file__).parent
PROCESSED_CSV = BASE / "data" / "processed" / "hts_processed.csv"

# Page configuration
st.set_page_config(
    page_title="HTS Intelligent Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stButton > button { width: 100%; margin-top: 10px; }
    .candidate-box { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0; }
    .success-box { background-color: #d4edda; padding: 20px; border-radius: 10px; border: 2px solid #c3e6cb; }
    .calculator-box { background-color: #eef2f6; padding: 20px; border-radius: 10px; border: 2px solid #d4dae3; }
    .results-box { background-color: #fff; padding: 20px; border-radius: 10px; border: 2px solid #d4edda; }
    </style>
""", unsafe_allow_html=True)

# Application header
st.title("HTS Intelligent Classification & Duty Assistant")
st.markdown("""
**1. Find HTS Code:** Enter a product description or a full/partial HTS code.
**2. Calculate Duty:** Once classified, enter shipment details to estimate the landed cost.
""")

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.candidates = pd.DataFrame()
    st.session_state.current_question = None
    st.session_state.question_history = []
    st.session_state.initial_query = ""
    st.session_state.final_result = None
    st.session_state.question_count = 0
    st.session_state.calculation_result = None
    st.session_state.chapter_info = None
    st.session_state.pipeline_status = ""

def reset_session():
    st.session_state.candidates = pd.DataFrame()
    st.session_state.current_question = None
    st.session_state.question_history = []
    st.session_state.initial_query = ""
    st.session_state.final_result = None
    st.session_state.question_count = 0
    st.session_state.calculation_result = None
    st.session_state.chapter_info = None

# Sidebar
with st.sidebar:
    st.header("⚙️ System Management")
    if not PROCESSED_CSV.exists():
        st.warning("Processed CSV not found. Please run the pipeline first.")
    elif st.session_state.get("pipeline_status"):
        st.success(st.session_state.pipeline_status)
    else:
        st.success("✅ System ready")

    # ✨ MODIFIED: This block is now corrected and optimized
    if st.button("🔄 Run Full Pipeline", help="Download, preprocess, and embed HTS data"):
        st.session_state.pipeline_status = ""
        start_time = time.time()
        
        orchestrator = HTSOrchestrator(BASE)
        with st.spinner("Running pipeline... This may take several minutes."):
            progress_bar = st.progress(0, text="Starting pipeline...")
            
            # Step 1: Fetch and process data (Fast part)
            progress_bar.progress(10, text="Step 1/2: Fetching and preprocessing HTS data...")
            processed_path = orchestrator.run_preprocessing_pipeline()
            
            # Step 2: Embed and index data (Slow part)
            progress_bar.progress(30, text="Step 2/2: Embedding data and indexing... (This may take a moment)")
            indexed = orchestrator.run_embedding_pipeline(processed_path)
            
            progress_bar.progress(100, text="✅ Pipeline complete!")
            time.sleep(2)

        end_time = time.time()
        elapsed_time = end_time - start_time
        
        st.session_state.pipeline_status = f"Pipeline run successful! ({elapsed_time:.2f}s)"
        st.success(f"✅ Pipeline finished in {elapsed_time:.2f} seconds. Indexed {indexed} records.")
        st.rerun()

    st.divider()
    st.header("📊 Current Session")
    if not st.session_state.candidates.empty:
        st.metric("Candidates Remaining", len(st.session_state.candidates))
        st.metric("Questions Asked", st.session_state.question_count)
    else:
        st.info("No active session")

    if st.button("🔄 Reset Session"):
        reset_session()
        st.rerun()

# --- Main application logic remains unchanged ---
if PROCESSED_CSV.exists():
    qa_agent = QueryAgent(str(PROCESSED_CSV))

    # --- CLASSIFICATION UI ---
    st.header("Step 1: Find HTS Code")
    user_input = st.text_input(
        "Enter HTS Code (10-digit), Partial HTS Code (4/6 digits), or Product Description:",
        placeholder="e.g., 0101210010, 0101, stainless steel kitchen sink",
        key="unified_input"
    )

    if st.button("Search / Classify", type="primary"):
        if user_input:
            reset_session()
            st.session_state.initial_query = user_input.strip()
            clean_input = user_input.replace(".", "").strip()
            
            if clean_input.isdigit() and len(clean_input) == 10:
                with st.spinner("Searching exact HTS match..."):
                    results = qa_agent.query_exact_hts(user_input.strip(), k=5)
                if results:
                    st.session_state.final_result = pd.Series(results[0]["payload"])
                else:
                    st.warning("No exact matches found. Try a partial code or description.")
            
            elif clean_input.isdigit() and len(clean_input) in [4, 6]:
                with st.spinner("Finding candidates..."):
                    candidates = qa_agent.get_candidates_by_prefix(user_input)
                if not candidates.empty:
                    st.session_state.candidates = candidates
                    st.session_state.chapter_info = qa_agent.get_chapter_description(candidates)
                    st.success(f"Found {len(candidates)} candidates for prefix '{user_input}'")
                else:
                    st.error(f"No HTS codes found starting with '{user_input}'")
            
            else:
                with st.spinner("Searching by product description..."):
                    candidates = qa_agent.get_candidates_by_product(user_input.strip(), k=200)
                if not candidates.empty:
                    st.session_state.candidates = candidates
                    st.session_state.chapter_info = qa_agent.get_chapter_description(candidates)
                    st.success(f"Found {len(candidates)} potential matches for '{user_input}'")
                else:
                    st.error("No matching products found. Try different keywords.")
            st.rerun()

    # Question-answer classification for partial/product searches
    if not st.session_state.candidates.empty and st.session_state.final_result is None:
        st.divider()
        col1, col2 = st.columns([2, 1])
        with col1:
            st.header("🎯 Classification in Progress")
            st.write(f"Initial query: **{st.session_state.initial_query}**")
        with col2:
            st.metric("Candidates Remaining", len(st.session_state.candidates))
        
        if st.session_state.chapter_info:
            info = st.session_state.chapter_info
            st.info(f"Your product appears to belong to chapter **{info['chapter_code']}**: *{info['description']}*")
            st.divider()

        if len(st.session_state.candidates) == 1:
            st.session_state.final_result = st.session_state.candidates.iloc[0]
            st.rerun()
        else:
            if st.session_state.current_question is None:
                question = qa_agent.generate_smart_question(st.session_state.candidates)
                if question:
                    st.session_state.current_question = question
                else:
                    st.warning("Cannot narrow down further. Showing top candidates:")
                    for idx, row in st.session_state.candidates.head(5).iterrows():
                        with st.expander(f"HTS: {row['HTS Number']}"):
                            details = qa_agent.get_candidate_details(row)
                            for key, value in details.items():
                                st.write(f"**{key}:** {value}")

            if st.session_state.current_question:
                question = st.session_state.current_question
                st.subheader(question["question"])
                num_options = len(question["options"])
                option_cols = st.columns(num_options) if num_options <= 5 else st.columns(5)
                
                selected_option = None
                for idx, option in enumerate(question["options"]):
                    col_index = idx % len(option_cols)
                    with option_cols[col_index]:
                        if st.button(option["label"], key=f"opt_{idx}", use_container_width=True,
                                     help=f"Expected candidates: {option['expected_count']}"):
                            selected_option = option

                if selected_option:
                    filtered = qa_agent.filter_candidates_by_answer(
                        st.session_state.candidates, question, selected_option
                    )
                    st.session_state.candidates = filtered
                    st.session_state.question_history.append({
                        "question": question["question"],
                        "answer": selected_option["label"]
                    })
                    st.session_state.current_question = None
                    st.session_state.question_count += 1
                    st.rerun()

    # --- FINAL RESULT AND DUTY CALCULATOR UI ---
    if st.session_state.final_result is not None:
        st.divider()
        
        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.header("✅ Classification Complete!")
        result = st.session_state.final_result
        details = qa_agent.get_candidate_details(result)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("HTS Classification")
            st.write(f"**HTS Number:** `{details['HTS Number']}`")
            st.write(f"**Full Description:** {details['Full Description']}")
        with col2:
            st.subheader("Duty Information")
            st.write(f"**Unit of Quantity:** {details['Unit of Quantity']}")
            st.write(f"**General Rate:** {details['General Rate of Duty']}")
            st.write(f"**Special Rate:** {details['Special Rate of Duty']}")
            st.write(f"**Column 2 Rate:** {details['Column 2 Rate of Duty']}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()

        st.markdown('<div class="calculator-box">', unsafe_allow_html=True)
        st.header("Step 2: Calculate Landed Cost")
        
        with st.form(key="duty_calculator_form"):
            form_col1, form_col2 = st.columns(2)
            with form_col1:
                base_value = st.number_input("Base Product Value ($USD)", min_value=0.01, value=1000.0, step=100.0)
                country_names = list(COUNTRY_LIST.keys())
                selected_country_name = st.selectbox(
                    "Country of Origin", 
                    options=country_names, 
                    index=country_names.index("China")
                )
                entry_date = st.date_input("Entry Date", value=date.today())

            with form_col2:
                transport_mode = st.selectbox("Mode of Transport", options=["Ocean", "Air", "Rail", "Truck"])
                has_exclusion = st.checkbox("Apply Chapter 99 Exclusion?", help="Reduces duty for specific products.")
                metal_percent = st.slider(
                    "Metal Content (%) (Cu, Al, Pt, Fe)", 
                    min_value=0, max_value=100, value=0,
                    help="Dummy surcharge applied for products containing these metals."
                )

            submit_button = st.form_submit_button(label='Calculate Landed Cost', type="primary")

        if submit_button:
            country_iso = COUNTRY_LIST[selected_country_name]
            
            form_data = {
                "base_value": base_value, "country_iso": country_iso, "transport_mode": transport_mode,
                "entry_date": entry_date, "has_exclusion": has_exclusion, "metal_percent": metal_percent
            }
            
            calculator = DutyCalculator(st.session_state.final_result)
            st.session_state.calculation_result = calculator.calculate_landed_cost(form_data)
        
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.calculation_result:
            st.markdown('<div class="results-box">', unsafe_allow_html=True)
            res = st.session_state.calculation_result
            st.subheader("Estimated Landed Cost Breakdown")
            
            res_col1, res_col2, res_col3 = st.columns(3)
            with res_col1:
                st.metric("Base Product Value", f"${res['base_value']:,.2f}")
            with res_col2:
                st.metric("Total Duties & Surcharges", f"${res['total_duties']:,.2f}")
            with res_col3:
                st.metric("Landed Cost", f"${res['landed_cost']:,.2f}", delta=f"Fees: ${res['mpf_hmf_fees']:,.2f}")
            
            st.markdown("---")
            st.write(f"**Applicable Rate Category:** `{res['rate_category']}` at `{res['duty_rate_pct']}%`")
            st.write(f" ▸ **Base Duty:** `${res['base_duty']:,.2f}`")
            if res['metal_surcharge'] > 0:
                st.write(f" ▸ **Metal Surcharge:** `${res['metal_surcharge']:,.2f}`")
            if res['exclusion_reduction'] > 0:
                st.write(f" ▸ **Exclusion Reduction:** `- ${res['exclusion_reduction']:,.2f}`")

            if res["calculation_notes"]:
                st.warning("Please Note:")
                for note in res["calculation_notes"]:
                    st.write(f"- {note}")
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        if st.button("🔍 New Search", type="secondary"):
            reset_session()
            st.rerun()

else:
    st.error("⚠️ No processed data found. Please run the pipeline from the sidebar first.")