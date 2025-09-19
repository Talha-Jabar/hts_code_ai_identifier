# ---------------------------
# File: app/services/duty_service.py
# ---------------------------
# This module attempts to use your existing DutyCalculator (from services.duty_calculator)
# falling back to a small internal implementation if not present.

from typing import Dict, Any, Optional

UserDutyCalculator: Optional[type] = None  # always bound for Pylance
_HAS_USER_DC = False

try:
    from services.duty_calculator import DutyCalculator as UserDutyCalculator
    _HAS_USER_DC = True
except Exception:
    # If the import fails, we fall back to internal logic
    pass


class DutyService:
    def __init__(self, result_payload: Dict[str, Any]):
        # result_payload should be the payload/dict describing the HTS candidate
        self.payload = result_payload

    def calculate(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer user's DutyCalculator if available to keep behaviour identical to Streamlit app
        if _HAS_USER_DC and UserDutyCalculator is not None:
            dc = UserDutyCalculator(self.payload)
            return dc.calculate_landed_cost(form_data)

        # Otherwise, a simple fallback calculation (clear and commented so you can replace it)
        base_value = float(form_data.get('base_value', 0.0))
        metal_percent = float(form_data.get('metal_percent', 0.0))
        has_exclusion = bool(form_data.get('has_exclusion', False))

        # Determine duty rate from payload (try Special > General > Column2)
        def parse_pct(s):
            try:
                # Accept strings like '3.5%' or '3.5' or 'Free'
                if not s:
                    return 0.0
                s = str(s).strip()
                if s.lower() in ['free', 'n/a']:
                    return 0.0
                if s.endswith('%'):
                    s = s[:-1]
                return float(s)
            except Exception:
                return 0.0

        special = parse_pct(self.payload.get('Special_Rate_of_Duty', '') or '')
        general = parse_pct(self.payload.get('General_Rate_of_Duty', '') or '')
        column2 = parse_pct(self.payload.get('Column_2_Rate_of_Duty', '') or '')

        duty_rate = (
            special if special > 0
            else general if general > 0
            else column2 if column2 > 0
            else 0.0
        )
        base_duty = base_value * (duty_rate / 100.0)

        # metal surcharge (dummy): 0.2% of base_value per 1% metal content
        metal_surcharge = base_value * (metal_percent / 100.0) * 0.002

        # exclusion reduces duty by a fixed amount e.g., 10% of base_duty (dummy)
        exclusion_reduction = base_duty * 0.10 if has_exclusion else 0.0

        total_duties = max(0.0, base_duty + metal_surcharge - exclusion_reduction)

        # MPF/HMF fees (dummy): 0.35% of base_value
        mpf_hmf = base_value * 0.0035

        landed = base_value + total_duties + mpf_hmf

        notes = []
        if not _HAS_USER_DC:
            notes.append(
                "Fallback calculation used. Replace with services.duty_calculator.DutyCalculator for exact behavior."
            )

        return {
            'base_value': base_value,
            'base_duty': round(base_duty, 2),
            'metal_surcharge': round(metal_surcharge, 2),
            'exclusion_reduction': round(exclusion_reduction, 2),
            'total_duties': round(total_duties, 2),
            'mpf_hmf_fees': round(mpf_hmf, 2),
            'landed_cost': round(landed, 2),
            'rate_category': (
                'special' if special > 0
                else 'general' if general > 0
                else 'column2' if column2 > 0
                else 'none'
            ),
            'duty_rate_pct': duty_rate,
            'calculation_notes': notes,
        }
