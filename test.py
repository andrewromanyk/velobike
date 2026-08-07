import pandas as pd
import sys

def inspect_excel(file_path: str):
    try:
        # Load the file. Engine is specified to ensure compatibility with .xlsx
        df = pd.read_excel(file_path)        
        print(f"--- Inspection Report: {file_path} ---")
        print(f"Dimensions: {df.shape[0]} rows, {df.shape[1]} columns\n")
        
        print("Columns:")
        for idx, col in enumerate(df.columns):
            print(f"  [{idx}] {col}")
            
        print("\nFirst 5 rows:")
        # to_string() ensures columns are not arbitrarily truncated in the terminal
        print(df.head().to_string())
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
        inspect_excel(target_file)
    else:
        print("Usage: python inspect_excel.py <path_to_excel_file>")