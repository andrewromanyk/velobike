# modules/author.py
import xml.etree.ElementTree as ET
import urllib.request
import pandas as pd
import os
import re
import modules.globals as globals
import modules.image_downloader as image_downloader

def parse_to_dataframe(source_path: str, min_price: float = 0.0, excluded_categories: list = None, output_dir: str = "") -> pd.DataFrame: # type: ignore
    print(f"Module [author]: Fetching XML from {source_path}...")
    
    # Завантаження XML з URL
    req = urllib.request.Request(source_path, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        tree = ET.parse(response)
        
    root = tree.getroot()
    items_data = []

    for item in root.findall('.//item'):
        # Очищення та конвертація ціни
        price_str = item.findtext('rrc_UAH', '0').replace(',', '.')
        try:
            price = float(re.sub(r'[^\d.]', '', price_str))
        except ValueError:
            price = 0.0

        # Очищення залишку (наприклад, ">10" -> 10)
        stock_str = item.findtext('quantity_in_stock', '0')
        stock_clean = re.sub(r'\D', '', stock_str)
        stock = int(stock_clean) if stock_clean else 0

        row = {
            'brand': item.findtext('brand', '').strip(),
            'article': item.findtext('article', '').strip(),
            'title': item.findtext('title', '').strip(),
            'is_in_stock': stock,
            'price_r': price,
            'category': item.findtext('category', '').strip(),
            'descr': item.findtext('description', '').strip(),
        }

        # Обробка множинних тегів <picture>
        photos = [img.text.strip() for img in item.findall('picture') if img.text]
        row['photos'] = ' | '.join(photos)

        # Обробка тегів <param name="...">
        for param in item.findall('param'):
            name = param.get('name')
            value = param.text
            if name and value:
                row[f'param_{name.strip()}'] = value.strip()

        items_data.append(row)

    df = pd.DataFrame(items_data)
    initial_count = len(df)
    print(f"Module [author]: Parsed {initial_count} initial records.")

    # Фільтрація за наявністю
    stock_mask = df['is_in_stock'] > 0
    df = df[stock_mask]

    # Фільтрація за категоріями
    if excluded_categories:
        df = df[~df['category'].isin(excluded_categories)]

    # Фільтрація за ціною
    if min_price is not None and min_price > 0:
        df = df[df['price_r'] >= min_price]

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
        
        # Наявність та постачальник (встановіть потрібний код, напр. П4)
        export_df['Наличие'] = df['is_in_stock'].apply(
            lambda x: "В наявності" if pd.to_numeric(x, errors='coerce') > 0 else "Немає в наявності"
        )
        export_df['Поставщик'] = "П4" # Замініть на актуальний ідентифікатор Author
        export_df['Отображать'] = "так"
        
        export_df['Фото'] = df.get('photos', '')
        export_df['Описание товара(RU)'] = df.get('descr', '')
        export_df['Описание товара(UA)'] = df.get('descr', '')
        
        # Мапінг категорій
        if 'category' in df.columns:
            export_df['Раздел'] = df['category'].map(globals.CATEGORY_MAP).fillna('Компоненты/Другие')

        for index, row in df.iterrows():
            article = str(row.get('article', '')).strip()
            photos_str = str(row.get('photos', '')).strip()
            
            if photos_str and photos_str != 'nan':
                urls = [u.strip() for u in photos_str.split(' | ') if u.strip()]
                if not urls: continue
                
                if len(urls) == 1:
                    image_tasks.append((urls[0], article, 0))
                else:
                    for i, url in enumerate(urls, start=1):
                        image_tasks.append((url, article, i))

    export_df = export_df.fillna('')
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        worksheet.auto_filter.ref = worksheet.dimensions

    print(f"Module [author]: Exported {len(export_df)} mapped records.")
    
    if image_tasks:
        image_downloader.download_from_list(image_tasks, output_dir, status_callback=status_callback)