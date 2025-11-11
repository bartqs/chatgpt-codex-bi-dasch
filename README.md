# Inter Cars BI Dashboard

This repository contains a Dash application for the Inter Cars BI dashboard. The
app has been refactored to use the Dash Pages architecture while preserving the
original visuals, styling, and business logic.

## Getting started

Follow the steps below to run the application locally:

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the Dash app:
   ```bash
   python app.py
   ```
4. Open the dashboard in your browser:
   [http://127.0.0.1:8050/](http://127.0.0.1:8050/)

Ensure that the MySQL database referenced in the application is accessible
before launching the app.

## Data refresh behaviour

Every analytics page now loads data from MySQL on demand. The summary,
product, advisor, and customer pages each expose a “Atnaujinti duomenis”
button alongside the existing filters. Clicking the button clears all
in-memory caches and re-runs the relevant queries so the UI immediately
reflects newly ingested rows. When the app process starts the first page
visit triggers a fresh read as well. Default “latest month/year” selections
are now derived from the current database contents via `MAX` calculations,
so the controls and visuals automatically advance when new periods arrive.

## Updated files

- `data/app_data.py` – replaces module-level DataFrame loads with on-demand
  MySQL helpers and provides `reset_data_caches` for manual refreshes.
- `pages/overview.py` – sources filter defaults from live data and wires the
  refresh button to clear caches before re-running queries.
- `pages/product_page.py` & `pages/product_callbacks.py` – fetch product
  metadata per render, expose a refresh button, and make all data callbacks
  re-query MySQL when triggered.
- `pages/sales_advisor.py` – mirrors the new refresh workflow for advisor
  visuals and dropdowns.
- `pages/customers.py` – ensures customer filters, charts, and exports always
  read from the latest database state and participate in manual refreshes.

## Klientų apžvalga

Trečiasis puslapis „Klientų apžvalga“ (adresu `/customers`) leidžia analizuoti
konkretaus kliento rezultatus pagal pasirinktus metus ir metrikas. Puslapio
filtrai:

- **Pardavimų vadybininkas** – kelių pasirinkimų sąrašas, ribojantis klientų
  parinktis pagal vadybininką.
- **Klientas** – kelių pasirinkimų laukas; duomenys užkraunami tik tuomet, kai
  parinktas vienas konkretus klientas.
- **Kliento kodas** – rodomi tik su pasirinktu klientu susieti kodai.
- **Metai** – kelių metų palyginimas (paskutinis metų rinkinys parenkamas pagal
  naujausią turimą metus).
- **Matas** – galima perjungti tarp APYVARTA, PAJAMOS, MARŽA % ir KIEKIS.

Grafikas rodo mėnesinę dinamiką pagal pasirinktus metus, o lentelė pateikia
tas pačias reikšmes su „suma“ eilute. Mygtukas „Eksportuoti į Excel“ leidžia
išsisaugoti filtruotą lentelę (failo pavadinime įtraukiamas kliento vardas ir
metrika).
