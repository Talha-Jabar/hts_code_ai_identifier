# streamlit_app.py

import streamlit as st
from pathlib import Path
import pandas as pd
from chains.hts_chain import HTSOrchestrator
from agents.query_agent import QueryAgent
from utils.vectorstore import build_vectorstore
import time

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
    </style>
""", unsafe_allow_html=True)

# Application header
st.title("🔍 HTS Intelligent Classification Assistant")
st.markdown("""
**Smart HTS Code Finder**  
Enter either a complete HTS code, partial HTS code (4/6 digits), or a product description.  
The system will automatically detect and run the right classification process.
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

def reset_session():
    st.session_state.candidates = pd.DataFrame()
    st.session_state.current_question = None
    st.session_state.question_history = []
    st.session_state.initial_query = ""
    st.session_state.final_result = None
    st.session_state.question_count = 0

# Sidebar
with st.sidebar:
    st.header("⚙️ System Management")
    if not PROCESSED_CSV.exists():
        st.warning("Processed CSV not found. Please run the pipeline first.")
    else:
        st.success("✅ System ready")

    if st.button("🔄 Run Full Pipeline", help="Download, preprocess, and embed HTS data"):
        orchestrator = HTSOrchestrator(BASE)
        with st.spinner("Running pipeline... This may take several minutes."):
            progress_bar = st.progress(0)
            progress_bar.progress(33, text="Fetching latest HTS data...")
            result = orchestrator.run_full_pipeline()
            progress_bar.progress(66, text="Processing and embedding data...")
            processed_path = result["processed"]
            indexed = build_vectorstore(processed_path, overwrite=True)
            progress_bar.progress(100, text="Complete!")
        st.success(f"✅ Pipeline complete! Indexed {indexed} records.")
        st.info(f"Processed file: {processed_path}")
        time.sleep(2)
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

# Main
if PROCESSED_CSV.exists():
    qa_agent = QueryAgent(str(PROCESSED_CSV))

    # Universal input field
    st.header("🔎 Search")
    user_input = st.text_input(
        "Enter HTS Code (10-digit), Partial HTS Code (4/6 digits), or Product Description:",
        placeholder="e.g., 0101210010, 0101, textile, horse",
        key="unified_input"
    )

    if st.button("Search / Classify", type="primary"):
        if user_input:
            reset_session()
            st.session_state.initial_query = user_input.strip()
            clean_input = user_input.replace(".", "").strip()

            if clean_input.isdigit() and len(clean_input) == 10:
                # Exact HTS Search
                with st.spinner("Searching exact HTS match..."):
                    results = qa_agent.query_exact_hts(user_input.strip(), k=5)
                if results:
                    st.session_state.final_result = pd.Series(results[0]["payload"])
                else:
                    st.warning("No exact matches found. Try a partial code or description.")
            elif clean_input.isdigit() and len(clean_input) in [4, 6]:
                # Partial HTS Search
                with st.spinner("Finding candidates..."):
                    candidates = qa_agent.get_candidates_by_prefix(user_input)
                if not candidates.empty:
                    st.session_state.candidates = candidates
                    st.success(f"Found {len(candidates)} candidates for prefix '{user_input}'")
                else:
                    st.error(f"No HTS codes found starting with '{user_input}'")
            else:
                # Product description search
                with st.spinner("Searching by product description..."):
                    candidates = qa_agent.get_candidates_by_product(user_input.strip(), k=200)
                if not candidates.empty:
                    st.session_state.candidates = candidates
                    st.success(f"Found {len(candidates)} potential matches for '{user_input}'")
                else:
                    st.error("No matching products found. Try different keywords.")
            st.rerun()

    # Question-answer classification for partial/product
    if not st.session_state.candidates.empty and st.session_state.final_result is None:
        st.divider()
        col1, col2 = st.columns([2, 1])
        with col1:
            st.header("🎯 Classification in Progress")
            st.write(f"Initial query: **{st.session_state.initial_query}**")
        with col2:
            st.metric("Candidates Remaining", len(st.session_state.candidates))

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
                option_cols = st.columns(len(question["options"]))
                selected_option = None
                for idx, (col, option) in enumerate(zip(option_cols, question["options"])):
                    with col:
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

    # Final result
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
            st.write(f"**Indent Level:** {details['Indent']}")
            st.write(f"**Description:** {details['Description']}")
            st.write(f"**Specifications:** {details['Specifications']}")
        with col2:
            st.subheader("Duty Information")
            st.write(f"**Unit of Quantity:** {details['Unit of Quantity']}")
            st.write(f"**General Rate:** {details['General Rate of Duty']}")
            st.write(f"**Special Rate:** {details['Special Rate of Duty']}")
            st.write(f"**Column 2 Rate:** {details['Column 2 Rate of Duty']}")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.session_state.question_history:
            st.subheader("Classification Path")
            for i, qa in enumerate(st.session_state.question_history, 1):
                st.write(f"{i}. {qa['question']} → **{qa['answer']}**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 New Search", type="primary"):
                reset_session()
                st.rerun()
        with col2:
            if st.button("📋 Copy HTS Code"):
                st.write(f"HTS Code copied: `{details['HTS Number']}`")
                st.toast("HTS Code copied to clipboard!", icon="✅")
else:
    st.error("⚠️ No processed data found. Please run the pipeline from the sidebar first.")
