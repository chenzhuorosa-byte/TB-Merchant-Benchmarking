# Talabat Merchant Scraper

A web scraper for an outstanding Food&Delivery player. Point it at any restaurant listing page and it collects merchant data from both the listing cards and each restaurant's detail page, then exports everything to a formatted Excel file.

Runs locally in your browser — no cloud account needed.

---

## What it scrapes

**From the listing page (per card):**
- Restaurant name, cuisine type, rating
- Delivery time, delivery fee, minimum order

**From each restaurant's detail page:**
- Area (neighbourhood), full address
- GPS coordinates (latitude & longitude)
- Payment methods (Visa, Mastercard, KNET, Cash)
- Open/closed status

---

## Setup (first time only)

### 1. Install Python
Download Python 3.10 or newer from https://www.python.org/downloads/

> ✅ During installation, tick **"Add Python to PATH"**

### 2. Clone this repo
```
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd "YOUR_REPO_NAME"
```

### 3. Install dependencies

**Windows** — double-click `install.bat`. Done.

**Mac / Linux:**
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

> ⚠️ The `playwright install chromium` step is required — it downloads the browser the scraper uses. Without it, scraping won't work.

---

## Running the app

**Windows:**
```
.venv\Scripts\activate
python app.py
```

**Mac / Linux:**
```
source .venv/bin/activate
python app.py
```

Then open your browser and go to: **http://localhost:5000**

Leave the terminal open while using the app — closing it stops the server.

---

## How to use

**Step 1 — Analyze**
- Paste a Talabat listing URL (e.g. a city area page)
- Paste one example restaurant detail URL (any single restaurant page)
- Click **Analyze** and wait ~20 seconds

**Step 2 — Select fields**
- Tick the data fields you want to collect
- Set how many listing pages to scrape (start with 1 to test)

**Step 3 — Scrape**
- Click **Start Scraping**
- Watch two progress bars: blue = collecting restaurant list, green = visiting each restaurant page
- When done, click **Download Excel**

---

## Example URLs to paste

| Field | Example |
|-------|---------|
| Listing URL | `https://www.talabat.com/kuwait/restaurants/22/mirqab` |
| Detail URL | Any single restaurant page on talabat.com/kuwait/... |

---

## Resuming a paused session

If scraping is interrupted, scroll down to **Previous Sessions** on the main page and click **Resume**. It picks up exactly where it stopped.

---

## Troubleshooting

**"0 restaurants found" after Analyze**
Talabat may have detected the headless browser. Open `scraper/listing_scraper.py` and `scraper/detail_scraper.py`, find `headless=True` in the `_get_html()` function, and change it to `headless=False`. This opens a visible Chrome window during scraping.

**App won't start**
Make sure you activated the virtual environment first (the `.venv\Scripts\activate` or `source .venv/bin/activate` step).

**`playwright` command not found**
Run `pip install playwright` then `playwright install chromium` again inside the activated virtual environment.
