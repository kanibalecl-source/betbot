# ROCKET V8 ENTERPRISE ACTIVATION

This package extends the working V7 stack with:

1. Enterprise data feed connectors
   - Opta
   - StatsBomb
   - tracking data
   - Betfair liquidity
   - premium sharp feeds

2. AI research layer
   - transformer-style sequence model
   - RL betting policy agent
   - temporal neural-net-style model
   - Bayesian uncertainty layer

3. Distributed infrastructure
   - Redis queue support when `REDIS_URL` exists
   - Kafka event publishing when `KAFKA_BOOTSTRAP_SERVERS` exists
   - async workers
   - distributed inference
   - safe in-memory fallback when infrastructure is not configured

## Main entry point

```python
from rocket_v8_enterprise_orchestrator import RocketV8EnterpriseOrchestrator

v8 = RocketV8EnterpriseOrchestrator()
result = v8.analyze_fixture(
    fixture_id="12345",
    home_xg=1.55,
    away_xg=1.10,
    market="OVER_2_5",
    bookmaker_odds=1.95,
)
print(result)
```

## Enterprise feeds

Proprietary sources require credentials/contracts. Configure environment variables:

```env
OPTA_BASE_URL=
OPTA_API_KEY=
STATSBOMB_BASE_URL=
STATSBOMB_API_KEY=
TRACKING_BASE_URL=
TRACKING_API_KEY=
BETFAIR_BASE_URL=
BETFAIR_APP_KEY=
BETFAIR_SESSION_TOKEN=
SHARP_FEED_BASE_URL=
SHARP_FEED_API_KEY=
REDIS_URL=
KAFKA_BOOTSTRAP_SERVERS=
```

Without credentials, V8 uses local snapshots from:

```text
data/providers/opta/<fixture_id>.json
data/providers/statsbomb/<fixture_id>.json
data/providers/tracking/<fixture_id>.json
data/providers/betfair_liquidity/<fixture_id>.json
data/providers/premium_sharp/<fixture_id>.json
```

No fake premium data is invented. Missing credentials are reported clearly and the V7/V8 core still runs.
