# Start API dev server using uvicorn
$env:PYTHONPATH = "services/api;contracts/src"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
