import os
import datetime
import threading
import ctypes
import customtkinter as ctk
from tkinter import filedialog

# Імпорт ваших модулів
from modules import veloportal, veloplaneta, globals, settings_manager, author, bergamont

class Application(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(globals.UI_WINDOW_TITLE)
        self.geometry(globals.UI_WINDOW_GEOMETRY) 
        
        ctk.set_appearance_mode("Light")
        
        self.input_file = ""
        self.output_dir = os.path.join(os.getcwd(), "результат")
        self.settings_window = None

        self._build_ui()

    def _build_ui(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.place(relx=0.5, rely=0.5, anchor="center")
        
        self.main_container.grid_columnconfigure((0, 1, 2), weight=1, uniform="col", minsize=240)

        # ==========================================
        # ROW 0: The Status / Info Labels
        # ==========================================
        frame_src_header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        frame_src_header.grid(row=0, column=0, padx=10, pady=(0, 10), sticky="s")
        
        self.lbl_src_title = ctk.CTkLabel(frame_src_header, text=globals.UI_STR_LBL_SOURCE, text_color=globals.UI_COLOR_TEXT, font=globals.UI_FONT_BOLD)
        self.lbl_src_title.pack(side="left", padx=(0, 5))
        
        self.btn_settings = ctk.CTkButton(
            frame_src_header, 
            text=globals.UI_STR_BTN_SETTINGS, 
            width=30, 
            height=20, 
            font=("Arial", 12),
            command=self._open_settings
        )
        self.btn_settings.pack(side="left")

        self.lbl_input = ctk.CTkLabel(self.main_container, text=globals.UI_STR_LBL_NO_FILE, text_color=globals.UI_COLOR_TEXT_DIM, font=globals.UI_FONT_DEFAULT, wraplength=220)
        self.lbl_input.grid(row=0, column=1, padx=10, pady=(0, 10), sticky="s")

        self.lbl_output = ctk.CTkLabel(self.main_container, text=self.output_dir, text_color=globals.UI_COLOR_TEXT, font=globals.UI_FONT_DEFAULT, wraplength=220)
        self.lbl_output.grid(row=0, column=2, padx=10, pady=(0, 10), sticky="s")

        # ==========================================
        # ROW 1: The Interactive Controls
        # ==========================================
        self.source_var = ctk.StringVar(value="veloportal")
        self.dropdown_source = ctk.CTkOptionMenu(
            self.main_container, 
            values=["veloportal", "veloplaneta", "author", "bergamont"],
            variable=self.source_var, 
            font=globals.UI_FONT_DEFAULT,
            dropdown_font=globals.UI_FONT_DEFAULT,
            command=self._on_source_change # Змінено обробник
        )
        self.dropdown_source.grid(row=1, column=0, padx=10, pady=0, sticky="n")

        self.btn_input = ctk.CTkButton(self.main_container, text=globals.UI_STR_BTN_INPUT, font=globals.UI_FONT_DEFAULT, command=self._select_input)
        self.btn_input.grid(row=1, column=1, padx=10, pady=0, sticky="n")

        self.btn_output = ctk.CTkButton(self.main_container, text=globals.UI_STR_BTN_OUTPUT, font=globals.UI_FONT_DEFAULT, command=self._select_output)
        self.btn_output.grid(row=1, column=2, padx=10, pady=0, sticky="n")

        # ==========================================
        # ROW 2: Output Filename Field
        # ==========================================
        frame_filename = ctk.CTkFrame(self.main_container, fg_color="transparent")
        frame_filename.grid(row=2, column=2, padx=10, pady=(35, 0), sticky="n")

        ctk.CTkLabel(frame_filename, text=globals.UI_STR_LBL_FILENAME, text_color=globals.UI_COLOR_TEXT, font=globals.UI_FONT_DEFAULT).pack(pady=(0, 5))
        self.entry_filename = ctk.CTkEntry(frame_filename, width=220, font=globals.UI_FONT_DEFAULT)
        self.entry_filename.pack()
        
        self._update_default_filename(self.source_var.get())

        # ==========================================
        # ROW 3-6: Execution Controls & Dynamic Elements
        # ==========================================
        self.btn_run = ctk.CTkButton(
            self.main_container, 
            text=globals.UI_STR_BTN_RUN, 
            command=self._run_pipeline, 
            font=globals.UI_FONT_TITLE,
            fg_color=globals.UI_COLOR_BTN_READY,
            hover_color=globals.UI_COLOR_BTN_HOVER,
            width=220,
            height=45
        )
        self.btn_run.grid(row=3, column=0, columnspan=3, pady=(60, 10))

        self.progress_bar = ctk.CTkProgressBar(self.main_container, width=220, mode="indeterminate", progress_color=globals.UI_COLOR_BTN_READY)
        
        self.lbl_status = ctk.CTkLabel(self.main_container, text=globals.UI_STR_STATUS_READY, text_color=globals.UI_COLOR_TEXT, font=globals.UI_FONT_BOLD)
        self.lbl_status.grid(row=5, column=0, columnspan=3, pady=(10, 0))

        self.btn_open_folder = ctk.CTkButton(
            self.main_container, 
            text=getattr(globals, "UI_STR_BTN_OPEN_FOLDER", "Відкрити папку результатів"), 
            command=self._open_output_folder, 
            font=globals.UI_FONT_DEFAULT,
            fg_color="gray",
            hover_color="darkgray"
        )

    # --- Settings Window Logic ---
    def _open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = ctk.CTkToplevel(self)
            current_source = self.source_var.get()
            
            self.settings_window.title(globals.UI_STR_SETTINGS_TITLE.format(source=current_source))
            self.settings_window.geometry("500x500")
            self.settings_window.attributes("-topmost", True)
            self.settings_window.grab_set() 
            
            source_settings = settings_manager.get_source_settings(current_source)
            min_price_val = source_settings.get("min_price", 0.0)
            excluded_cats_list = source_settings.get("excluded_categories", [])

            ctk.CTkLabel(self.settings_window, text=globals.UI_STR_LBL_MIN_PRICE, font=globals.UI_FONT_BOLD).pack(pady=(20, 5))
            entry_min_price = ctk.CTkEntry(self.settings_window, width=200)
            entry_min_price.insert(0, str(min_price_val))
            entry_min_price.pack()

            ctk.CTkLabel(self.settings_window, text=globals.UI_STR_LBL_EXCLUDED_CATS, font=globals.UI_FONT_BOLD).pack(pady=(20, 5))
            
            scroll_frame = ctk.CTkScrollableFrame(self.settings_window, width=400, height=200)
            scroll_frame.pack(pady=5, padx=20, fill="x")
            
            category_entries = []

            def add_category_row(val=""):
                row_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
                
                entry = ctk.CTkEntry(row_frame, width=330)
                entry.insert(0, val)
                entry.pack(side="left", padx=(0, 5))
                
                def delete_row():
                    row_frame.destroy()
                    category_entries.remove(entry)
                    
                btn_del = ctk.CTkButton(
                    row_frame, 
                    text=globals.UI_STR_BTN_DEL_CAT, 
                    width=30, 
                    fg_color=globals.UI_COLOR_BTN_DELETE,        # Using global
                    hover_color=globals.UI_COLOR_BTN_DELETE_HOVER, # Using global
                    command=delete_row
                )
                btn_del.pack(side="right")
                
                category_entries.append(entry)

            for cat in excluded_cats_list:
                add_category_row(cat)

            ctk.CTkButton(
                self.settings_window, 
                text=globals.UI_STR_BTN_ADD_CAT, 
                fg_color="gray", 
                hover_color="darkgray",
                command=add_category_row
            ).pack(pady=5)

            def save_and_close():
                try:
                    new_min_price = float(entry_min_price.get().strip() or 0.0)
                except ValueError:
                    new_min_price = 0.0
                
                new_excluded_cats = []
                for entry_widget in category_entries:
                    val = entry_widget.get().strip()
                    if val:
                        new_excluded_cats.append(val)

                all_settings = settings_manager.load_settings()
                if current_source not in all_settings:
                    all_settings[current_source] = {}
                    
                all_settings[current_source]["min_price"] = new_min_price
                all_settings[current_source]["excluded_categories"] = new_excluded_cats
                settings_manager.save_settings(all_settings)
                
                if self.settings_window:
                    self.settings_window.destroy()
                    self.settings_window = None

            ctk.CTkButton(
                self.settings_window, 
                text=globals.UI_STR_BTN_SAVE, 
                command=save_and_close, 
                fg_color=globals.UI_COLOR_BTN_READY, 
                hover_color=globals.UI_COLOR_BTN_HOVER
            ).pack(pady=(20, 10))
            
        else:
            if self.settings_window:
                self.settings_window.focus()

    # --- Core Logic Methods ---
    def _select_input(self):
        current_source = self.source_var.get()
        
        # Dynamically set the allowed file types based on the dropdown selection
        if current_source in ["veloplaneta", "bergamont"]:
            allowed_types = [("Excel Files", "*.xls;*.xlsx"), ("All Files", "*.*")]
        else:
            allowed_types = [("XML Files", "*.xml"), ("All Files", "*.*")]
            
        path = filedialog.askopenfilename(
            title=getattr(globals, 'UI_STR_DIALOG_FILE', 'Оберіть файл'), 
            filetypes=allowed_types
        )
        
        if path:
            self.input_file = os.path.normpath(path)
            self.lbl_input.configure(text=os.path.basename(self.input_file), text_color=globals.UI_COLOR_TEXT)

    def _select_output(self):
        path = filedialog.askdirectory(title=globals.UI_STR_DIALOG_OUT, initialdir=self.output_dir)
        if path:
            self.output_dir = os.path.normpath(path)
            self.lbl_output.configure(text=self.output_dir)

    def _on_source_change(self, choice):
        self._update_default_filename(choice)
        
        if choice == "author":
            self.btn_input.configure(state="disabled")
            self.lbl_input.configure(text=globals.UI_STR_AUTHOR_URL_INFO, text_color=globals.UI_COLOR_TEXT_DIM)
            self.input_file = globals.AUTHOR_XML_URL # Using global
        else:
            self.btn_input.configure(state="normal")
            if self.input_file == globals.AUTHOR_XML_URL: # Using global
                self.input_file = ""
                self.lbl_input.configure(text=globals.UI_STR_LBL_NO_FILE, text_color=globals.UI_COLOR_TEXT_DIM)

    def _update_default_filename(self, source_name):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        default_name = f"{source_name}_{date_str}.xlsx"
        self.entry_filename.delete(0, "end")
        self.entry_filename.insert(0, default_name)

    def _open_output_folder(self):
        if os.path.exists(self.output_dir):
            os.startfile(self.output_dir)

    def _update_progress_text(self, text):
        self.after(0, lambda: self.lbl_status.configure(text=text))

    def _run_pipeline(self):
        if not self.input_file:
            self.lbl_status.configure(text=globals.UI_STR_ERR_NO_INPUT, text_color=globals.UI_COLOR_STATUS_ERR)
            return
            
        target_filename = self.entry_filename.get().strip()
        if not target_filename:
            self.lbl_status.configure(text=globals.UI_STR_ERR_NO_FILENAME, text_color=globals.UI_COLOR_STATUS_ERR)
            return

        current_source = self.source_var.get()
        
        # --- File Extension Validation ---
        if current_source != "author":
            _, ext = os.path.splitext(self.input_file)
            ext = ext.lower()
            
            if current_source == "veloportal" and ext != ".xml":
                self.lbl_status.configure(text=getattr(globals, 'UI_STR_ERR_WRONG_EXT_XML', 'Помилка формату'), text_color=globals.UI_COLOR_STATUS_ERR)
                return
                
            if current_source in ["veloplaneta", "bergamont"] and ext not in [".xls", ".xlsx"]:
                self.lbl_status.configure(text=getattr(globals, 'UI_STR_ERR_WRONG_EXT_XLS', 'Помилка формату'), text_color=globals.UI_COLOR_STATUS_ERR)
                return
        # ---------------------------------

        self.btn_open_folder.grid_remove()
        self.btn_run.configure(state="disabled", text=globals.UI_STR_BTN_PROCESSING)
        self.lbl_status.configure(text=globals.UI_STR_STATUS_WORKING, text_color=globals.UI_COLOR_STATUS_WARN)

        self.progress_bar.grid(row=4, column=0, columnspan=3, pady=(0, 5))
        self.progress_bar.start()

        source_settings = settings_manager.get_source_settings(current_source)

        threading.Thread(target=self._execute_worker, args=(current_source, target_filename, source_settings), daemon=True).start()

    def _execute_worker(self, source_name, target_filename, settings):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            self._update_progress_text(globals.UI_STR_PROGRESS_PROCESSING) # Using global

            if source_name == "veloportal":
                active_module = veloportal
            elif source_name == "veloplaneta":
                active_module = veloplaneta
            elif source_name == "author":
                active_module = author
            elif source_name == "bergamont":
                active_module = bergamont
            else:
                raise ValueError(globals.UI_STR_ERR_UNKNOWN_SOURCE) # Using global

            df = active_module.parse_to_dataframe(
                source_path=self.input_file, 
                min_price=settings.get('min_price', 0.0),
                excluded_categories=settings.get('excluded_categories', []),
                output_dir=self.output_dir
            )
            
            self._update_progress_text(globals.UI_STR_PROGRESS_DOWNLOADING) # Using global

            active_module.export_to_template(
                df=df, 
                output_dir=self.output_dir, 
                file_name=target_filename,
                status_callback=self._update_progress_text
            )
            
            success_msg = globals.UI_STR_SUCCESS.format(target_filename=target_filename)
            self.after(0, self._process_complete, success_msg, globals.UI_COLOR_STATUS_OK, True)
            
        except Exception as e:
            err_msg = globals.UI_STR_ERR_GENERIC.format(error=str(e))
            self.after(0, self._process_complete, err_msg, globals.UI_COLOR_STATUS_ERR, False)

    def _process_complete(self, message, color, success=False):
        self.progress_bar.stop()
        self.progress_bar.grid_remove()

        self.lbl_status.configure(text=message, text_color=color)
        self.btn_run.configure(state="normal", text=globals.UI_STR_BTN_RUN)
        
        if success:
            self.btn_open_folder.grid(row=6, column=0, columnspan=3, pady=(15, 0))

if __name__ == "__main__":
    if os.name == 'nt':
        myappid = 'veloportal.dataprocessor.app.1.0' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = Application()
    app.mainloop()