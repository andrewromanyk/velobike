@echo off

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Compiling the executable...
pyinstaller --noconfirm --onefile --windowed --collect-all customtkinter --name "DataProcessor" --specpath "build" --workpath "build\temp" --distpath "build" gui.py
