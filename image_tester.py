import os
import glob
import webbrowser
import pandas as pd
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image
import xml.etree.ElementTree as ET
import re

class OriginalFileTesterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Original Source Image Verifier")
        self.geometry("1100x750")
        ctk.set_appearance_mode("Dark")

        self.data_records = []
        self.current_index = 0
        self.images_dir = ""
        self.source_file = ""
        self.image_references = [] # Для запобігання збиранню сміття (Garbage Collection) картинок

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Бокова панель (Керування) ---
        sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(sidebar, text="Налаштування", font=("Arial", 20, "bold")).pack(pady=(20, 10), padx=20)

        self.format_var = ctk.StringVar(value="Excel (.xls, .xlsx)")
        self.dropdown_format = ctk.CTkOptionMenu(
            sidebar, 
            values=["Excel (.xls, .xlsx)", "XML (.xml)"], 
            variable=self.format_var
        )
        self.dropdown_format.pack(pady=10, padx=20, fill="x")

        self.btn_load_source = ctk.CTkButton(sidebar, text="1. Обрати оригінальний файл", command=self._load_source_file)
        self.btn_load_source.pack(pady=10, padx=20, fill="x")

        self.btn_load_dir = ctk.CTkButton(sidebar, text="2. Обрати папку з фотографіями", command=self._load_images_dir)
        self.btn_load_dir.pack(pady=10, padx=20, fill="x")

        self.lbl_status = ctk.CTkLabel(sidebar, text="Очікування файлів...", text_color="gray", wraplength=240)
        self.lbl_status.pack(pady=15, padx=20)

        # Навігація
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(side="bottom", pady=20, padx=20, fill="x")

        self.btn_prev = ctk.CTkButton(nav_frame, text="< Попередній", state="disabled", command=self._prev_row)
        self.btn_prev.pack(side="left", expand=True, padx=(0, 5))

        self.btn_next = ctk.CTkButton(nav_frame, text="Наступний >", state="disabled", command=self._next_row)
        self.btn_next.pack(side="right", expand=True, padx=(5, 0))

        self.lbl_counter = ctk.CTkLabel(sidebar, text="- / -", font=("Arial", 14, "bold"))
        self.lbl_counter.pack(side="bottom", pady=5)

        # --- Головне вікно (Дані та Зображення) ---
        main_view = ctk.CTkFrame(self, fg_color="transparent")
        main_view.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main_view.grid_columnconfigure(0, weight=1)
        main_view.grid_rowconfigure(2, weight=1)

        # Блок інформації про товар
        info_frame = ctk.CTkFrame(main_view)
        info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        info_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(info_frame, text="Артикул:", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.lbl_article = ctk.CTkLabel(info_frame, text="-", font=("Arial", 16, "bold"), text_color="#2FA572")
        self.lbl_article.grid(row=0, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(info_frame, text="Назва:", font=("Arial", 14, "bold")).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.lbl_name = ctk.CTkLabel(info_frame, text="-", font=("Arial", 14), wraplength=600, justify="left")
        self.lbl_name.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        # Додано блок кольору
        ctk.CTkLabel(info_frame, text="Колір:", font=("Arial", 14, "bold")).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.lbl_color = ctk.CTkLabel(info_frame, text="-", font=("Arial", 14))
        self.lbl_color.grid(row=2, column=1, sticky="w", padx=10, pady=5)

        # Блок з оригінальними посиланнями
        self.links_frame = ctk.CTkScrollableFrame(main_view, height=100, label_text="Оригінальні посилання (з прайсу)")
        self.links_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Блок із завантаженими фотографіями
        self.img_scroll_frame = ctk.CTkScrollableFrame(main_view, label_text="Завантажені зображення (Локальні)")
        self.img_scroll_frame.grid(row=2, column=0, sticky="nsew")

    def _load_source_file(self):
        file_format = self.format_var.get()
        exts = [("Excel Files", "*.xls;*.xlsx")] if "Excel" in file_format else [("XML Files", "*.xml")]
        
        path = filedialog.askopenfilename(filetypes=exts)
        if not path:
            return
            
        self.source_file = path
        self.data_records = []
        self.current_index = 0
        
        try:
            if "Excel" in file_format:
                self._parse_excel(path)
            else:
                self._parse_xml(path)
                
            if not self.data_records:
                self.lbl_status.configure(text="Дані не знайдено. Перевірте формат.", text_color="red")
            else:
                self._check_ready_state()
                
        except Exception as e:
            self.lbl_status.configure(text=f"Помилка читання: {e}", text_color="red")

    def _parse_excel(self, path):
        df = pd.read_excel(path)
        
        cols = [str(c).lower() for c in df.columns]
        
        art_col = next((c for c in df.columns if str(c).strip().lower() in ['код для опт.', 'артикул', 'код', 'article']), None)
        name_col = next((c for c in df.columns if str(c).strip().lower() in ['найменування', 'название(ru)', 'название', 'title', 'назва']), None)
        color_col = next((c for c in df.columns if str(c).strip().lower() in ['колір', 'цвет', 'color']), None)
        link_cols = [c for c in df.columns if any(kw in str(c).lower() for kw in ['посилання', 'url', 'ссылка', 'сайт', 'фото'])]

        if not art_col:
            raise ValueError("Не знайдено колонку з Артикулом")

        for _, row in df.iterrows():
            if pd.isna(row.get(art_col)): continue
            
            article = str(row[art_col]).strip()
            name = str(row[name_col]).strip() if name_col else "Без назви"
            
            # Отримання кольору
            if color_col and pd.notna(row.get(color_col)):
                color = str(row[color_col]).strip()
            else:
                color = "Не вказано"
            
            links = []
            for lc in link_cols:
                val = str(row[lc]).strip()
                if val and val.lower() != 'nan':
                    urls = re.split(r'\||\n|,', val)
                    links.extend([u.strip() for u in urls if u.strip().startswith('http')])
            
            self.data_records.append({
                'article': article, 
                'name': name, 
                'color': color,
                'links': list(set(links))
            })

    def _parse_xml(self, path):
        tree = ET.parse(path)
        root = tree.getroot()
        
        for item in root.findall('.//item'):
            article = item.findtext('article', '').strip()
            if not article: continue
            
            name = item.findtext('title', '').strip()
            
            # Пошук кольору в тегах або параметрах XML
            color = "Не вказано"
            for param in item.findall('param') + item.findall('params/param'):
                param_name = param.get('name', '')
                if param_name and param_name.strip().lower() in ['колір', 'цвет', 'color']:
                    color = param.text.strip() if param.text else "Не вказано"
                    break
            
            links = []
            url = item.findtext('url', '').strip()
            if url: links.append(url)
            
            for pic in item.findall('picture') + item.findall('photos/image'):
                if pic.text and pic.text.strip():
                    links.append(pic.text.strip())
                    
            self.data_records.append({
                'article': article, 
                'name': name, 
                'color': color,
                'links': list(set(links))
            })

    def _load_images_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.images_dir = path
            self._check_ready_state()

    def _check_ready_state(self):
        if self.data_records and self.images_dir:
            self.lbl_status.configure(text=f"Успішно завантажено {len(self.data_records)} товарів.", text_color="#2FA572")
            self._update_ui_state()
            self._display_current_row()

    def _update_ui_state(self):
        if not self.data_records: return
        total = len(self.data_records)
        self.lbl_counter.configure(text=f"{self.current_index + 1} / {total}")
        self.btn_prev.configure(state="normal" if self.current_index > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.current_index < total - 1 else "disabled")

    def _prev_row(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._update_ui_state()
            self._display_current_row()

    def _next_row(self):
        if self.current_index < len(self.data_records) - 1:
            self.current_index += 1
            self._update_ui_state()
            self._display_current_row()

    def _open_link(self, url):
        webbrowser.open(url)

    def _display_current_row(self):
        for widget in self.links_frame.winfo_children(): widget.destroy()
        for widget in self.img_scroll_frame.winfo_children(): widget.destroy()
        self.image_references.clear()

        record = self.data_records[self.current_index]
        article = record['article']

        self.lbl_article.configure(text=article)
        self.lbl_name.configure(text=record['name'])
        self.lbl_color.configure(text=record['color']) # Відображаємо колір

        # --- Відображення посилань ---
        if record['links']:
            for i, url in enumerate(record['links']):
                btn = ctk.CTkButton(
                    self.links_frame, 
                    text=f"Відкрити посилання {i+1} у браузері", 
                    command=lambda u=url: self._open_link(u),
                    fg_color="#3498db", hover_color="#2980b9"
                )
                btn.pack(side="left", padx=10, pady=10)
        else:
            ctk.CTkLabel(self.links_frame, text="Оригінальних посилань не знайдено", text_color="gray").pack(pady=10)

        # --- Відображення локальних фотографій ---
        safe_name = "".join([c for c in article if c.isalnum() or c in ['-', '_']]).rstrip()
        
        pattern_base = os.path.join(self.images_dir, f"{safe_name}.*")
        pattern_indexed = os.path.join(self.images_dir, f"{safe_name}@*.*")
        
        matched_files = glob.glob(pattern_base) + glob.glob(pattern_indexed)

        if not matched_files:
            ctk.CTkLabel(self.img_scroll_frame, text="Локальних фотографій для цього артикулу не знайдено.", text_color="red").pack(pady=40)
            return

        for file_path in matched_files:
            try:
                pil_img = Image.open(file_path)
                pil_img.thumbnail((350, 350))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                self.image_references.append(ctk_img)
                
                frame = ctk.CTkFrame(self.img_scroll_frame, fg_color="transparent")
                frame.pack(side="left", padx=15, pady=15)
                
                lbl_img = ctk.CTkLabel(frame, image=ctk_img, text="")
                lbl_img.pack()
                
                filename = os.path.basename(file_path)
                ctk.CTkLabel(frame, text=filename, font=("Arial", 12)).pack(pady=5)
                
            except Exception as e:
                print(f"Failed to load {file_path}: {e}")

if __name__ == "__main__":
    app = OriginalFileTesterApp()
    app.mainloop()