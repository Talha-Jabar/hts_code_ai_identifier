import pandas as pd
import requests
import os
import warnings
from dotenv import load_dotenv
load_dotenv()
warnings.filterwarnings("ignore")

token = os.getenv("ACCESS_TOKEN_GOV")
baseUrl = 'https://datawebws.usitc.gov/dataweb'
headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Authorization": f"Bearer {token}"
}
def preprocess_tariff_programs()-> pd.DataFrame:
    resp = requests.get(f"{baseUrl}/api/v2/tariff/tariffProgramsLookup", headers=headers, verify=False)
    data = resp.json()
    rows = []
    for p in data.get('programs', []):
        code = p.get('code')
        desc = p.get('description')
        group = p.get('countriesgroups', {}).get('group_name', '')
        countries = p.get('countriesgroups', {}).get('countries', [])
        country_list = '; '.join(countries) if countries else ''
        rows.append({
            'tariff_program': code,
            'description': desc,
            'Group': group,
            'Countries': country_list
        })
    df = pd.DataFrame(rows)
    df['Countries'] = df.apply(
    lambda row: row['Group'] if pd.isna(row['Countries']) or str(row['Countries']).strip() == '' else row['Countries'],
    axis=1
    )

    return df




# if __name__ == "__main__":
#     preprocess_tariff_programs()
    














if __name__ == "__main__":
    preprocess_tariff_programs()







