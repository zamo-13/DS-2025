# DSA Moderation Dashboard — Assignment 3



## How to run 

**1. Unzip this folder** anywhere on your computer

**2. Open a terminal**
In the unziped folder open a Terminal. (Or navigate to the folder in you terminal)

**3. First time only: set up the environment**
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt (if libararies are not installed yet)
```
**4. Start the app**
```
streamlit run app.py
```
---

## Project structure

| File / folder | What it is |
| --- | --- |
| `app.py` | The dashboard itself — see its About tab for what each tab shows and how the numbers were made |
| `07_export_dashboard_data_eu.py` | The script that produces the 5 CSVs from the raw source data |
| `dashboard_data/` | The 5 real CSVs the app reads — regenerated from source data |
| `requirements.txt` | Python packages needed to run the app |
| `.venv/` | The isolated Python environment for this app (not committed to git) |

This app is self-contained: `app.py` only reads the exported CSVs, and the
export script only read from the local pc where the raw data was stored. I added the script here only for better understandig where the csv files came from. 