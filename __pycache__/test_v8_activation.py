from rocket_v8_enterprise_orchestrator import RocketV8EnterpriseOrchestrator

if __name__ == "__main__":
    v8 = RocketV8EnterpriseOrchestrator()
    result = v8.analyze_fixture("test_fixture", 1.6, 1.1, "OVER_2_5", 1.95)
    assert result["status"] == "V8_FULL_ENTERPRISE_STACK_ACTIVE"
    assert 0.01 <= result["probability"] <= 0.99
    assert result["bookmaker_used_only_for_comparison"] is True
    batch = v8.distributed_analyze([
        {"fixture_id": "test_fixture_1", "home_xg": 1.4, "away_xg": 1.2, "market": "BTTS_YES", "bookmaker_odds": 1.9},
        {"fixture_id": "test_fixture_2", "home_xg": 1.8, "away_xg": 0.8, "market": "HOME_WIN", "bookmaker_odds": 2.1},
    ])
    assert batch["status"] == "DISTRIBUTED_INFERENCE_COMPLETE"
    print("V8_ENTERPRISE_ACTIVATION_OK")
