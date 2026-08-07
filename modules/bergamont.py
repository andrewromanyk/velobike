import pandas as pd
import os
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup
import webbrowser
import threading
from io import BytesIO
import modules.globals as globals
import modules.image_downloader as image_downloader
from ddgs import DDGS

# --- Імпорти для графічного інтерфейсу ---
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

GLOBAL_SKIP_FALLBACK = False

class ManualClipboardPickerWindow:
    """
    Вікно, яке "слухає" буфер обміну. 
    Відкриває стандартний браузер і чекає, поки користувач скопіює URL картинки.
    """
    def __init__(self, query, article, color):
        self.query = query
        self.selected_url = ""
        self.last_clipboard = ""
        self.preview_photo = None
        
        self.skip_all = False # НОВЕ: Прапорець для пропуску всіх наступних
        
        self.temp_root = False
        if tk._default_root is None: # type: ignore
            self.root = tk.Tk()
            self.root.withdraw()
            self.top = tk.Toplevel(self.root)
            self.temp_root = True
        else:
            self.root = tk._default_root # type: ignore
            self.top = tk.Toplevel(self.root)
            
        self.top.title("Ручний пошук зображення")
        self.top.geometry("500x650") # Трохи розширив вікно для кнопок
        self.top.attributes('-topmost', True)
        self.top.grab_set()
        
        self.top.clipboard_clear()
        
        self._build_ui(query, article, color)
        
        search_url = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(query + ' bicycle')}"
        webbrowser.open(search_url)
        
        self._check_clipboard()

    def _build_ui(self, query, article, color):
        info_frame = ttk.Frame(self.top, padding=10)
        info_frame.pack(fill=tk.X)
        
        instructions = (
            "1. У вашому браузері відкрито пошук.\n"
            "2. Знайдіть правильне зображення.\n"
            "3. Натисніть ПКМ ➔ 'Копіювати адресу зображення'."
        )
        ttk.Label(info_frame, text=instructions, font=("Arial", 11, "bold"), foreground="#2c3e50").pack(pady=(0, 10))
        
        text_widget = tk.Text(info_frame, height=4, font=("Arial", 10), wrap="word", bg="#f0f0f0", relief="flat")
        text_widget.pack(fill=tk.X)
        text_widget.insert(tk.END, f"Артикул: {article}\nКолір: {color}\nЗапит: {query}")
        text_widget.configure(state="disabled")

        self.preview_frame = ttk.Frame(self.top, padding=10)
        self.preview_frame.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_status = ttk.Label(self.preview_frame, text="Очікування посилання в буфері обміну...", font=("Arial", 10), foreground="gray")
        self.lbl_status.pack(pady=20)
        
        self.lbl_image = ttk.Label(self.preview_frame)
        self.lbl_image.pack(expand=True)

        # ОНОВЛЕНІ КНОПКИ
        self.btn_frame = ttk.Frame(self.top, padding=10)
        self.btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_accept = ttk.Button(self.btn_frame, text="✅ Зберегти", command=self._on_accept, state=tk.DISABLED)
        self.btn_accept.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        ttk.Button(self.btn_frame, text="⏭ Пропустити", command=self._on_skip).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        ttk.Button(self.btn_frame, text="🛑 Пропустити всі", command=self._on_skip_all).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def _check_clipboard(self):
        """Регулярно перевіряє буфер обміну на наявність посилання."""
        try:
            current_clip = self.top.clipboard_get().strip()
            # Якщо з'явилося нове посилання, що починається з http
            if current_clip != self.last_clipboard and current_clip.lower().startswith("http"):
                self.last_clipboard = current_clip
                # Перевіряємо, чи це пряме посилання на картинку або щось схоже
                if "google.com" not in current_clip or "imgres" in current_clip:
                    self._load_preview(current_clip)
        except tk.TclError:
            pass # Буфер порожній або містить не текст
            
        # Зациклюємо перевірку кожні 500 мілісекунд
        self.check_id = self.top.after(500, self._check_clipboard)

    def _load_preview(self, url):
        self.lbl_status.config(text="Завантаження прев'ю...", foreground="blue")
        self.btn_accept.config(state=tk.DISABLED)
        
        def fetch():
            try:
                res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                res.raise_for_status()
                img = Image.open(BytesIO(res.content))
                img.thumbnail((350, 350), Image.Resampling.LANCZOS)
                
                # Повертаємось в головний потік для оновлення UI
                self.top.after(0, self._show_preview, img, url)
            except Exception as e:
                self.top.after(0, lambda: self.lbl_status.config(text=f"Помилка: неможливо завантажити це посилання.\nСпробуйте 'Відкрити зображення в новій вкладці' і скопіювати.", foreground="red"))

        threading.Thread(target=fetch, daemon=True).start()

    def _show_preview(self, img, url):
        self.preview_photo = ImageTk.PhotoImage(img)
        self.lbl_image.config(image=self.preview_photo)
        self.lbl_status.config(text="Фото успішно розпізнано! Натисніть 'Зберегти'.", foreground="green")
        self.btn_accept.config(state=tk.NORMAL)
        # Зберігаємо тимчасово обраний URL
        self.temp_url = url

    def show(self):
        if self.temp_root:
            self.root.mainloop() 
        else:
            self.top.wait_window()
        return self.selected_url

    def _on_accept(self):
        self.selected_url = self.temp_url
        self._close()
        
    def _on_skip(self):
        self.selected_url = ""
        self._close()
        
    def _close(self):
        self.top.after_cancel(self.check_id) # Зупиняємо цикл перевірки
        self.top.grab_release()
        self.top.destroy()
        if self.temp_root:
            self.root.quit()
            self.root.destroy()

    def _on_skip_all(self):
        self.skip_all = True
        self.selected_url = ""
        self._close()


def parse_to_dataframe(source_path: str, min_price: float = 0.0, excluded_categories: list = None, output_dir: str = "", enable_fallback: bool = True) -> pd.DataFrame: # type: ignore
    global GLOBAL_SKIP_FALLBACK
    # При новому запуску парсингу скидаємо або встановлюємо статус фолбеку
    GLOBAL_SKIP_FALLBACK = not enable_fallback 
    
    print(f"Module [bergamont]: Parsing {source_path}...")
    df_raw = pd.read_excel(source_path)
    initial_count = len(df_raw)
    df_valid = df_raw.dropna(subset=['Код для опт.']).copy()
    print(f"Module [bergamont]: Dropped {initial_count - len(df_valid)} grouping/empty rows.")

    items_data = []
    for _, row in df_valid.iterrows():
        price_regular = pd.to_numeric(row.get('Роздр. грн', 0), errors='coerce')
        price_actual = pd.to_numeric(row.get('Актуальн. роздр. грн', 0), errors='coerce')
        if pd.isna(price_actual) or price_actual == 0:
            price_actual = price_regular
        old_price = price_regular if price_regular > price_actual else 0

        specs = []
        if pd.notna(row.get('Кіл. швидкостей ')): specs.append(f"<b>Кількість швидкостей:</b> {str(row.get('Кіл. швидкостей ')).strip()}")
        if pd.notna(row.get('Рама/Вилка ')): specs.append(f"<b>Рама/Вилка:</b> {str(row.get('Рама/Вилка ')).strip()}")
        if pd.notna(row.get('Гальма ')): specs.append(f"<b>Гальма:</b> {str(row.get('Гальма ')).strip()}")
        descr = "<br/>".join(specs)

        official_url = str(row.get('Посилання на офіційний сайт', '')).strip()
        gdrive_url = str(row.get('Посилання на фото (Google Disk)', '')).strip()
        title_val = str(row.get('НАЙМЕНУВАННЯ', '')).strip()
        color_val = str(row.get('Колір', '')).strip() 
        article_val = str(row['Код для опт.']).strip()
        
        photos_str = ""
        needs_review = False
        
        if official_url and official_url.lower() != 'nan' and 'bergamont.com' not in official_url.lower():
            photos_str = fetch_image_urls_from_website(official_url, title_val, color_val)

        # ВИКЛИК РУЧНОГО ВІКНА (якщо його не вимкнено глобально)
        if not photos_str and not GLOBAL_SKIP_FALLBACK:
            photos_str = _search_image_fallback(title_val, article_val, color_val)
            if photos_str: # Ставимо мітку "перевірити" лише якщо ми дійсно знайшли фото
                needs_review = True

        mapped_row = {
            'article': article_val,
            'brand': str(row.get('Поставщик', '')).strip(),
            'category': str(row.get('Категория', '')).strip(),
            'title': title_val,
            'color': color_val,
            'price_r': price_actual,
            'old_price': old_price,
            'descr': descr,
            'photos': photos_str,
            'needs_review': needs_review,
            'is_in_stock': 10
        }
        items_data.append(mapped_row)
        
    df = pd.DataFrame(items_data)
    if excluded_categories: df = df[~df['category'].isin(excluded_categories)]
    if min_price is not None and min_price > 0: df = df[df['price_r'] >= min_price]
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
        export_df['Старая цена'] = df['old_price'].replace(0, '')
        export_df['Цвет'] = df['color'].replace('nan', '')
        export_df['Наличие'] = df['is_in_stock'].apply(lambda x: "В наявності" if pd.to_numeric(x, errors='coerce') > 0 else "Немає в наявності")
        export_df['Поставщик'] = "П4"
        export_df['Фото'] = df.get('photos', '')
        export_df['Описание товара(RU)'] = df.get('descr', '')
        export_df['Описание товара(UA)'] = df.get('descr', '')
        
        if 'category' in df.columns:
            export_df['Раздел'] = df['category'].map(globals.CATEGORY_MAP).fillna('Велосипеди/Інше')

        for _index, row in df.iterrows():
            article = str(row.get('article', '')).strip()
            photos_str = str(row.get('photos', '')).strip()
            needs_review = row.get('needs_review', False)
            
            subfolder = "перевірити" if needs_review else ""
            
            if photos_str and photos_str.lower().startswith(('http://', 'https://')):
                urls = [u.strip() for u in photos_str.split(' | ') if u.strip()]
                if not urls: continue
                if len(urls) == 1:
                    image_tasks.append((urls[0], article, 0, subfolder))
                else:
                    for i, url in enumerate(urls, start=1):
                        image_tasks.append((url, article, i, subfolder))

    export_df = export_df.fillna('')
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        worksheet.auto_filter.ref = worksheet.dimensions

    print(f"Module [bergamont]: Exported {len(export_df)} mapped records.")
    if image_tasks:
        image_downloader.download_from_list(image_tasks, output_dir, status_callback=status_callback)

def get_similarity_score(title: str, image_url: str) -> int:
    title_tokens = set(re.findall(r'\w+', title.lower()))
    parsed_url = urllib.parse.urlparse(image_url)
    filename = os.path.basename(parsed_url.path)
    image_tokens = set(re.findall(r'\w+', filename.lower()))
    return len(title_tokens.intersection(image_tokens))

# --- ВАШІ ПАРСЕРИ САЙТІВ ЗАЛИШЕНО БЕЗ ЗМІН ДЛЯ ЕКОНОМІЇ МІСЦЯ ---
# (Залиште тут ваші функції _scrape_bottecchia, _scrape_vnc, _scrape_reidbikes)

def _scrape_bottecchia(url: str, color_from_excel: str) -> str:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response.status_code != 200: return ""
        html_text = response.text
        soup = BeautifulSoup(html_text, 'html.parser')
        target_tokens = set(re.findall(r'\w+', str(color_from_excel).lower()))
        radio_inputs = soup.find_all('input', class_=re.compile(r'product-variant__input'))
        best_variant_id = None
        max_score = -1
        for radio in radio_inputs:
            variant_val = str(radio.get('value', '')).lower()
            variant_tokens = set(re.findall(r'\w+', variant_val))
            score = len(target_tokens.intersection(variant_tokens))
            if score > max_score and score > 0:
                max_score = score
                best_variant_id = radio.get('data-variant-id')

        if best_variant_id:
            match = re.search(rf'"{best_variant_id}".*?"image"\s*:\s*\{{.*?"src"\s*:\s*"([^"]+)"', html_text)
            if match:
                img_src = match.group(1).replace(r'\/', '/') 
                return f"https:{img_src}" if img_src.startswith('//') else img_src

        images = [el.get('data-image') for el in soup.find_all('product-image-zoom') if el.get('data-image')]
        if not images:
            images = [img.get('src') for img in soup.select('.css-slider-container img') if img.get('src')]
            
        if images:
            best_image = images[0]
            max_sub_score = -1
            for img in images:
                img_lower = img.lower() # type: ignore
                sub_score = sum(1 for token in target_tokens if len(token) > 2 and token in img_lower)
                if sub_score > max_sub_score:
                    max_sub_score = sub_score
                    best_image = img
            return f"https:{best_image}" if best_image.startswith('//') else best_image # type: ignore

        return ""
    except Exception as e:
        print(f"Module [bergamont]: Scrape Error Bottecchia ({url}) - {e}")
        return ""

    
def _scrape_vnc(url: str, color_from_excel: str, title_from_excel: str) -> str:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response.status_code != 200:
            return ""
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        all_galleries = soup.find_all('div', class_=re.compile(r'dmPhotoGallery'))
        valid_galleries = []
        
        for gallery in all_galleries:
            caption_button = gallery.find('a', class_=re.compile(r'caption-button'))
            href = caption_button.get('href', '').strip() if caption_button else "" # type: ignore
            if not href or href == '#' or href.startswith('javascript'):
                valid_galleries.append(gallery)

        target_color_tokens = set(re.findall(r'\w+', str(color_from_excel).lower()))
        best_gallery_images = []
        max_score = -1

        if valid_galleries:
            for gallery in valid_galleries:
                title_elem = gallery.find(class_='caption-title')
                gallery_color = title_elem.text if title_elem else ""
                gallery_tokens = set(re.findall(r'\w+', gallery_color.lower()))
                score = len(target_color_tokens.intersection(gallery_tokens))
                
                img_containers = gallery.find_all(class_='image-container')
                imgs = []
                for container in img_containers:
                    img_tag = container.find('img')
                    if img_tag:
                        src = img_tag.get('data-src') or img_tag.get('src')
                        if src and 'cdninstagram.com' not in src:
                            imgs.append(src)
                            
                if score > max_score and imgs:
                    max_score = score
                    best_gallery_images = imgs
                    
            if max_score <= 0 and not best_gallery_images:
                for gallery in valid_galleries:
                    img_containers = gallery.find_all(class_='image-container')
                    imgs = [img.find('img').get('data-src') or img.find('img').get('src') for img in img_containers if img.find('img')]
                    imgs = [src for src in imgs if src and 'cdninstagram.com' not in src]
                    if imgs:
                        best_gallery_images = imgs
                        break

            if best_gallery_images:
                final_urls = []
                for img in best_gallery_images:
                    img = img.strip()
                    if img.startswith('//'):
                        img = f"https:{img}"
                    if img not in final_urls:
                        final_urls.append(img)
                return " | ".join(final_urls)

        fallback_candidates = []
        target_title_tokens = set(re.findall(r'\w+', str(title_from_excel).lower()))

        for style in soup.find_all('style'):
            if style.string:
                urls = re.findall(r"background-image\s*:\s*url\(['\"]?(https?://[^'\"\)]+)['\"]?\)", style.string)
                fallback_candidates.extend(urls)

        for tag in soup.find_all(style=True):
            urls = re.findall(r"background-image\s*:\s*url\(['\"]?(https?://[^'\"\)]+)['\"]?\)", tag['style']) # type: ignore
            fallback_candidates.extend(urls)

        for widget in soup.find_all('div', class_=re.compile(r'imageWidget')):
            img = widget.find('img')
            if img:
                src = img.get('data-dm-image-path') or img.get('data-src') or img.get('src')
                if src: fallback_candidates.append(src)

        best_fallback = None
        max_fb_score = -1
        valid_fallbacks = []
        exclusions = ['logo', 'icon', 'favicon', 'cdninstagram.com', 'size', 'chart', 'geometry', 'drawing']

        for src in fallback_candidates:
            if not src or any(exc in src.lower() for exc in exclusions):
                continue

            clean_src = src.strip()
            if clean_src.startswith('//'):
                clean_src = f"https:{clean_src}"

            if clean_src not in valid_fallbacks:
                valid_fallbacks.append(clean_src)

            filename = urllib.parse.unquote(clean_src.split('/')[-1].split('?')[0].lower())
            score = sum(1 for t in target_title_tokens if len(t) >= 3 and t in filename)

            if score > max_fb_score:
                max_fb_score = score
                best_fallback = clean_src

        if best_fallback:
            return best_fallback
        elif valid_fallbacks:
            return valid_fallbacks[0]
            
        return ""
        
    except Exception as e:
        print(f"Module [bergamont]: Scrape Error VNC/Atlantic ({url}) - {e}")
        return ""

def _scrape_reidbikes(url: str, color_from_excel: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15.0)
        if response.status_code != 200:
            return ""
        
        soup = BeautifulSoup(response.text, 'html.parser')
        target_tokens = set(re.findall(r'\w+', str(color_from_excel).lower()))
        
        swatches = soup.find_all('a', class_=re.compile(r'pl-swatches__link'))
        
        best_url = url
        max_score = -1
        
        for swatch in swatches:
            color_title = swatch.get('title') or swatch.get('aria-label') or ""
            swatch_tokens = set(re.findall(r'\w+', color_title.lower())) # type: ignore
            score = len(target_tokens.intersection(swatch_tokens))
            
            if score > max_score and score > 0:
                max_score = score
                href = swatch.get('href')
                if href and not href.lower().startswith('javascript'): # type: ignore
                    best_url = urllib.parse.urljoin(url, href) # type: ignore
                else:
                    best_url = url 
                    
        if best_url != url:
            response = requests.get(best_url, headers=headers, timeout=15.0)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
        gallery = soup.find('ul', class_=re.compile(r'product__media-list'))
        if not gallery:
            return ""
            
        img_tags = gallery.find_all('img')
        final_urls = []
        
        for img in img_tags:
            src = img.get('src') or img.get('data-src')
            if src:
                clean_src = src.split('?')[0] # type: ignore
                if clean_src.startswith('//'):
                    clean_src = f"https:{clean_src}"
                    
                if clean_src not in final_urls:
                    final_urls.append(clean_src)
                    
        return " | ".join(final_urls)
        
    except Exception as e:
        print(f"Module [bergamont]: Scrape Error Reid ({url}) - {e}")
        return ""

def _search_image_fallback(query: str, article: str, color: str) -> str:
    """Викликає вікно-перехоплювач, якщо ручний пошук не був вимкнений."""
    global GLOBAL_SKIP_FALLBACK
    if GLOBAL_SKIP_FALLBACK:
        return ""

    try:
        clean_query = re.sub(r'\(.*?\)', '', query).strip()
        picker = ManualClipboardPickerWindow(clean_query, article, color)
        result = picker.show()
        
        # Якщо користувач натиснув "Пропустити всі", активуємо глобальний прапорець
        if picker.skip_all:
            GLOBAL_SKIP_FALLBACK = True
            
        return result
    except Exception as e:
        print(f"Module [bergamont]: Manual Search Error ({query}) - {e}")
    return ""

def fetch_image_urls_from_website(url: str, title: str, color: str) -> str:
    if not url or pd.isna(url) or str(url).lower() == 'nan':
        return ""
    
    url_lower = str(url).lower()
    
    try:
        if "bottecchia.com" in url_lower:
            return _scrape_bottecchia(url, color)
        elif "vncompany.co.uk" in url_lower or "atlanticbicycles.com" in url_lower:
            return _scrape_vnc(url, color, title) 
        elif "reidbikes.com" in url_lower:
            return _scrape_reidbikes(url, color)
    except Exception as e:
        print(f"Module [bergamont]: Router Error - {e}")
        
    return ""