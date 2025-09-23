# utils/preprocessing.py
import re
import pandas as pd
from pathlib import Path

HTS_CODE_REGEX = re.compile(r"\b(\d{10})\b")

def flatten_hts_with_indent(input_path: Path, output_path: Path, max_levels: int = 10) -> Path:
    """
    Flatten HTS CSV into structured format:
      - Expand hierarchy into Spec_Level_1...Spec_Level_10
      - Inherit duty rates and unit of quantity from parents
    Returns path to saved CSV.
    """
    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]

    def extract_digits(s):
        return ''.join(re.findall(r'\d', str(s))) if s else ''

    current_levels = [''] * (max_levels + 1)
    duty_per_level = [ {"General":"", "Special":"", "Column2":"", "Unit":""} for _ in range(max_levels+1) ]

    out_rows = []

    for _, row in df.iterrows():
        desc = str(row.get('Description','')).strip()
        try:
            indent = int(str(row.get('Indent','')).strip())
        except Exception:
            indent = None

        # Clamp indent
        if indent is not None:
            if indent > max_levels:
                indent = max_levels
            elif indent < 0:
                indent = 0

        # Update hierarchy levels
        if indent is not None and desc:
            current_levels[indent] = desc
            # clear deeper levels
            for i in range(indent+1, max_levels+1):
                current_levels[i] = ""
                # ✨ FIX: Clear duty rates for deeper levels as well
                duty_per_level[i] = {"General":"", "Special":"", "Column2":"", "Unit":""}

        # Duty + unit values from this row
        gen = str(row.get("General Rate of Duty", "")).strip()
        spec = str(row.get("Special Rate of Duty", "")).strip()
        col2 = str(row.get("Column 2 Rate of Duty", "")).strip()
        unit = str(row.get("Unit of Quantity", "")).strip()

        if indent is not None:
            if gen: duty_per_level[indent]["General"] = gen
            if spec: duty_per_level[indent]["Special"] = spec
            if col2: duty_per_level[indent]["Column2"] = col2
            if unit: duty_per_level[indent]["Unit"] = unit

        def eff(key):
            if indent is None:
                return ""
            for lvl in range(indent, -1, -1):
                val = duty_per_level[lvl][key]
                if val:
                    return val
            return ""

        raw_hts = row.get('HTS Number','')
        digits = extract_digits(raw_hts)

        # Only output full 10-digit HTS rows
        if len(digits) >= 10:
            out = {
                "HTS Number": raw_hts,
                "HTS_Digits": digits[:10],
                "Indent": indent if indent is not None else "",
                "Description": current_levels[0]
            }
            for lvl in range(1, max_levels+1):
                out[f"Spec_Level_{lvl}"] = current_levels[lvl]

            out["Unit_of_Quantity"] = eff("Unit")
            out["General_Rate_of_Duty"] = eff("General")
            out["Special_Rate_of_Duty"] = eff("Special")
            out["Column_2_Rate_of_Duty"] = eff("Column2")

            out_rows.append(out)

    out_df = pd.DataFrame(out_rows)

    # Drop fully empty columns
    if not out_df.empty:
        out_df = out_df.loc[:, (out_df != "").any(axis=0)]

        # Compose 'text' column based only on Spec_Level_* columns (for embeddings / LLM)
        spec_cols = [c for c in out_df.columns if c.startswith("Spec_Level_")]
        def build_text_from_specs(r):
            parts = []
            for c in spec_cols:
                v = str(r.get(c, "")).strip()
                if v:
                    parts.append(v)
            # include HTS prefix for context
            hts = r.get("HTS_Digits", "")
            prefix = hts[:6] if hts else ""
            prefix4 = hts[:4] if hts else ""
            meta = []
            if prefix4:
                meta.append(f"prefix4:{prefix4}")
            if prefix:
                meta.append(f"prefix6:{prefix}")
            if meta:
                return " | ".join(meta + parts)
            return " | ".join(parts)
        out_df["text"] = out_df.apply(build_text_from_specs, axis=1)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    return out_path