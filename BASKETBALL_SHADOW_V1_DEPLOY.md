# Basketball Shadow v1.2 / server v20.2

The module is isolated from football, volleyball, handball and tennis.
Uploading the package does not start it automatically.

Railway variables required for activation:

```text
BETBOT_BASKETBALL_ENABLED=1
BETBOT_BASKETBALL_SHADOW_ONLY=1
BASKETBALL_API_SPORTS_KEY=<server secret>
BETBOT_BASKETBALL_POLL_MINUTES=30
BETBOT_BASKETBALL_BACKFILL_DAYS=30
BETBOT_BASKETBALL_LOOKAHEAD_DAYS=7
BETBOT_BASKETBALL_BACKFILL_DAYS_PER_CYCLE=2
BETBOT_BASKETBALL_BACKFILL_RETRY_DATES_PER_CYCLE=1
BETBOT_BASKETBALL_MAX_REQUESTS_PER_CYCLE=40
BETBOT_BASKETBALL_ENTITLEMENT_CIRCUIT_THRESHOLD=3
BETBOT_BASKETBALL_MAX_ODDS_REQUESTS_PER_CYCLE=20
BETBOT_BASKETBALL_MIN_REQUEST_INTERVAL_SECONDS=0.25
```

`API_SPORTS_KEY` can be used instead of `BASKETBALL_API_SPORTS_KEY` when the
same API-Sports account is licensed for basketball.

Expected production logs:

```text
START basketball_shadow: ... -m basketball_v1.runtime
BASKETBALL v1.2 SHADOW START ...
BASKETBALL_SHADOW_CYCLE
HEARTBEAT ... basketball_shadow=True
```

Safety guarantees:

- SQLite storage: `/data/basketball/basketball_shadow.sqlite3`
- no training admission
- no model candidate creation or promotion
- no real-money execution
- invalid records are quarantined
- finished and void games are settled automatically
- overtime is stored explicitly
- existing sport databases are not read or modified
- the 30-day backfill advances by two days per cycle and survives restarts
- quota, authentication and rate-limit responses open a circuit breaker
- date-scoped plan restrictions are skipped after another date succeeds
- three entitlement failures without any successful date open the circuit
- the request budget prevents retry storms and excessive API consumption
- provider quota headers and sanitized failure categories are persisted
