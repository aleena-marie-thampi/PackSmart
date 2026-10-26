# PackSmart – Intelligent Packing Assistant

Flask web app that builds the best packing list under a luggage weight limit.

## Project structure
```
packsmart/
├── app.py            Flask server, REST API, input validation, sample data
├── packing.py        CSP + backtracking (branch & bound)
├── requirements.txt
├── data.json         created automatically (your saved trip)
├── templates/index.html
└── static/ style.css, app.js
```

## Windows setup (Command Prompt or PowerShell)
1. Install Python 3.10+ from https://www.python.org (tick "Add Python to PATH").
2. Open a terminal in the `packsmart` folder and run:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
   (PowerShell blocked the activate script? Run `Set-ExecutionPolicy -Scope Process RemoteSigned` first.)
3. Open http://127.0.0.1:5000 in your browser. Stop the server with Ctrl+C.

## How the algorithms work
- **CSP**: each item is a 0/1 variable. Constraints: total weight <= limit; essential items = 1.
  Essentials get domain {1}; items too heavy to fit beside the essentials get domain {0} (forward checking).
- **Backtracking**: assigns items one by one (pack, then leave), backtracks on capacity violations, and prunes
  any branch whose optimistic score bound cannot beat the best list found. Returns the max-priority feasible list.
