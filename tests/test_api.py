import os

os.environ["ENVIRONMENT"] = "test"
os.environ["API_KEY"] = "test-key-with-at-least-thirty-two-characters"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
AUTH = {"x-api-key": os.environ["API_KEY"]}

def test_health():
    r = client.get('/api/v1/health')
    assert r.status_code == 200
    assert r.json()['ok'] is True

def test_predict_value_bet_shape():
    r = client.post('/api/v1/predict', headers=AUTH, json={
        'home_team': 'Alpha FC',
        'away_team': 'Beta FC',
        'market': 'Over 2.5',
        'odds': 2.1,
        'probability': 0.55
    })
    assert r.status_code == 200
    body = r.json()
    assert body['match_name'] == 'Alpha FC vs Beta FC'
    assert 'edge' in body
    assert body['recommendation'] in {'BET', 'PASS'}


def test_predict_requires_api_key():
    r = client.post('/api/v1/predict', json={
        'home_team': 'Alpha FC',
        'away_team': 'Beta FC',
        'market': 'Over 2.5',
        'odds': 2.1,
        'probability': 0.55
    })
    assert r.status_code == 401
