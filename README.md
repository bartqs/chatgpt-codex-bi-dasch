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

## Product page

Navigate to `/product` to analyse manufacturer performance. Use the year and
branch filters (defaulting to the latest year and branches L51/L52) to refresh
the manufacturer table. Selecting a manufacturer loads a combined turnover,
margin, and quantity chart for the available months.
