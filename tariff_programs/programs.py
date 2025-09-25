# tariff_programs/programs.py
import time
import requests
import pandas as pd
from typing import Dict, Any, List

# ----------------------------
# CONFIG - put your token here
# ----------------------------
BASE_URL = "https://datawebws.usitc.gov/dataweb"
TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIyMDAzNTU3IiwianRpIjoiN2JmZDVkNzctMjY3NS00YmVkLTk2MjMtNWNkZTRhNjFiNDY0IiwiaXNzIjoiZGF0YXdlYiIsImlhdCI6MTc1ODc4NTY4MiwiZXhwIjoxNzc0MzM3NjgyfQ.gIoWATAbd6wjDH6lADybnCVPuh5OFIy0nE17oYqS38ucCK3TYpimtmtwgFeDe5fyxNHhOhtEdDFsI-3TKtgk4Q"
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Authorization": "Bearer " + TOKEN,
}

# ----------------------------
# Helper: POST with retries/backoff
# ----------------------------
def post_with_retries(url: str, payload: Dict[str, Any], max_retries: int = 6, timeout: int = 120):
    backoff = 1
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=HEADERS, verify=False, timeout=timeout)
        except requests.RequestException as e:
            print(f"[Attempt {attempt}] Network error: {e}. Sleeping {backoff}s and retrying.")
            time.sleep(backoff)
            backoff *= 2
            continue

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code in (429, 503):
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else backoff
            print(f"[Attempt {attempt}] HTTP {resp.status_code} from server. Waiting {wait}s before retry.")
            time.sleep(wait)
            backoff *= 2
            continue
        else:
            resp.raise_for_status()

    raise RuntimeError(f"Failed after {max_retries} attempts for {url}")


# ----------------------------
# Utility: parse DataWeb JSON -> DataFrame
# ----------------------------
def get_columns(column_groups: List[Dict[str, Any]], prev_cols=None):
    if prev_cols is None:
        columns = []
    else:
        columns = prev_cols
    for group in column_groups:
        if isinstance(group, dict) and 'columns' in group.keys():
            get_columns(group['columns'], columns)
        elif isinstance(group, dict) and 'label' in group.keys():
            columns.append(group['label'])
        elif isinstance(group, list):
            get_columns(group, columns)
    return columns


def get_data(row_groups: List[Dict[str, Any]]):
    data = []
    for row in row_groups:
        rowData = []
        for field in row['rowEntries']:
            rowData.append(field.get('value'))
        data.append(rowData)
    return data


# ----------------------------
# 1) Get list of import programs
# ----------------------------
def get_import_programs():
    url = BASE_URL + "/api/v2/query/getImportPrograms"
    payload = {"tradeType": "Import"}
    print("Fetching import programs list...")
    resp_json = post_with_retries(url, payload)
    options = resp_json.get("options", [])
    df = pd.DataFrame(options)
    return df


# ----------------------------
# 2) Per-program query: countries + HTS codes + descriptions
# ----------------------------
def get_countries_hts_for_program(program_value: str, years: List[str] = ["2023"]):
    url = BASE_URL + "/api/v2/report2/runReport"
    payload = {
        "savedQueryName": "",
        "savedQueryDesc": "",
        "isOwner": True,
        "runMonthly": False,
        "reportOptions": {"tradeType": "Import", "classificationSystem": "HTS"},
        "searchOptions": {
            "MiscGroup": {
                "extImportPrograms": {
                    "aggregation": "Aggregate CSC",
                    "extImportPrograms": [program_value],
                    "extImportProgramsExpanded": [],
                    "programsSelectType": "list"
                }
            },
            "countries": {
                "aggregation": "Break out Countries",
                "countries": [],
                "countriesExpanded": [],
                "countriesSelectType": "all",
                "countryGroups": {"systemGroups": [], "userGroups": []}
            },
            "commodities": {
                "aggregation": "Break out Commodities",
                "codeDisplayFormat": "BOTH",   # ✅ FIXED: get code + description
                "commodities": [],
                "commoditiesExpanded": [],
                "commoditiesManual": "",
                "commodityGroups": {"systemGroups": [], "userGroups": []},
                "commoditySelectType": "all",
                "granularity": "10"
            },
            "componentSettings": {
                "dataToReport": ["CONS_FIR_UNIT_QUANT"],
                "timeframeSelectType": "fullYears",
                "years": years
            }
        },
        "sortingAndDataFormat": {
            "DataSort": {"columnOrder": [], "fullColumnOrder": [], "sortOrder": []},
            "reportCustomizations": {
                "exportCombineTables": False,
                "showAllSubtotal": True,
                "subtotalRecords": "",
                "totalRecords": "20000",
                "exportRawData": False
            }
        }
    }

    resp_json = post_with_retries(url, payload)
    dto = resp_json.get("dto", {})
    tables = dto.get("tables", [])
    if not tables:
        return pd.DataFrame()

    column_groups = tables[0].get("column_groups", [])
    row_groups = tables[0].get("row_groups", [])
    if len(row_groups) == 0:
        return pd.DataFrame()

    cols = get_columns(column_groups)
    data = get_data(row_groups[0].get("rowsNew", []))
    df = pd.DataFrame(data, columns=cols)

    # Normalize column detection
    country_cols = [c for c in df.columns if "country" in c.lower()]
    commodity_cols = [c for c in df.columns if "commodity" in c.lower()]

    results = []
    for _, row in df.iterrows():
        country = row[country_cols[0]] if country_cols else None
        commodity = row[commodity_cols[0]] if commodity_cols else None

        hts_code, hts_desc = None, None
        if commodity:
            parts = commodity.split(" ", 1)
            hts_code = parts[0]
            hts_desc = parts[1] if len(parts) > 1 else ""

        results.append({
            "Country": country,
            "HTSCode": hts_code,
            "HTSDescription": hts_desc
        })

    return pd.DataFrame(results)


# ----------------------------
# MAIN driver
# ----------------------------
if __name__ == "__main__":
    # 1) Import programs list
    try:
        programs_df = get_import_programs()
        if not programs_df.empty:
            programs_df.to_excel("import_programs.xlsx", index=False)
            print("Saved import programs list -> import_programs.xlsx")
        else:
            print("No programs returned from getImportPrograms.")
    except Exception as e:
        print("Failed to fetch import programs:", e)
        raise

    # 2) Per-program queries
    programs = programs_df.to_dict("records")
    rows = []
    print("Starting per-program queries for Countries + HTS Codes + Descriptions...")
    for idx, p in enumerate(programs, start=1):
        val = p.get("value")
        label = p.get("label") or p.get("name") or ""
        if not val:
            continue
        print(f"[{idx}/{len(programs)}] Querying Program='{label}' (value={val}) ...")
        try:
            df = get_countries_hts_for_program(val, years=["2023"])
        except Exception as e:
            print(f"  -> Error for program {val}: {e}. Skipping.")
            df = pd.DataFrame()
        if df.empty:
            rows.append({"Program": label or val, "ProgramValue": val,
                         "Country": None, "HTSCode": None, "HTSDescription": None})
        else:
            for _, r in df.iterrows():
                rows.append({
                    "Program": label or val,
                    "ProgramValue": val,
                    "Country": r.get("Country"),
                    "HTSCode": r.get("HTSCode"),
                    "HTSDescription": r.get("HTSDescription")
                })
        time.sleep(1.0)

    final_df = pd.DataFrame(rows)
    final_df.to_excel("tariff_program_country_hts_mapping.xlsx", index=False)
    print(f"Saved Program↔Country↔HTS mapping -> tariff_program_country_hts_mapping.xlsx ({len(final_df)} rows)")
