import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
from io import BytesIO
from PIL import Image, ImageTk
from ddgs import DDGS
import webbrowser

def search_images_fallback(query: str) -> list:
    """Пошук зображень через DuckDuckGo (до 10 результатів)."""
    images = []
    try:
        short_query = query.replace("'", "")
        with DDGS() as ddgs:
            results = ddgs.images(
                short_query,
                region="wt-wt",
                safesearch="on",
                max_results=10,
                type_image="photo"
            )
            for result in results:
                img = result.get("image")
                if img:
                    images.append(img)
    except Exception as e:
        msg = str(e).lower()
        if "no results found" not in msg:
            print(f"DuckDuckGo Search Error ({query}) - {e}")
    return images

class ImageSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Тестер пошуку зображень DuckDuckGo")
        self.root.geometry("800x800")
        
        # Змінні для зберігання посилань на зображення, щоб їх не видалив збирач сміття
        self.image_references = []
        
        self._build_ui()

    def _build_ui(self):
        # Верхня панель з полем вводу та кнопкою
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top_frame, text="Запит:", font=("Arial", 12)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.entry_query = ttk.Entry(top_frame, font=("Arial", 12))
        self.entry_query.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_query.bind("<Return>", lambda event: self.start_search())

        self.btn_search = ttk.Button(top_frame, text="Шукати", command=self.start_search)
        self.btn_search.pack(side=tk.LEFT)

        self.lbl_status = ttk.Label(self.root, text="Введіть запит для пошуку.", font=("Arial", 10), foreground="gray")
        self.lbl_status.pack(side=tk.TOP, fill=tk.X, padx=10)

        # Область з прокруткою для відображення результатів
        container = ttk.Frame(self.root)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Прив'язка прокрутки коліщатком миші
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def clear_results(self):
        """Очищення попередніх результатів."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.image_references.clear()

    def start_search(self):
        query = self.entry_query.get().strip()
        if not query:
            return

        self.clear_results()
        self.btn_search.config(state=tk.DISABLED)
        self.lbl_status.config(text=f"Виконую пошук: '{query}'...", foreground="blue")
        
        # Запуск пошуку в окремому потоці, щоб не блокувати інтерфейс
        threading.Thread(target=self._search_thread_task, args=(query,), daemon=True).start()

    def _search_thread_task(self, query):
        image_urls = search_images_fallback(query)
        
        if not image_urls:
            self.root.after(0, self._update_status, "Зображень не знайдено або виникла помилка.", "red")
            self.root.after(0, lambda: self.btn_search.config(state=tk.NORMAL))
            return

        self.root.after(0, self._update_status, f"Знайдено {len(image_urls)} зображень. Завантаження...", "orange")

        # Завантаження та відображення кожної картинки
        for i, url in enumerate(image_urls, start=1):
            self._download_and_display_image(i, url)

        self.root.after(0, self._update_status, f"Готово. Знайдено {len(image_urls)} зображень.", "green")
        self.root.after(0, lambda: self.btn_search.config(state=tk.NORMAL))

    def _download_and_display_image(self, index, url):
        try:
            # Маскуємося під браузер для обходу базових блокувань хотлінків
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            img_data = response.content
            pil_image = Image.open(BytesIO(img_data))
            
            # Зміна розміру картинки для прев'ю (ширина 500px, збереження пропорцій)
            basewidth = 500
            wpercent = (basewidth / float(pil_image.size[0]))
            hsize = int((float(pil_image.size[1]) * float(wpercent)))
            pil_image = pil_image.resize((basewidth, hsize), Image.Resampling.LANCZOS)
            
            # Передача об'єкта в основний потік для створення віджета
            self.root.after(0, self._add_image_to_ui, index, pil_image, url)
            
        except Exception as e:
            error_msg = f"Помилка завантаження фото #{index}"
            self.root.after(0, self._add_error_to_ui, index, error_msg, url)

    def _add_image_to_ui(self, index, pil_image, url):
        # ImageTk.PhotoImage має створюватися в основному потоці
        tk_image = ImageTk.PhotoImage(pil_image)
        self.image_references.append(tk_image) # Зберігаємо референс

        card_frame = ttk.Frame(self.scrollable_frame, borderwidth=1, relief="solid")
        card_frame.pack(pady=10, padx=10, fill=tk.X)

        # Заголовок
        ttk.Label(card_frame, text=f"Результат #{index}", font=("Arial", 10, "bold")).pack(anchor="w", padx=5, pady=5)
        
        # Картинка
        img_label = ttk.Label(card_frame, image=tk_image)
        img_label.pack(padx=5, pady=5)
        
        # Посилання
        link_label = tk.Label(card_frame, text=url, font=("Arial", 9), fg="blue", cursor="hand2", wraplength=700)
        link_label.pack(anchor="w", padx=5, pady=5)
        link_label.bind("<Button-1>", lambda e, link=url: webbrowser.open(link))

    def _add_error_to_ui(self, index, error_msg, url):
        card_frame = ttk.Frame(self.scrollable_frame, borderwidth=1, relief="solid")
        card_frame.pack(pady=10, padx=10, fill=tk.X)
        
        ttk.Label(card_frame, text=f"Результат #{index} - {error_msg}", font=("Arial", 10, "bold"), foreground="red").pack(anchor="w", padx=5, pady=5)
        
        link_label = tk.Label(card_frame, text=url, font=("Arial", 9), fg="blue", cursor="hand2", wraplength=700)
        link_label.pack(anchor="w", padx=5, pady=5)
        link_label.bind("<Button-1>", lambda e, link=url: webbrowser.open(link))

    def _update_status(self, text, color="black"):
        self.lbl_status.config(text=text, foreground=color)

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageSearchApp(root)
    root.mainloop()