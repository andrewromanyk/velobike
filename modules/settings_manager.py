import os
import toml

SETTINGS_FILE = "settings.toml"

# Стандартні налаштування для всіх джерел
DEFAULT_SETTINGS = {
    "veloportal": {
        "min_price": 0.0,
        "excluded_categories": []
    },
    "veloplaneta": {
        "min_price": 0.0,
        "excluded_categories": []
    },
    "author": {
        "min_price": 0.0,
        "excluded_categories": []
    },
    "bergamont": {
        "min_price": 0.0,
        "excluded_categories": []
    },
}

def load_settings() -> dict:
    """Завантажує налаштування з TOML файлу. Якщо файлу немає — створює дефолтний."""
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return toml.load(f)
    except Exception as e:
        print(f"Помилка читання settings.toml: {e}. Використовуються стандартні налаштування.")
        return DEFAULT_SETTINGS

def save_settings(settings_dict: dict):
    """Зберігає поточний словник налаштувань у TOML файл."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        toml.dump(settings_dict, f)

def get_source_settings(source_name: str) -> dict:
    """Отримує налаштування для конкретного джерела (з фолбеком на дефолт)."""
    settings = load_settings()
    if source_name not in settings:
        settings[source_name] = DEFAULT_SETTINGS.get(source_name, {})
    return settings[source_name]