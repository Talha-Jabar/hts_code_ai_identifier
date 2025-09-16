# utils/llm_utils.py
# Simplified to remove generic question generation - now handled by QueryAgent

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from typing import List, Dict, Optional
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
def get_llm(temperature: float = 0.0, max_tokens: int = 500):
    """
    Get configured LLM instance.
    
    Args:
        temperature: Sampling temperature (0.0 for deterministic)
        max_tokens: Maximum tokens in response
        
    Returns:
        Configured ChatOpenAI instance
    """
    return ChatOpenAI(
        temperature=temperature,
        max_completion_tokens=max_tokens,
        model="gpt-4o-mini"  # You can change to gpt-4 if needed
    )

def extract_hts_features(description: str) -> Dict:
    """
    Extract key features from a product description for HTS classification.
    
    Args:
        description: Product description text
        
    Returns:
        Dictionary of extracted features
    """
    template = """
    You are an expert in HTS (Harmonized Tariff Schedule) classification.
    
    Analyze this product description and extract key features relevant to HTS classification:
    
    Product: {description}
    
    Return a JSON object with these fields:
    - material: Primary material composition
    - form: Physical form (whole, cut, pieces, powder, etc.)
    - processing: Processing state (raw, cooked, frozen, dried, etc.)
    - use: Intended use or application
    - origin: Animal, vegetable, mineral, synthetic
    - special_features: List of any special characteristics
    
    Return ONLY valid JSON, no additional text.
    """
    
    prompt = PromptTemplate(input_variables=["description"], template=template)
    llm = get_llm(temperature=0.0)
    
    try:
        response = llm.predict(prompt.format(description=description))
        # Clean response and parse JSON
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.endswith("```"):
            response = response[:-3]
        return json.loads(response)
    except Exception as e:
        print(f"Error extracting features: {e}")
        return {
            "material": "unknown",
            "form": "unknown",
            "processing": "unknown",
            "use": "general",
            "origin": "unknown",
            "special_features": []
        }

def validate_hts_code(hts_code: str) -> bool:
    """
    Validate if a string is a valid HTS code format.
    
    Args:
        hts_code: HTS code string to validate
        
    Returns:
        True if valid HTS format, False otherwise
    """
    # Remove dots and spaces
    clean_code = hts_code.replace(".", "").replace(" ", "")
    
    # Check if it's 10 digits
    if len(clean_code) != 10:
        return False
    
    # Check if all characters are digits
    if not clean_code.isdigit():
        return False
    
    return True

def format_hts_code(hts_code: str) -> str:
    """
    Format an HTS code in the standard format: XXXX.XX.XX.XX
    
    Args:
        hts_code: Raw HTS code string
        
    Returns:
        Formatted HTS code string
    """
    # Remove any existing formatting
    clean_code = hts_code.replace(".", "").replace(" ", "").replace("-", "")
    
    # Pad with zeros if needed
    if len(clean_code) < 10:
        clean_code = clean_code.ljust(10, '0')
    elif len(clean_code) > 10:
        clean_code = clean_code[:10]
    
    # Format as XXXX.XX.XX.XX
    if len(clean_code) == 10:
        return f"{clean_code[:4]}.{clean_code[4:6]}.{clean_code[6:8]}.{clean_code[8:10]}"
    
    return hts_code

def compare_specifications(spec1: str, spec2: str) -> float:
    """
    Compare two specification strings and return similarity score.
    Used for intelligent question generation.
    
    Args:
        spec1: First specification string
        spec2: Second specification string
        
    Returns:
        Similarity score between 0 and 1
    """
    if not spec1 or not spec2:
        return 0.0
    
    # Simple word overlap similarity
    words1 = set(spec1.lower().split())
    words2 = set(spec2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

def generate_clarifying_questions(spec_text: str, max_questions: int = 10) -> List[Dict]:
    """
    DEPRECATED: This function is kept for backward compatibility.
    The QueryAgent now handles intelligent question generation.
    
    Args:
        spec_text: Specification text (not used)
        max_questions: Maximum questions (not used)
        
    Returns:
        Empty list - actual question generation is in QueryAgent
    """
    # This function is deprecated but kept to avoid breaking imports
    # The intelligent question generation is now handled by QueryAgent.generate_smart_question()
    return []

def analyze_candidate_distribution(candidates_df) -> Dict:
    """
    Analyze the distribution of candidates across specification levels.
    Helps in determining the best questions to ask.
    
    Args:
        candidates_df: DataFrame of candidate HTS codes
        
    Returns:
        Dictionary with distribution analysis
    """
    analysis = {
        "total_candidates": len(candidates_df),
        "spec_diversity": {},
        "recommended_approach": ""
    }
    
    # Analyze each specification level
    spec_cols = [c for c in candidates_df.columns if c.startswith("Spec_Level_")]
    
    for col in spec_cols:
        unique_values = candidates_df[col].dropna().unique()
        if len(unique_values) > 0:
            analysis["spec_diversity"][col] = {
                "unique_values": len(unique_values),
                "values": list(unique_values)[:5],  # Top 5 values
                "coverage": len(candidates_df[col].dropna()) / len(candidates_df)
            }
    
    # Determine recommended approach
    if len(candidates_df) <= 5:
        analysis["recommended_approach"] = "Direct selection - few candidates"
    elif analysis["spec_diversity"]:
        # Find the level with best discrimination power
        best_level = max(
            analysis["spec_diversity"].items(),
            key=lambda x: x[1]["unique_values"] * x[1]["coverage"]
        )
        analysis["recommended_approach"] = f"Start with {best_level[0]}"
    else:
        analysis["recommended_approach"] = "Manual review needed"
    
    return analysis