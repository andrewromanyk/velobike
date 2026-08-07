import xml.etree.ElementTree as ET
import pandas as pd
import os
import modules.globals as globals
import modules.image_downloader as image_downloader

def parse_to_dataframe(source_path: str, min_price: float = 0.0, excluded_categories: list = None, output_dir: str = "") -> pd.DataFrame: # type: ignore
    tree = ET.parse(source_path)
    root = tree.getroot()
    
    items_data = []

    for item in root.iter('item'):
        row = {
            'brand': item.findtext('brand'),
            'article': item.findtext('article'),
            'title': item.findtext('title', '').strip(),
            'is_in_stock': item.findtext('is_in_stock'),
            'price_r': item.findtext('price_r'),
            'category': item.findtext('category'),
            'descr': item.findtext('descr', '').strip(),
        }

        photos = [img.text.strip() for img in item.findall('photos/image') if img.text]
        row['photos'] = ' | '.join(photos)

        for param in item.findall('params/param'):
            name = param.findtext('name')
            value = param.findtext('value')
            if name and value:
                row[f'param_{name.strip()}'] = value.strip()

        items_data.append(row)

    df = pd.DataFrame(items_data)
    initial_count = len(df)
    print(f"Module [veloportal]: Parsed {initial_count} initial records.")

    if 'price_r' in df.columns:
        df['price_r'] = pd.to_numeric(df['price_r'], errors='coerce')
    if 'is_in_stock' in df.columns:
        df['is_in_stock'] = pd.to_numeric(df['is_in_stock'], errors='coerce')

    # Filter 1: In-stock
    if 'is_in_stock' in df.columns:
        stock_mask = df['is_in_stock'] > 0
        df = df[stock_mask]
        stock_filtered = initial_count - len(df)
        print(f"Module [veloportal]: Filtered out {stock_filtered} records (out of stock/invalid).")

    # Filter 2: Excluded Categories
    if 'category' in df.columns and excluded_categories:
        pre_cat_count = len(df)
        df = df[~df['category'].isin(excluded_categories)]
        cat_filtered = pre_cat_count - len(df)
        print(f"Module [veloportal]: Filtered out {cat_filtered} records (excluded categories).")

    # Filter 3: Minimum Price
    if min_price is not None and 'price_r' in df.columns:
        pre_price_count = len(df)
        price_mask = df['price_r'] >= min_price
        df = df[price_mask]
        price_filtered = pre_price_count - len(df)
        print(f"Module [veloportal]: Filtered out {price_filtered} records (price < {min_price}).")

    return df.reset_index(drop=True)

def export_to_template(df: pd.DataFrame, output_dir: str, file_name: str, status_callback=None):
    """
    Maps the parsed DataFrame to the Excel template schema, detects unmapped categories, 
    exports it, and calls the external image downloader utility.
    """
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
        export_df['Поставщик'] = "П2"
        export_df['Фото'] = df.get('photos', '')
        
        export_df['Описание товара(RU)'] = df.get('descr', '')
        export_df['Описание товара(UA)'] = df.get('descr', '')
        
        if 'param_Колір' in df.columns:
            export_df['Цвет'] = df['param_Колір']

        if 'category' in df.columns:
            # Intercept and log any categories missing from the mapping dictionary
            unique_current_cats = set(df['category'].dropna().unique())
            mapped_cats = set(globals.CATEGORY_MAP.keys())
            unmapped_cats = unique_current_cats - mapped_cats
            
            if unmapped_cats:
                print(f"Module [veloportal]: WARNING - Found {len(unmapped_cats)} unmapped categories falling back to 'Компоненты/Другие':")
                for c in sorted(list(unmapped_cats)):
                    print(f"  - {c}")

            # Apply the mapping
            export_df['Раздел'] = df['category'].map(globals.CATEGORY_MAP).fillna('Компоненты/Другие')

        # Construct the agnostic list of (url, identifier, index) for the downloader
        for index, row in df.iterrows():
            article = str(row.get('article', '')).strip()
            photos_str = str(row.get('photos', '')).strip()
            
            if photos_str and photos_str != 'nan':
                # Split the photos string using the ' | ' separator defined in the parser
                urls = [u.strip() for u in photos_str.split(' | ') if u.strip()]
                
                if not urls:
                    continue
                
                # If there is only one image, pass index 0 (no '@1' suffix)
                if len(urls) == 1:
                    image_tasks.append((urls[0], article, 0))
                # If there are multiple images, append the index (1, 2, 3...) to create '@1', '@2'
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

    print(f"Module [veloportal]: Exported {len(export_df)} mapped records to {output_path}.")
    
    # Pass the list to the independent utility
    if image_tasks:
        image_downloader.download_from_list(
            image_tasks, 
            output_dir, 
            status_callback=status_callback
        )