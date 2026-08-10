import os
import sys
import time
import requests
import threading
import traceback

# Головна константа версії вашої програми
CURRENT_VERSION = "v0.0.4" 
REPO_NAME = "andrewromanyk/velobike"
CHECK_INTERVAL_SECONDS = 15 * 60  # 15 хвилин

def cleanup_orphaned_files():
    """Видаляє тимчасові або старі файли після успішного оновлення або збою."""
    if not getattr(sys, 'frozen', False):
        return  # Не працює під час запуску через звичайний python script.py

    current_exe = sys.executable
    old_exe = current_exe + ".old"
    tmp_exe = current_exe + ".tmp"
    
    for file_path in [old_exe, tmp_exe]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Updater: Cleaned up {file_path}")
            except OSError:
                pass # Файл може бути ще заблокований антивірусом, видалимо наступного разу

def _check_and_download(status_callback):
    print("Updater: Checking for updates...")

    if not getattr(sys, 'frozen', False):
        status_callback(f"Версія: {CURRENT_VERSION} (Dev)", False)
        return

    current_exe = sys.executable
    old_exe = current_exe + ".old"
    tmp_exe = current_exe + ".tmp"

    # Якщо ми вже завантажили оновлення і перейменували файли в цій сесії
    if os.path.exists(old_exe):
        status_callback("Нова версія доступна. Перезапустіть програму, аби оновити", True)
        return

    api_url = f"https://api.github.com/repos/{REPO_NAME}/releases/latest"
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        latest_version = data.get("tag_name", "")
        
        if not latest_version or latest_version == CURRENT_VERSION:
            status_callback(f"Версія: {CURRENT_VERSION}", False)
            return

        # Шукаємо .exe серед файлів релізу
        exe_url = None
        for asset in data.get("assets", []):
            if asset["name"].endswith(".exe"):
                exe_url = asset["browser_download_url"]
                break
                
        if not exe_url:
            return

        status_callback(f"Завантаження оновлення {latest_version}...", False)

        # 1. Безпечне завантаження у .tmp файл
        with requests.get(exe_url, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(tmp_exe, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # 2. Атомарне перейменування (тільки якщо завантаження успішне на 100%)
        os.rename(current_exe, old_exe)
        os.rename(tmp_exe, current_exe)

        # 3. Сповіщення інтерфейсу
        status_callback("Нова версія доступна. Перезапустіть програму, аби оновити", True)

    except Exception as e:
        print(f"Updater Error: {traceback.format_exc()}")
        status_callback(f"Версія: {CURRENT_VERSION}", False)

def _update_loop(status_callback):
    """Безкінечний цикл перевірки оновлень."""
    cleanup_orphaned_files()
    while True:
        _check_and_download(status_callback)
        time.sleep(CHECK_INTERVAL_SECONDS)

def start_background_updater(status_callback):
    """Запускає процес у демонізованому потоці (вимкнеться разом із програмою)."""
    t = threading.Thread(target=_update_loop, args=(status_callback,), daemon=True)
    t.start()