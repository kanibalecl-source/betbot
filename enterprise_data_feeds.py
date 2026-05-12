from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        if isinstance(v, str) and v.endswith('%'):
            v = v[:-1]
        return float(v)
    except Exception:
        return default


@dataclass
class EnterpriseFeedResult:
    provider: str
    ok: bool
    payload: Dict[str, Any]
    mode: str
    error: Optional[str] = None
    status_code: Optional[int] = None
    fetched_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EnterpriseDataFeeds:
    """Enterprise feed hub for premium football data.

    This module is production-safe: proprietary providers such as Opta,
    StatsBomb, Betfair and sharp feeds require credentials/contracts. When keys
    are not configured, the connector does not fake data; it falls back to local
    snapshots under data/providers/<provider>/<fixture_id>.json and returns a
    clear status. That lets the bot run immediately while still being ready for
    real enterprise feeds the moment credentials are supplied.

    Environment variables supported:
    - OPTA_BASE_URL, OPTA_API_KEY
    - STATSBOMB_BASE_URL, STATSBOMB_API_KEY
    - TRACKING_BASE_URL, TRACKING_API_KEY
    - BETFAIR_BASE_URL, BETFAIR_APP_KEY, BETFAIR_SESSION_TOKEN
    - SHARP_FEED_BASE_URL, SHARP_FEED_API_KEY
    """

    PROVIDERS = ['opta', 'statsbomb', 'tracking', 'betfair_liquidity', 'premium_sharp']

    def __init__(self, data_dir: str | Path = 'data', timeout: int = 14, retries: int = 2):
        self.data_dir = Path(data_dir)
        self.provider_dir = self.data_dir / 'providers'
        self.cache_dir = self.data_dir / 'enterprise_feeds_cache'
        self.provider_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.retries = retries

    def fetch_all(self, fixture_id: str | int, providers: Optional[List[str]] = None) -> Dict[str, Any]:
        providers = providers or self.PROVIDERS
        results = []
        for provider in providers:
            try:
                if provider == 'opta':
                    res = self.fetch_opta(fixture_id)
                elif provider == 'statsbomb':
                    res = self.fetch_statsbomb(fixture_id)
                elif provider == 'tracking':
                    res = self.fetch_tracking(fixture_id)
                elif provider == 'betfair_liquidity':
                    res = self.fetch_betfair_liquidity(fixture_id)
                elif provider == 'premium_sharp':
                    res = self.fetch_premium_sharp(fixture_id)
                else:
                    res = EnterpriseFeedResult(provider, False, {}, 'unknown', f'unknown provider {provider}', fetched_at=_now())
                results.append(res.to_dict())
            except Exception as exc:
                results.append(EnterpriseFeedResult(provider, False, {}, 'error', str(exc), fetched_at=_now()).to_dict())
        merged = self.merge(results)
        merged['enterprise_feed_results'] = results
        self._cache(f'enterprise_{fixture_id}', merged)
        return merged

    def fetch_opta(self, fixture_id: str | int) -> EnterpriseFeedResult:
        return self._fetch_http_or_local(
            provider='opta', fixture_id=fixture_id,
            base_env='OPTA_BASE_URL', key_env='OPTA_API_KEY',
            endpoint=f'/fixtures/{fixture_id}/advanced'
        )

    def fetch_statsbomb(self, fixture_id: str | int) -> EnterpriseFeedResult:
        return self._fetch_http_or_local(
            provider='statsbomb', fixture_id=fixture_id,
            base_env='STATSBOMB_BASE_URL', key_env='STATSBOMB_API_KEY',
            endpoint=f'/matches/{fixture_id}/events'
        )

    def fetch_tracking(self, fixture_id: str | int) -> EnterpriseFeedResult:
        return self._fetch_http_or_local(
            provider='tracking', fixture_id=fixture_id,
            base_env='TRACKING_BASE_URL', key_env='TRACKING_API_KEY',
            endpoint=f'/fixtures/{fixture_id}/tracking'
        )

    def fetch_premium_sharp(self, fixture_id: str | int) -> EnterpriseFeedResult:
        return self._fetch_http_or_local(
            provider='premium_sharp', fixture_id=fixture_id,
            base_env='SHARP_FEED_BASE_URL', key_env='SHARP_FEED_API_KEY',
            endpoint=f'/fixtures/{fixture_id}/signals'
        )

    def fetch_betfair_liquidity(self, fixture_id: str | int) -> EnterpriseFeedResult:
        local = self._local('betfair_liquidity', fixture_id)
        if local.ok:
            return local
        base = os.getenv('BETFAIR_BASE_URL')
        app_key = os.getenv('BETFAIR_APP_KEY')
        session = os.getenv('BETFAIR_SESSION_TOKEN')
        if not (base and app_key and session):
            return EnterpriseFeedResult('betfair_liquidity', False, {}, 'missing_credentials', 'BETFAIR_* env vars not configured', fetched_at=_now())
        url = base.rstrip('/') + '/exchange/betting/json-rpc/v1'
        payload = {
            'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listMarketBook', 'id': 1,
            'params': {'marketIds': [str(fixture_id)], 'priceProjection': {'priceData': ['EX_BEST_OFFERS', 'EX_TRADED']}}
        }
        headers = {'X-Application': app_key, 'X-Authentication': session, 'content-type': 'application/json'}
        return self._post_json('betfair_liquidity', url, payload, headers)

    def _fetch_http_or_local(self, provider: str, fixture_id: str | int, base_env: str, key_env: str, endpoint: str) -> EnterpriseFeedResult:
        local = self._local(provider, fixture_id)
        if local.ok:
            return local
        base = os.getenv(base_env)
        key = os.getenv(key_env)
        if not (base and key):
            return EnterpriseFeedResult(provider, False, {}, 'missing_credentials', f'{base_env}/{key_env} not configured', fetched_at=_now())
        url = base.rstrip('/') + endpoint
        headers = {'Authorization': f'Bearer {key}', 'x-api-key': key, 'Accept': 'application/json'}
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                r = requests.get(url, headers=headers, timeout=self.timeout)
                if 200 <= r.status_code < 300:
                    payload = r.json() if r.content else {}
                    payload = self.normalize_provider_payload(provider, fixture_id, payload)
                    return EnterpriseFeedResult(provider, True, payload, 'http', status_code=r.status_code, fetched_at=_now())
                last_err = f'HTTP {r.status_code}: {r.text[:180]}'
            except Exception as exc:
                last_err = str(exc)
            time.sleep(0.5 * (attempt + 1))
        return EnterpriseFeedResult(provider, False, {}, 'http_error', last_err, fetched_at=_now())

    def _post_json(self, provider: str, url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> EnterpriseFeedResult:
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if 200 <= r.status_code < 300:
                    data = r.json() if r.content else {}
                    data = self.normalize_provider_payload(provider, payload['params']['marketIds'][0], data)
                    return EnterpriseFeedResult(provider, True, data, 'http', status_code=r.status_code, fetched_at=_now())
                last_err = f'HTTP {r.status_code}: {r.text[:180]}'
            except Exception as exc:
                last_err = str(exc)
            time.sleep(0.5 * (attempt + 1))
        return EnterpriseFeedResult(provider, False, {}, 'http_error', last_err, fetched_at=_now())

    def _local(self, provider: str, fixture_id: str | int) -> EnterpriseFeedResult:
        root = self.provider_dir / provider
        for suffix in ('json', 'csv'):
            path = root / f'{fixture_id}.{suffix}'
            if not path.exists():
                continue
            try:
                if suffix == 'json':
                    raw = json.loads(path.read_text(encoding='utf-8'))
                else:
                    with path.open('r', encoding='utf-8', newline='') as fh:
                        raw = {'rows': list(csv.DictReader(fh))}
                payload = self.normalize_provider_payload(provider, fixture_id, raw)
                return EnterpriseFeedResult(provider, True, payload, 'local_snapshot', fetched_at=_now())
            except Exception as exc:
                return EnterpriseFeedResult(provider, False, {}, 'local_error', str(exc), fetched_at=_now())
        return EnterpriseFeedResult(provider, False, {}, 'no_local_snapshot', 'local snapshot not found', fetched_at=_now())

    def normalize_provider_payload(self, provider: str, fixture_id: str | int, raw: Dict[str, Any]) -> Dict[str, Any]:
        p = {'provider': provider, 'fixture_id': str(fixture_id), 'fetched_at': _now(), 'raw_keys': list(raw.keys())[:30]}
        # These normalizers accept already-normalized snapshots and common provider shapes.
        for k in ('home_team','away_team','league','start_time','home_xg','away_xg','home_shots','away_shots','home_shots_on_target','away_shots_on_target','home_possession','away_possession','home_dangerous_attacks','away_dangerous_attacks'):
            if k in raw: p[k] = raw[k]
        if provider == 'statsbomb':
            events = raw.get('events') or raw.get('rows') or raw.get('data') or []
            if isinstance(events, list):
                shots = [e for e in events if str(e.get('type', e.get('event_type',''))).lower() == 'shot']
                p['shot_events'] = shots[:500]
                p['home_shots'] = raw.get('home_shots', len([s for s in shots if str(s.get('team_side','')).lower() == 'home']))
                p['away_shots'] = raw.get('away_shots', len([s for s in shots if str(s.get('team_side','')).lower() == 'away']))
                p['home_xg'] = raw.get('home_xg', sum(_num(s.get('xg', s.get('shot_statsbomb_xg'))) for s in shots if str(s.get('team_side','')).lower() == 'home'))
                p['away_xg'] = raw.get('away_xg', sum(_num(s.get('xg', s.get('shot_statsbomb_xg'))) for s in shots if str(s.get('team_side','')).lower() == 'away'))
        elif provider == 'tracking':
            frames = raw.get('frames') or raw.get('rows') or []
            p['tracking_frames'] = len(frames) if isinstance(frames, list) else _num(raw.get('tracking_frames'), 0)
            p['avg_team_speed_home'] = raw.get('avg_team_speed_home')
            p['avg_team_speed_away'] = raw.get('avg_team_speed_away')
            p['defensive_line_height_home'] = raw.get('defensive_line_height_home')
            p['defensive_line_height_away'] = raw.get('defensive_line_height_away')
        elif provider == 'betfair_liquidity':
            p['matched_volume'] = raw.get('matched_volume', raw.get('totalMatched'))
            p['back_lay_spread'] = raw.get('back_lay_spread')
            p['liquidity_score'] = raw.get('liquidity_score')
            p['market_books'] = raw.get('result', raw.get('market_books', []))
        elif provider == 'premium_sharp':
            p['sharp_signal'] = raw.get('sharp_signal', raw.get('signal'))
            p['steam_move'] = raw.get('steam_move')
            p['syndicate_pressure'] = raw.get('syndicate_pressure')
        elif provider == 'opta':
            p['opta_quality'] = raw.get('quality_score', raw.get('opta_quality'))
            p['formations'] = raw.get('formations')
            p['lineups'] = raw.get('lineups')
        return p

    def merge(self, results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        ok = [r for r in results if r.get('ok')]
        merged: Dict[str, Any] = {'status': 'NO_ENTERPRISE_FEEDS' if not ok else 'ENTERPRISE_FEEDS_MERGED', 'updated_at': _now()}
        if not ok:
            return merged
        payloads = [r.get('payload', {}) for r in ok]
        # Use all numeric provider features. Average xG-like stats, max liquidity/sharp signals.
        keys = sorted(set().union(*(p.keys() for p in payloads)))
        for key in keys:
            vals = [p.get(key) for p in payloads if p.get(key) not in (None, '', [], {})]
            if not vals: continue
            numeric = []
            for v in vals:
                try: numeric.append(float(v))
                except Exception: pass
            if key in ('home_xg','away_xg','home_shots','away_shots','home_shots_on_target','away_shots_on_target') and numeric:
                merged[key] = round(sum(numeric)/len(numeric), 6)
            elif key in ('matched_volume','liquidity_score','sharp_signal','steam_move','syndicate_pressure') and numeric:
                merged[key] = max(numeric)
            else:
                merged[key] = vals[0]
        merged['enterprise_providers_used'] = [r['provider'] for r in ok]
        merged['enterprise_provider_count'] = len(ok)
        return merged

    def _cache(self, key: str, payload: Dict[str, Any]) -> None:
        safe = hashlib.sha1(str(key).encode('utf-8')).hexdigest()[:16]
        (self.cache_dir / f'{safe}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
