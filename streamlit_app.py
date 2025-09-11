# streamlit_app.py

# Implements intelligent question-based narrowing of HTS candidates

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

# Custom CSS for better UI
st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
        margin-top: 10px;
    }
    .candidate-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        padding: 20px;
        border-radius: 10px;
        border: 2px solid #c3e6cb;
    }
    </style>
""", unsafe_allow_html=True)

# Application header
st.title("🔍 HTS Intelligent Classification Assistant")
st.markdown("""
**Smart HTS Code Finder** - Uses intelligent questioning to narrow down the exact HTS code based on product specifications.
This system analyzes the specification hierarchy dynamically to ask the most relevant questions.
""")

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.candidates = pd.DataFrame()
    st.session_state.current_question = None
    st.session_state.question_history = []
    st.session_state.mode = None
    st.session_state.initial_query = ""
    st.session_state.final_result = None
    st.session_state.question_count = 0

def reset_session():
    """Reset the session state for a new query (but keep mode)."""
    st.session_state.candidates = pd.DataFrame()
    st.session_state.current_question = None
    st.session_state.question_history = []
    # keep st.session_state.mode
    st.session_state.initial_query = ""
    st.session_state.final_result = None
    st.session_state.question_count = 0

# Sidebar for pipeline management
with st.sidebar:
    st.header("⚙️ System Management")

    # Check if processed CSV exists
    if not PROCESSED_CSV.exists():
        st.warning("Processed CSV not found. Please run the pipeline first.")
    else:
        st.success("✅ System ready")

    # Pipeline runner
    if st.button("🔄 Run Full Pipeline", help="Download, preprocess, and embed HTS data"):
        orchestrator = HTSOrchestrator(BASE)
        with st.spinner("Running pipeline... This may take several minutes."):
            progress_bar = st.progress(0)

            # Step 1: Fetch
            progress_bar.progress(33, text="Fetching latest HTS data...")
            result = orchestrator.run_full_pipeline()

            # Step 2: Process
            progress_bar.progress(66, text="Processing and embedding data...")
            processed_path = result["processed"]

            # Step 3: Build vectorstore
            indexed = build_vectorstore(processed_path, overwrite=True)
            progress_bar.progress(100, text="Complete!")

        st.success(f"✅ Pipeline complete! Indexed {indexed} records.")
        st.info(f"Processed file: {processed_path}")
        time.sleep(2)
        st.rerun()

    st.divider()

    # Session info
    st.header("📊 Current Session")
    if not st.session_state.candidates.empty:
        st.metric("Candidates Remaining", len(st.session_state.candidates))
        st.metric("Questions Asked", st.session_state.question_count)
    else:
        st.info("No active session")

    if st.button("🔄 Reset Session"):
        reset_session()
        st.rerun()

    # Debug info (remove later if not needed)
    st.write("DEBUG: Current Mode →", st.session_state.mode)

# Main content area
if PROCESSED_CSV.exists():
    # Initialize QueryAgent
    qa_agent = QueryAgent(str(PROCESSED_CSV))

    # Query mode selection
    st.header("Select Query Mode")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📋 Exact 10-digit HTS", use_container_width=True):
            reset_session()
            st.session_state.mode = "exact"
            st.rerun()

    with col2:
        if st.button("🔢 Partial HTS (4/6 digit)", use_container_width=True):
            reset_session()
            st.session_state.mode = "partial"
            st.rerun()

    with col3:
        if st.button("📦 Product Description", use_container_width=True):
            reset_session()
            st.session_state.mode = "product"
            st.rerun()

    st.divider()

    # Mode-specific interface
    if st.session_state.mode == "exact":
        st.header("🔍 Exact HTS Code Search")
        
        hts_input = st.text_input(
            "Enter complete 10-digit HTS code:",
            placeholder="e.g., 0101210010 or 0101.21.00.10",
            key="exact_input"
        )
        
        if st.button("Search", type="primary"):
            if hts_input:
                with st.spinner("Searching database..."):
                    results = qa_agent.query_exact_hts(hts_input.strip(), k=5)
                
                if results:
                    st.success(f"Found {len(results)} matching records")
                    for i, result in enumerate(results, 1):
                        payload = result["payload"]
                        score = result.get("score", 0)
                        
                        with st.expander(f"Result {i} - HTS: {payload.get('HTS Number', 'Unknown')} (Score: {score:.3f})"):
                            details = qa_agent.get_candidate_details(pd.Series(payload))
                            for key, value in details.items():
                                st.write(f"**{key}:** {value}")
                else:
                    st.warning("No exact matches found. Try a partial search instead.")


    elif st.session_state.mode == "partial":
        st.header("🔢 Partial HTS Code Search")

        partial_input = st.text_input(
            "Enter 4 or 6 digit HTS prefix:",
            placeholder="e.g., 0101 or 0101.21",
            key="partial_input",
            help="Enter the first 4 or 6 digits of the HTS code"
        )

        if partial_input:
            clean_input = partial_input.replace(".", "").strip()
            if len(clean_input) in [4, 6]:
                if st.button("Start Classification", type="primary"):
                    with st.spinner("Finding candidates..."):
                        candidates = qa_agent.get_candidates_by_prefix(partial_input)

                    if not candidates.empty:
                        st.session_state.candidates = candidates
                        st.session_state.initial_query = partial_input
                        st.success(f"Found {len(candidates)} candidates for prefix '{partial_input}'")
                        st.rerun()
                    else:
                        st.error(f"No HTS codes found starting with '{partial_input}'")
            else:
                st.warning("Please enter exactly 4 or 6 digits (e.g., '0101' or '010121')")

    elif st.session_state.mode == "product":
        st.header("📦 Product Description Search")

        product_input = st.text_input(
            "Enter product description:",
            placeholder="e.g., horse, computer, textile",
            key="product_input"
        )

        if st.button("Start Classification", type="primary"):
            if product_input:
                with st.spinner("Searching for matching products..."):
                    candidates = qa_agent.get_candidates_by_product(product_input.strip(), k=200)

                if not candidates.empty:
                    st.session_state.candidates = candidates
                    st.session_state.initial_query = product_input
                    st.success(f"Found {len(candidates)} potential matches for '{product_input}'")
                    st.rerun()
                else:
                    st.error("No matching products found. Try different keywords.")

    # Question-Answer Interface (for partial and product modes)
    if not st.session_state.candidates.empty and st.session_state.final_result is None:
        st.divider()

        # Display current status
        col1, col2 = st.columns([2, 1])
        with col1:
            st.header("🎯 Classification in Progress")
            st.write(f"Initial query: **{st.session_state.initial_query}**")
        with col2:
            st.metric("Candidates Remaining", len(st.session_state.candidates))

        # Check if we have a single candidate
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

                progress_cols = st.columns(3)
                with progress_cols[0]:
                    st.info(f"Question {st.session_state.question_count + 1}")
                with progress_cols[1]:
                    st.info(f"Analyzing: {question['spec_column'].replace('_', ' ').title()}")

                st.subheader(question["question"])

                option_cols = st.columns(len(question["options"]))

                selected_option = None
                for idx, (col, option) in enumerate(zip(option_cols, question["options"])):
                    with col:
                        if st.button(
                            option["label"],
                            key=f"opt_{idx}",
                            use_container_width=True,
                            help=f"Expected candidates: {option['expected_count']}"
                        ):
                            selected_option = option

                if selected_option:
                    filtered = qa_agent.filter_candidates_by_answer(
                        st.session_state.candidates,
                        question,
                        selected_option
                    )

                    st.session_state.candidates = filtered
                    st.session_state.question_history.append({
                        "question": question["question"],
                        "answer": selected_option["label"]
                    })
                    st.session_state.current_question = None
                    st.session_state.question_count += 1

                    st.rerun()

                if st.session_state.question_history:
                    with st.expander("Question History"):
                        for i, qa in enumerate(st.session_state.question_history, 1):
                            st.write(f"**Q{i}:** {qa['question']}")
                            st.write(f"**A{i}:** {qa['answer']}")

                with st.expander(f"Preview Top Candidates ({len(st.session_state.candidates)} total)"):
                    for idx, row in st.session_state.candidates.head(3).iterrows():
                        st.write(f"**{row['HTS Number']}** - {row['Description'][:100]}...")

    # Display final result
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
            st.write(f"Total questions answered: {len(st.session_state.question_history)}")

            for i, qa in enumerate(st.session_state.question_history, 1):
                st.write(f"{i}. {qa['question']} → **{qa['answer']}**")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔍 New Search", type="primary"):
                reset_session()
                st.session_state.mode = None
                st.rerun()
        with col2:
            if st.button("📋 Copy HTS Code"):
                st.write(f"HTS Code copied: `{details['HTS Number']}`")
                st.toast("HTS Code copied to clipboard!", icon="✅")

else:
    st.error("⚠️ No processed data found. Please run the pipeline from the sidebar first.")
