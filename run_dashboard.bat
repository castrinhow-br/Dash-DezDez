@echo off
IF EXIST .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)
python -m pip install -r requirements.txt
streamlit run app.py
pause
