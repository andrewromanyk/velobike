import pandas as pd
import os
import re
import openpyxl
import modules.globals as globals
import modules.image_downloader as image_downloader

try:
    import win32com.client
except ImportError:
    win32com = None

def clean_stock_value(val):
    if pd.isna(val):
        return 0
    
    val_str = str(val).strip().lower()
    
    if val_str in ['есть', 'yes', '+', 'в наличии']:
        return 10 
        
    clean_str = re.sub(r'[^\d.]', '', val_str)
    
    try:
        return int(float(clean_str)) if clean_str else 0
    except ValueError:
        return 0

def extract_formulas_openpyxl(source_path, target_col_idx=3):
    """
    Extracts =HYPERLINK formulas from an .xlsx file using openpyxl.
    """
    url_map = {}
    wb = openpyxl.load_workbook(source_path, data_only=False, read_only=True)
    sheet = wb.active
    
    for row_idx, row in enumerate(sheet.iter_rows(min_row=9, min_col=target_col_idx, max_col=target_col_idx), start=9): # type: ignore
        cell = row[0]
        if cell.value and isinstance(cell.value, str) and "HYPERLINK" in cell.value.upper():
            match = re.search(r'HYPERLINK\("([^"]+)"', cell.value, re.IGNORECASE)
            if match:
                url_map[row_idx] = match.group(1)
                
    wb.close()
    return url_map

def convert_xls_to_xlsx(source_path, output_dir):
    """
    Uses Excel COM to convert an old .xls file to a modern .xlsx file.
    Saves the temporary file into the designated output directory.
    """
    if not win32com:
        raise RuntimeError("pywin32 is not installed. Cannot convert .xls to .xlsx automatically.")
        
    abs_source = os.path.abspath(source_path)
    
    # Створюємо нове ім'я файлу (Price.xls -> Price.xlsx) у папці output
    base_name = os.path.basename(source_path) + "x" 
    abs_target = os.path.abspath(os.path.join(output_dir, base_name))
    
    if os.path.exists(abs_target):
        os.remove(abs_target)
        
    excel = None
    wb = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        wb = excel.Workbooks.Open(abs_source, ReadOnly=True)
        wb.SaveAs(abs_target, FileFormat=51)
        wb.Close()
    except Exception as e:
        print(f"Module [veloplaneta]: COM Conversion Error - {e}")
        raise
    finally:
        if excel:
            excel.Quit()
            
    return abs_target


def parse_to_dataframe(source_path: str, min_price: float = 0.0, excluded_categories: list = None, output_dir: str = "") -> pd.DataFrame: # type: ignore
    working_path = source_path
    
    if source_path.lower().endswith('.xls'):
        print("Module [veloplaneta]: Converting .xls to .xlsx via Excel COM...")
        # Передаємо цільову папку для збереження
        working_path = convert_xls_to_xlsx(source_path, output_dir)

    print("Module [veloplaneta]: Extracting URLs via openpyxl...")
    hyperlink_map = extract_formulas_openpyxl(working_path, target_col_idx=3)
    
    df_raw = pd.read_excel(working_path, header=8, engine='openpyxl')
    initial_count = len(df_raw)
    print(f"Module [veloplaneta]: Read {initial_count} raw rows.")

    df_raw.columns = df_raw.columns.astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)

    df_valid = df_raw.dropna(subset=['Артикул']).copy()
    print(f"Module [veloplaneta]: Dropped {initial_count - len(df_valid)} empty/grouping rows.")

    items_data = []
    for index, row in df_valid.iterrows():
        excel_row_idx = index + 10 # type: ignore
        
        photo_data = hyperlink_map.get(excel_row_idx, str(row.get('Фото', '')).strip())

        mapped_row = {
            'article': str(row.get('Артикул', '')).strip(),
            'title': str(row.get('Наименование товаров', '')).strip(),
            'brand': str(row.get('Бренд', '')).strip(),
            'category': str(row.get('Вид товара', '')).strip(),
            'price_r': row.get('Розничная для продажи, грн', 0),
            'is_in_stock': clean_stock_value(row.get('Остаток', 0)),
            'photos': photo_data 
        }
        items_data.append(mapped_row)

    df = pd.DataFrame(items_data)
    df['price_r'] = pd.to_numeric(df['price_r'], errors='coerce').fillna(0)

    stock_mask = df['is_in_stock'] > 0
    df = df[stock_mask]
    print(f"Module [veloplaneta]: Filtered out {len(items_data) - len(df)} records (out of stock).")

    if excluded_categories:
        pre_cat_count = len(df)
        df = df[~df['category'].isin(excluded_categories)]
        cat_filtered = pre_cat_count - len(df)
        print(f"Module [veloplaneta]: Filtered out {cat_filtered} records (excluded categories).")

    if min_price > 0:
        pre_price_count = len(df)
        price_mask = df['price_r'] >= min_price
        df = df[price_mask]
        price_filtered = pre_price_count - len(df)
        print(f"Module [veloplaneta]: Filtered out {price_filtered} records (price < {min_price}).")

    return df.reset_index(drop=True)

def export_to_template(df: pd.DataFrame, output_dir: str, file_name: str, status_callback=None):
    output_path = os.path.join(output_dir, file_name)
    export_df = pd.DataFrame(columns=globals.TEMPLATE_COLUMNS)
    image_tasks = []

    if not df.empty:
        export_df['Артикул'] = df['article']
        export_df['Родительский артикул'] = df['article']
        
        export_df['Название(RU)'] = df['title']
        export_df['Название(UA)'] = df['title']
        
        export_df['Бренд'] = df['brand']
        export_df['Цена'] = df['price_r']
        export_df['Наличие'] = df['is_in_stock'].apply(
            lambda x: "В наявності" if pd.to_numeric(x, errors='coerce') > 0 else "Немає в наявності"
        )
        export_df['Поставщик'] = "П3"
        export_df['Отображать'] = "так"
        export_df['Фото'] = df.get('photos', '')
        
        export_df['Описание товара(RU)'] = ""
        export_df['Описание товара(UA)'] = ""
        
        if 'category' in df.columns:
            export_df['Раздел'] = df['category'].map(globals.VELOPLANETA_CATEGORY_MAP).fillna('Компоненты/Другие')

        for index, row in df.iterrows():
            article = str(row.get('article', '')).strip()
            photos_str = str(row.get('photos', '')).strip()
            
            if photos_str and photos_str.lower().startswith(('http://', 'https://')):
                urls = [u.strip() for u in photos_str.split(' | ') if u.strip()]
                if not urls:
                    continue
                if len(urls) == 1:
                    image_tasks.append((urls[0], article, 0))
                else:
                    for i, url in enumerate(urls, start=1):
                        image_tasks.append((url, article, i))

    export_df = export_df.fillna('')
    
    # Use ExcelWriter to access the openpyxl worksheet object
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        
        # Apply auto-filter across the entire data range
        worksheet.auto_filter.ref = worksheet.dimensions

    print(f"Module [veloplaneta]: Exported {len(export_df)} mapped records to {output_path}.")
    
    if image_tasks:
        if status_callback:
            status_callback("Завантаження зображень...")
            
        image_downloader.download_from_list(
            image_tasks, 
            output_dir, 
            status_callback=status_callback
        )