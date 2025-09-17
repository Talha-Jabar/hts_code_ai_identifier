# services/duty_calculator.py

import re
import pandas as pd
from typing import Dict, Any, Tuple
from utils.countries import COLUMN_2_COUNTRIES

class DutyCalculator:
    """
    Handles all logic related to calculating import duties and fees.
    """

    def __init__(self, hts_data: pd.Series):
        """
        Initializes the calculator with the data for a specific HTS code.
        """
        self.hts_data = hts_data

    def _parse_duty_rate(self, rate_string: str) -> Dict[str, Any]:
        """
        Parses a duty rate string (e.g., "5%", "Free", "2.5¢/kg") into a structured format.
        
        Returns:
            A dictionary with 'type', 'rate', and optional 'unit'.
        """
        rate_string = rate_string.strip()
        
        if "free" in rate_string.lower():
            return {"type": "free", "rate": 0.0}

        # Look for a percentage value
        percent_match = re.search(r"(\d+\.?\d*)\s*%", rate_string)
        if percent_match:
            return {"type": "percentage", "rate": float(percent_match.group(1))}
            
        # Look for a cents-per-unit value (e.g., 2.5¢/kg)
        unit_match = re.search(r"(\d+\.?\d*)\s*¢\s*/\s*(\w+)", rate_string)
        if unit_match:
            # Note: This calculation requires weight/quantity, which we don't have.
            # We'll flag this as an unsupported type for now.
            return {"type": "unit_based", "rate": float(unit_match.group(1)), "unit": unit_match.group(2)}

        # Handle simple numeric rates (often in Column 2) as percentages
        try:
            return {"type": "percentage", "rate": float(rate_string)}
        except ValueError:
            pass
            
        return {"type": "unsupported", "text": rate_string}

    def _get_applicable_rate_info(self, country_iso: str) -> Tuple[str, str]:
        """
        Determines which duty rate (General, Special, Column 2) applies for a given country.
        
        Returns:
            A tuple containing the rate category name and the raw rate string.
        """
        # 1. Check for Column 2 countries first
        if country_iso in COLUMN_2_COUNTRIES:
            return "Column 2", self.hts_data.get("Column_2_Rate_of_Duty", "")

        # 2. Check for Special rate countries
        special_rate_str = self.hts_data.get("Special_Rate_of_Duty", "")
        # Find all 2-letter ISO codes in parentheses
        special_countries = re.findall(r"\((\w{2})\)", special_rate_str)
        if country_iso in special_countries:
            return "Special", special_rate_str
            
        # 3. Default to General rate
        return "General", self.hts_data.get("General_Rate_of_Duty", "")

    def calculate_landed_cost(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates the total landed cost based on user inputs.

        Args:
            form_data: A dictionary of user inputs from the Streamlit form.

        Returns:
            A dictionary containing the detailed cost breakdown.
        """
        base_value = form_data.get("base_value", 0.0)
        country_iso = form_data.get("country_iso", "")
        transport_mode = form_data.get("transport_mode", "Ocean")
        has_exclusion = form_data.get("has_exclusion", False)
        metal_percent = form_data.get("metal_percent", 0.0)

        # Step 1: Determine the applicable duty rate
        rate_category, raw_rate_str = self._get_applicable_rate_info(country_iso)
        parsed_rate = self._parse_duty_rate(raw_rate_str)
        
        # Step 2: Calculate base duty
        base_duty = 0.0
        duty_rate_pct = 0.0
        calculation_notes = []

        if parsed_rate["type"] == "percentage":
            duty_rate_pct = parsed_rate["rate"]
            base_duty = base_value * (duty_rate_pct / 100.0)
        elif parsed_rate["type"] == "free":
            duty_rate_pct = 0.0
            base_duty = 0.0
        else: # Handle unsupported or unit-based rates
            calculation_notes.append(
                f"⚠️ Automated duty calculation is not supported for this rate type ('{parsed_rate.get('text', 'N/A')}'). Duty is estimated as $0."
            )

        # Step 3: Apply dummy adjustments (as per requirements)
        # a) Metal Content Adjustment
        metal_surcharge = 0.0
        if metal_percent > 0:
            # Dummy logic: Add a 5% tariff on the value proportional to the metal content
            metal_surcharge = base_value * (metal_percent / 100.0) * 0.05 
            calculation_notes.append(
                f"An additional ${metal_surcharge:,.2f} has been added for {metal_percent}% metal content."
            )

        # b) Exclusion Code Adjustment
        exclusion_reduction = 0.0
        if has_exclusion:
            # Dummy logic: Reduce the calculated duty by 50% if an exclusion applies
            pre_exclusion_duty = base_duty + metal_surcharge
            exclusion_reduction = pre_exclusion_duty * 0.50
            calculation_notes.append(
                f"A reduction of ${exclusion_reduction:,.2f} has been applied due to a Chapter 99 exclusion."
            )

        total_duties = base_duty + metal_surcharge - exclusion_reduction
        
        # Step 4: Calculate MPF/HMF fees based on transport mode (dummy values)
        mpf_hmf = 0.0
        if transport_mode == "Ocean":
            # MPF ($35) + HMF ($13) - Example for China
            mpf_hmf = 48.00
        else: # Air, Rail, Truck
            # MPF only ($35) - Example for China
            mpf_hmf = 35.00
            
        # Step 5: Calculate Total Landed Cost
        landed_cost = base_value + total_duties + mpf_hmf

        return {
            "base_value": base_value,
            "rate_category": rate_category,
            "duty_rate_pct": duty_rate_pct,
            "base_duty": base_duty,
            "metal_surcharge": metal_surcharge,
            "exclusion_reduction": exclusion_reduction,
            "total_duties": total_duties,
            "mpf_hmf_fees": mpf_hmf,
            "landed_cost": landed_cost,
            "calculation_notes": calculation_notes
        }