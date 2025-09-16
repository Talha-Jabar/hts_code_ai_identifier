# agents/query_agent.py
# This module handles intelligent question generation based on specification hierarchy

from typing import List, Dict, Optional
import pandas as pd
from collections import Counter
class QueryAgent:
    def __init__(self, processed_csv_path: str):
        """Initialize the QueryAgent with processed CSV data."""
        self.df = pd.read_csv(processed_csv_path, dtype=str).fillna("")
        # Identify specification columns dynamically
        self.spec_cols: List[str] = [c for c in self.df.columns if c.startswith("Spec_Level_")]
        self.spec_cols = sorted(self.spec_cols, key=lambda x: int(x.split("_")[-1]))

        # Add normalized HTS Number column (digits only)
        self.df["HTS_Normalized"] = self.df["HTS Number"].str.replace(".", "", regex=False)

    def get_candidates_by_prefix(self, prefix: str) -> pd.DataFrame:
        clean_prefix = prefix.replace(".", "").strip()
        return self.df[self.df["HTS_Normalized"].str.startswith(clean_prefix)]

    def get_candidates_by_product(self, query: str, k: int = 200) -> pd.DataFrame:
        from utils import vectorstore
        hits = vectorstore.search_qdrant(query, k=k)
        indices = [
            int(h["payload"]["row_index"]) for h in hits if "row_index" in h["payload"]
        ]
        return self.df.iloc[indices] if indices else pd.DataFrame()

    def query_exact_hts(self, hts_code: str, k: int = 10) -> List[Dict]:
        """
        Search for an exact HTS code match in both DataFrame and Qdrant.
        Normalizes input and dataset for reliable matching.
        """
        from utils import vectorstore

        clean_code = hts_code.replace(".", "").strip()

        # Check DataFrame directly
        df_matches = self.df[self.df["HTS_Normalized"] == clean_code]
        if not df_matches.empty:
            results = []
            for _, row in df_matches.iterrows():
                results.append({
                    "payload": row.to_dict(),
                    "score": 1.0  # perfect match
                })
            return results

        # Fallback: query Qdrant
        hits = vectorstore.search_qdrant(query=clean_code, k=k, exact_hts=clean_code)
        return hits

    def generate_smart_question(self, candidates: pd.DataFrame) -> Optional[Dict]:
        """
        Generates a smart, multiple-choice question to narrow down candidates.
        It finds the first specification level with multiple options and poses a question,
        avoiding simple "Yes/No" questions and providing clearer choices.
        """
        if len(candidates) <= 1:
            return None

        for spec_col in self.spec_cols:
            # Clean up the values in the current specification column
            spec_values = candidates[spec_col].apply(lambda x: x.strip() if isinstance(x, str) else "")
            
            # Count occurrences of each unique, non-empty value
            value_counts = Counter(spec_values[spec_values != ""])

            # If there's more than one unique value, we can ask a question
            if len(value_counts) > 1:
                # Sort values by frequency, descending
                sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
                
                options = []
                # If there are many options, group less common ones under "Other"
                # to keep the UI clean. We'll show up to 3 most common options individually.
                if len(sorted_values) > 4: 
                    top_options = sorted_values[:3]
                    other_count = sum(count for _, count in sorted_values[3:])
                    
                    for value, count in top_options:
                        options.append({
                            "label": self._format_option_text(value),
                            "filter_value": value,
                            "expected_count": count
                        })
                    
                    if other_count > 0:
                        # "filter_value" for "Other" is a list of all remaining values
                        other_values = [val for val, _ in sorted_values[3:]]
                        options.append({
                            "label": "Other",
                            "filter_value": other_values,
                            "expected_count": other_count
                        })
                else:
                    # If there are 4 or fewer options, show all of them
                    for value, count in sorted_values:
                        options.append({
                            "label": self._format_option_text(value),
                            "filter_value": value,
                            "expected_count": count
                        })
                
                # Generate a meaningful question text based on the context
                question_text = self._generate_question_text(spec_col, [v[0] for v in sorted_values], candidates)
                
                return {
                    "id": 1,
                    "question": question_text,
                    "spec_column": spec_col,
                    "options": options
                }

        return None # No question could be generated

    def filter_candidates_by_answer(self, candidates: pd.DataFrame,
                                     question: Dict, selected_option: Dict) -> pd.DataFrame:
        """
        Filters the candidate DataFrame based on the user's selected answer.
        Handles both single value and list-of-values filtering (for "Other").
        """
        spec_col = question["spec_column"]
        filter_value = selected_option["filter_value"]

        # This case was for the old "No" option in binary questions.
        # It's less likely to be used now but is kept for robustness.
        if filter_value is None:
            main_value = question["options"][0]["filter_value"]
            return candidates[candidates[spec_col] != main_value]
        # This handles the "Other" option, where filter_value is a list of strings
        elif isinstance(filter_value, list):
            return candidates[candidates[spec_col].isin(filter_value)]
        # This is the standard case for a single selection
        else:
            return candidates[candidates[spec_col] == filter_value]

    def _format_option_text(self, value: str) -> str:
        """Formats the text for a question option button."""
        return value.strip().capitalize() if value else "Not specified"

    def _generate_question_text(self, spec_col: str, values: List[str], candidates: pd.DataFrame) -> str:
        """
        Generates a more semantic question text.
        It tries to find context from parent specification levels to frame the question
        in a more meaningful way than a generic prompt.
        """
        level_num = int(spec_col.split("_")[-1])

        # Attempt to find a descriptive parent context from a higher specification level.
        # This helps frame the question more specifically.
        if level_num > 1:
            parent_spec_col = f"Spec_Level_{level_num - 1}"
            if parent_spec_col in candidates.columns:
                # Find unique, non-empty parent descriptions for the current candidates
                parent_values = [v for v in candidates[parent_spec_col].unique() if v and v.strip()]
                
                # If there is exactly one common parent, use it to make the question more specific.
                if len(parent_values) == 1:
                    parent_text = parent_values[0].strip().rstrip(':')
                    return f"For '{parent_text}', which of the following applies?"

        # Fallback to keyword-based question generation if a unique parent isn't found
        values_lower = [v.lower() for v in values if v]

        if any('imported' in v for v in values_lower):
            return "What is the import status?"
        elif any('purebred' in v or 'breeding' in v for v in values_lower):
            return "What is the breeding type?"
        elif any('male' in v or 'female' in v for v in values_lower):
            return "What is the gender?"
        elif any('live' in v for v in values_lower):
            return "Is the product live or processed?"
        elif any('whole' in v or 'cut' in v or 'pieces' in v for v in values_lower):
            return "In what form is the product?"
        elif any('fresh' in v or 'frozen' in v or 'dried' in v for v in values_lower):
            return "What is its preservation state?"
        elif level_num == 1:
            return "What is the product category?"
        else:
            # A better generic fallback question
            return "Please select the most relevant characteristic:"

    def get_candidate_details(self, candidate: pd.Series) -> Dict:
        """Formats the details of a single HTS candidate for display."""
        specs = []
        for spec_col in self.spec_cols:
            value = candidate.get(spec_col, "")
            if value and value.strip():
                specs.append(value.strip())

        return {
            "HTS Number": candidate.get("HTS Number", ""),
            "Indent": candidate.get("Indent", ""),
            "Description": candidate.get("Description", ""),
            "Specifications": " > ".join(specs) if specs else "No specifications",
            "Unit of Quantity": candidate.get("Unit_of_Quantity", ""),
            "General Rate of Duty": candidate.get("General_Rate_of_Duty", ""),
            "Special Rate of Duty": candidate.get("Special_Rate_of_Duty", ""),
            "Column 2 Rate of Duty": candidate.get("Column_2_Rate_of_Duty", "")
        }