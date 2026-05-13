
ROCKET V9 - ODDS API FULL INTEGRATION

1. Install requirements

pip install -r requirements.txt

2. Create .env file

Copy:
.env.example

to:
.env

3. Add your key

ODDS_API_KEY=YOUR_REAL_KEY

4. Run orchestrator

python rocket_v9/orchestrator_v9.py

5. What is enabled

- OddsAPI market intelligence
- Multi bookmaker aggregation
- EV calculation
- Edge calculation
- CLV tracking
- Market comparison
- Value detection

6. IMPORTANT

Bookmaker odds DO NOT create predictions.

The AI model creates probability.

OddsAPI is only:
- market benchmark
- line movement intelligence
- value comparison layer
