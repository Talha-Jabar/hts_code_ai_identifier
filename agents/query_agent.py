# agents/query_agent.py
# Python 3.13 compatible implementation
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
        if len(candidates) <= 1:
            return None

        for spec_col in self.spec_cols:
            spec_values = candidates[spec_col].apply(lambda x: x.strip() if x else "")
            unique_values = [v for v in spec_values.unique() if v]
            if len(unique_values) <= 1:
                continue

            value_counts = Counter(spec_values[spec_values != ""])
            if len(value_counts) > 1:
                sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
                if len(sorted_values) == 2:
                    main_value = sorted_values[0][0]
                    return {
                        "id": 1,
                        "question": f"Is it {self._format_question_text(main_value)}?",
                        "spec_column": spec_col,
                        "options": [
                            {
                                "label": "Yes",
                                "filter_value": main_value,
                                "expected_count": sorted_values[0][1]
                            },
                            {
                                "label": "No",
                                "filter_value": None,
                                "expected_count": sum(count for val, count in sorted_values[1:])
                            }
                        ]
                    }
                else:
                    options = []
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
                            other_values = [val for val, _ in sorted_values[3:]]
                            options.append({
                                "label": "Other",
                                "filter_value": other_values,
                                "expected_count": other_count
                            })
                    else:
                        for value, count in sorted_values:
                            options.append({
                                "label": self._format_option_text(value),
                                "filter_value": value,
                                "expected_count": count
                            })

                    question_text = self._generate_question_text(spec_col, unique_values, candidates)
                    return {
                        "id": 1,
                        "question": question_text,
                        "spec_column": spec_col,
                        "options": options
                    }

        return None

    def filter_candidates_by_answer(self, candidates: pd.DataFrame,
                                   question: Dict, selected_option: Dict) -> pd.DataFrame:
        spec_col = question["spec_column"]
        filter_value = selected_option["filter_value"]

        if filter_value is None:
            main_value = question["options"][0]["filter_value"]
            return candidates[candidates[spec_col] != main_value]
        elif isinstance(filter_value, list):
            return candidates[candidates[spec_col].isin(filter_value)]
        else:
            return candidates[candidates[spec_col] == filter_value]

    def _format_question_text(self, value: str) -> str:
        value = value.lower().strip()
        if value.startswith("other"):
            return value
        if value[0] in 'aeiou':
            return f"an {value}"
        elif value not in ['purebred', 'breeding', 'imported', 'live']:
            return f"a {value}"
        return value

    def _format_option_text(self, value: str) -> str:
        return value.strip().capitalize() if value else "Not specified"

    def _generate_question_text(self, spec_col: str, values: List[str], candidates: pd.DataFrame) -> str:
        level_num = int(spec_col.split("_")[-1])
        values_lower = [v.lower() for v in values if v]

        if any('imported' in v for v in values_lower):
            return "What is the import status?"
        elif any('purebred' in v or 'breeding' in v for v in values_lower):
            return "What is the breeding type?"
        elif any('male' in v or 'female' in v for v in values_lower):
            return "What is the gender?"
        elif any('live' in v for v in values_lower):
            return "Is it live or processed?"
        elif any('whole' in v or 'cut' in v or 'pieces' in v for v in values_lower):
            return "What is the form?"
        elif any('fresh' in v or 'frozen' in v or 'dried' in v for v in values_lower):
            return "What is the preservation method?"
        elif level_num == 1:
            return "What type of product is it?"
        elif level_num == 2:
            return "What specific variety?"
        else:
            return f"Select the specific characteristic:"

    def get_candidate_details(self, candidate: pd.Series) -> Dict:
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
