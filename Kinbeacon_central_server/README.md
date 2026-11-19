# KinBeacon Central Server

The central orchestration server for the KinBeacon indoor localization and safety system.

## Setup & Installation

```bash
cd Kinbeacon_central_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the Server

```bash
# Start server with Uvicorn (binds to http://0.0.0.0:8000)
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Running Tests

```bash
./venv/bin/pytest -v
```

## Demo Seeding & Execution

1. **Seed demo venue (Zone 1 + single anchor + demo device):**
```bash
./venv/bin/python scripts/seed_venue.py --file scripts/seed_demo.json
```

2. **Run device search demo:**
```bash
./venv/bin/python scripts/run_demo.py --device KINBEACON-PHONE1
```
