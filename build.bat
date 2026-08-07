@echo off

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Compiling the executable...
pyinstaller --noconfirm --onefile --windowed --collect-all customtkinter --name "DataProcessor" --specpath "build_output" --workpath "build_output\temp" --distpath "build_output" gui.py
