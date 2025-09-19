# ---------------------------
# File: app/services/query_service.py
# ---------------------------
from agents.query_agent import QueryAgent
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
import uuid


class QueryService:
    def __init__(self, processed_csv_path: Path):
        self.processed_csv_path = processed_csv_path
        self.qa_agent = QueryAgent(str(processed_csv_path))

    def build_session_from_candidates(self, candidates_df) -> Tuple[str, List[int]]:
        # Use original df indices so filtering later works with QueryAgent
        indices = list(candidates_df.index)
        session_id = uuid.uuid4().hex
        return session_id, indices

    def get_candidates_df(self, indices: List[int]):
        if not indices:
            # return empty DataFrame with same columns
            return self.qa_agent.df.iloc[0:0]
        return self.qa_agent.df.loc[indices]

    def make_question_for_indices(self, indices: List[int]):
        df = self.get_candidates_df(indices)
        q = self.qa_agent.generate_smart_question(df)
        return q

    def details_for_index(self, idx: int) -> Dict[str, Any]:
        row = self.qa_agent.df.loc[idx]
        if isinstance(row, type(self.qa_agent.df)):
            # If multiple rows are returned, select the first one
            row = row.iloc[0]
        
        assert isinstance(row, pd.Series)  # helps mypy/pyright
        return self.qa_agent.get_candidate_details(row)