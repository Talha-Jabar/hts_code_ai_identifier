# database/convert_to_json.py
"""
Converts CSV and Excel files to JSON format for database import.
Handles HTS processed CSV and Tariff Programs Excel file.
"""
import sys
print(sys.executable)

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List
import re


class DataConverter:
    """
    Converts HTS CSV and Tariff Programs Excel to JSON format.
    Prepares data for database insertion with proper structure.
    """
    
    def __init__(self, base_dir: Path = None):
        """
        Initialize converter with base directory.
        
        Args:
            base_dir: Base directory of the project. Defaults to current working directory.
        """
        self.base_dir = base_dir or Path.cwd()
        self.data_dir = self.base_dir / "data"
        self.json_dir = self.data_dir / "json"
        
        # Create json directory if it doesn't exist
        self.json_dir.mkdir(parents=True, exist_ok=True)
    
    def convert_hts_csv_to_json(self, csv_path: Path = None) -> Path:
        """
        Converts HTS processed CSV to JSON format.
        
        Args:
            csv_path: Path to hts_processed.csv. Defaults to data/processed/hts_processed.csv
        
        Returns:
            Path to the generated JSON file
        """
        # Default path if not provided
        if csv_path is None:
            csv_path = self.data_dir / "processed" / "hts_processed.csv"
        
        if not csv_path.exists():
            raise FileNotFoundError(f"HTS CSV file not found at: {csv_path}")
        
        print(f"Reading HTS CSV from: {csv_path}")
        
        # Read CSV file
        df = pd.read_csv(csv_path, dtype=str).fillna("")
        
        # Process each row to create proper structure
        hts_records = []
        for idx, row in df.iterrows():
            # Extract prefix codes for indexing
            hts_digits = row.get('HTS_Digits', '')
            prefix4 = hts_digits[:4] if len(hts_digits) >= 4 else ''
            prefix6 = hts_digits[:6] if len(hts_digits) >= 6 else ''
            
            record = {
                'hts_number': row.get('HTS Number', ''),
                'hts_digits': hts_digits,
                'indent': row.get('Indent', ''),
                'description': row.get('Description', ''),
                'spec_level_1': row.get('Spec_Level_1', ''),
                'spec_level_2': row.get('Spec_Level_2', ''),
                'spec_level_3': row.get('Spec_Level_3', ''),
                'spec_level_4': row.get('Spec_Level_4', ''),
                'spec_level_5': row.get('Spec_Level_5', ''),
                'spec_level_6': row.get('Spec_Level_6', ''),
                'spec_level_7': row.get('Spec_Level_7', ''),
                'spec_level_8': row.get('Spec_Level_8', ''),
                'spec_level_9': row.get('Spec_Level_9', ''),
                'spec_level_10': row.get('Spec_Level_10', ''),
                'unit_of_quantity': row.get('Unit_of_Quantity', ''),
                'general_rate_of_duty': row.get('General_Rate_of_Duty', ''),
                'special_rate_of_duty': row.get('Special_Rate_of_Duty', ''),
                'column_2_rate_of_duty': row.get('Column_2_Rate_of_Duty', ''),
                'text': row.get('text', ''),
                'prefix4': prefix4,
                'prefix6': prefix6
            }
            
            hts_records.append(record)
        
        # Save to JSON
        output_path = self.json_dir / "hts_codes.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(hts_records, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Converted {len(hts_records)} HTS records to JSON: {output_path}")
        return output_path
    
    def convert_tariff_programs_to_json(self, excel_path: Path = None) -> Path:
        """
        Converts Tariff Programs Excel to JSON format.
        
        Args:
            excel_path: Path to tariff_programs.xlsx. Defaults to data/tariff_programs.xlsx
        
        Returns:
            Path to the generated JSON file
        """
        # Default path if not provided
        if excel_path is None:
            excel_path = self.data_dir / "tariff_programs" /"tariff_programs.xlsx"
        
        if not excel_path.exists():
            raise FileNotFoundError(f"Tariff Programs Excel file not found at: {excel_path}")
        
        print(f"Reading Tariff Programs Excel from: {excel_path}")
        
        # Read Excel file
        df = pd.read_excel(excel_path, dtype=str, engine="openpyxl").fillna("")
        
        # Process each row to create proper structure
        tariff_records = []
        for idx, row in df.iterrows():
            # Clean up program code (remove any extra whitespace)
            program_code = str(row.get('Program Code', row.get('Code', ''))).strip()
            
            # Get countries and normalize (replace semicolons, commas, etc.)
            countries_raw = str(row.get('Countries', '')).strip()
            # Normalize separators to semicolons
            countries = re.sub(r'[,;]\s*', ';', countries_raw)
            
            record = {
                'program_code': program_code,
                'program_name': str(row.get('Program Name', row.get('Name', row.get('Description', '')))).strip(),
                'group_name': str(row.get('Group', '')).strip(),
                'countries': countries,
                'description': str(row.get('Description', row.get('Program Name', ''))).strip()
            }
            
            # Only add if program_code is not empty
            if program_code:
                tariff_records.append(record)
        
        # Save to JSON
        output_path = self.json_dir / "tariff_programs.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tariff_records, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Converted {len(tariff_records)} tariff program records to JSON: {output_path}")
        return output_path
    
    def convert_all(self) -> Dict[str, Path]:
        """
        Converts both HTS CSV and Tariff Programs Excel to JSON.
        
        Returns:
            Dictionary with paths to generated JSON files
        """
        print("Starting conversion of all data files to JSON...\n")
        
        results = {}
        
        try:
            results['hts_codes'] = self.convert_hts_csv_to_json()
        except Exception as e:
            print(f"✗ Error converting HTS CSV: {e}")
            results['hts_codes'] = None
        
        try:
            results['tariff_programs'] = self.convert_tariff_programs_to_json()
        except Exception as e:
            print(f"✗ Error converting Tariff Programs Excel: {e}")
            results['tariff_programs'] = None
        
        print("\n" + "="*60)
        print("Conversion Summary:")
        for key, path in results.items():
            if path:
                print(f"✓ {key}: {path}")
            else:
                print(f"✗ {key}: Failed")
        print("="*60)
        
        return results


def main():
    """
    Main function to run the conversion process.
    """
    converter = DataConverter()
    results = converter.convert_all()
    
    return results


if __name__ == "__main__":
    main()