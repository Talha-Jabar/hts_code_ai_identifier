# agents/query_agent.py
# Python 3.13 compatible implementation
# This module handles intelligent question generation based on specification hierarchy

from typing import List, Dict, Optional, Tuple, Set
import pandas as pd
from collections import Counter
import json

class QueryAgent:
    def __init__(self, processed_csv_path: str):
        """Initialize the QueryAgent with processed CSV data."""
        self.df = pd.read_csv(processed_csv_path, dtype=str).fillna("")
        # Identify specification columns dynamically
        self.spec_cols: List[str] = [c for c in self.df.columns if c.startswith("Spec_Level_")]
        # Sort spec columns by level number to maintain hierarchy
        self.spec_cols = sorted(self.spec_cols, key=lambda x: int(x.split("_")[-1]))
        
    def get_candidates_by_prefix(self, prefix: str) -> pd.DataFrame:
        """
        Filter candidates by 4- or 6-digit prefix.
        
        Args:
            prefix: 4 or 6 digit HTS prefix (e.g., "0101" or "0101.21")
            
        Returns:
            DataFrame of matching candidates
        """
        # Remove dots for comparison if present
        clean_prefix = prefix.replace(".", "")
        return self.df[self.df["HTS Number"].str.replace(".", "").str.startswith(clean_prefix)]
    
    def get_candidates_by_product(self, query: str, k: int = 200) -> pd.DataFrame:
        """
        Semantic search candidates by product name using vectorstore.
        
        Args:
            query: Product description to search
            k: Number of top results to return
            
        Returns:
            DataFrame of matching candidates
        """
        from utils import vectorstore
        hits = vectorstore.search_qdrant(query, k=k)
        indices = [
            int(h["payload"]["row_index"]) for h in hits if "row_index" in h["payload"]
        ]
        return self.df.iloc[indices] if indices else pd.DataFrame()
    
    def query_exact_hts(self, hts_code: str, k: int = 10) -> List[Dict]:
        """
        Search for an exact HTS code match in Qdrant.
        
        Args:
            hts_code: Exact 10-digit HTS code
            k: Number of results to return
            
        Returns:
            List of matching results from Qdrant
        """
        from utils import vectorstore
        hits = vectorstore.search_qdrant(
            query=hts_code,
            k=k,
            exact_hts=hts_code
        )
        return hits
    
    def generate_smart_question(self, candidates: pd.DataFrame) -> Optional[Dict]:
        """
        Generate a single intelligent question based on the current candidates.
        This method analyzes the specification hierarchy to find the best
        distinguishing question.
        
        Args:
            candidates: Current candidate DataFrame
            
        Returns:
            Dictionary with question details or None if candidates <= 1
        """
        if len(candidates) <= 1:
            return None
            
        # Find the first spec level where candidates differ
        for spec_col in self.spec_cols:
            # Get unique non-empty values at this spec level
            spec_values = candidates[spec_col].apply(lambda x: x.strip() if x else "")
            unique_values = [v for v in spec_values.unique() if v]
            
            # Skip if all values are the same or empty
            if len(unique_values) <= 1:
                continue
                
            # Count occurrences of each value
            value_counts = Counter(spec_values[spec_values != ""])
            
            # If we have different values, create a question
            if len(value_counts) > 1:
                # Sort values by frequency (most common first)
                sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
                
                # Generate question based on the most common values
                if len(sorted_values) == 2:
                    # Binary choice - create Yes/No question
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
                                "filter_value": None,  # Will filter out the main_value
                                "expected_count": sum(count for val, count in sorted_values[1:])
                            }
                        ]
                    }
                else:
                    # Multiple choice question
                    # Group less common options if there are many
                    if len(sorted_values) > 4:
                        # Show top 3 options + "Other"
                        top_options = sorted_values[:3]
                        other_count = sum(count for _, count in sorted_values[3:])
                        
                        options = []
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
                                "filter_value": other_values,  # List of other values
                                "expected_count": other_count
                            })
                    else:
                        # Show all options
                        options = []
                        for value, count in sorted_values:
                            options.append({
                                "label": self._format_option_text(value),
                                "filter_value": value,
                                "expected_count": count
                            })
                    
                    # Determine question type based on spec level content
                    level_num = int(spec_col.split("_")[-1])
                    question_text = self._generate_question_text(spec_col, unique_values, candidates)
                    
                    return {
                        "id": 1,
                        "question": question_text,
                        "spec_column": spec_col,
                        "options": options
                    }
        
        # If no distinguishing spec level found, return None
        return None
    
    def filter_candidates_by_answer(self, candidates: pd.DataFrame, 
                                   question: Dict, selected_option: Dict) -> pd.DataFrame:
        """
        Filter candidates based on the user's answer to a question.
        
        Args:
            candidates: Current candidates DataFrame
            question: The question that was asked
            selected_option: The option selected by the user
            
        Returns:
            Filtered DataFrame of candidates
        """
        spec_col = question["spec_column"]
        filter_value = selected_option["filter_value"]
        
        if filter_value is None:
            # "No" option - exclude the main value
            main_value = question["options"][0]["filter_value"]
            return candidates[candidates[spec_col] != main_value]
        elif isinstance(filter_value, list):
            # "Other" option - include any of the listed values
            return candidates[candidates[spec_col].isin(filter_value)]
        else:
            # Specific value selected
            return candidates[candidates[spec_col] == filter_value]
    
    def _format_question_text(self, value: str) -> str:
        """
        Format a specification value for use in a question.
        Makes the text more readable and grammatically correct.
        
        Args:
            value: Raw specification value
            
        Returns:
            Formatted text for question
        """
        # Convert to lowercase and clean up
        value = value.lower().strip()
        
        # Handle common patterns
        if value.startswith("other"):
            return value  # Keep "other" as is
        
        # Add articles where appropriate
        if value[0] in 'aeiou':
            return f"an {value}"
        elif value not in ['purebred', 'breeding', 'imported', 'live']:
            return f"a {value}"
        
        return value
    
    def _format_option_text(self, value: str) -> str:
        """
        Format a specification value for use as an option label.
        
        Args:
            value: Raw specification value
            
        Returns:
            Formatted option label
        """
        # Capitalize first letter and clean up
        return value.strip().capitalize() if value else "Not specified"
    
    def _generate_question_text(self, spec_col: str, values: List[str], 
                               candidates: pd.DataFrame) -> str:
        """
        Generate appropriate question text based on the specification column and values.
        
        Args:
            spec_col: Specification column name
            values: Unique values in this column
            candidates: Current candidates for context
            
        Returns:
            Question text
        """
        level_num = int(spec_col.split("_")[-1])
        
        # Analyze the nature of the values to determine question type
        values_lower = [v.lower() for v in values if v]
        
        # Common question patterns based on content
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
        """
        Get formatted details for a single candidate.
        
        Args:
            candidate: Single row from DataFrame
            
        Returns:
            Dictionary with formatted candidate details
        """
        # Collect all non-empty specification levels
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