import os
import modules.veloportal as veloportal
import modules.globals as globals

def main():
    input_xml_dir = "xml"
    output_dir = "output"
    
    test_xml_path = os.path.join(input_xml_dir, "goods.xml")
    output_excel_name = "veloportal_export.xlsx"
    
    if not os.path.exists(test_xml_path):
        print(f"Error: Target file '{test_xml_path}' does not exist.")
        return

    print(f"Processing data source: {test_xml_path}...\n")
    
    df = veloportal.parse_to_dataframe(test_xml_path, min_price=globals.DEFAULT_MIN_PRICE)
    
    print(f"\nExtraction complete. {len(df)} records remaining.\n")
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("Formatting to template schema, mapping categories, and fetching images...")
    
    # Passing the directory and filename to the orchestrator function
    veloportal.export_to_template(df, output_dir, output_excel_name)
    
    print("\nExecution finished.")

if __name__ == "__main__":
    main()