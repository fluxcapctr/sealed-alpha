from tools.run_daily import check_price_health


def prices(**kw):
    base = {"expected": 1000, "coverage": 0.97, "unpriced_count": 30, "queries_failed": 0, "success": 970}
    base.update(kw)
    return base


def test_healthy_run_has_no_problems(config):
    assert check_price_health(config, prices(), sets_total=100) == []


def test_low_coverage_is_a_problem(config):
    problems = check_price_health(config, prices(coverage=0.5, unpriced_count=500, success=500), sets_total=100)
    assert any("coverage" in p for p in problems)


def test_many_failed_searches_is_a_problem(config):
    problems = check_price_health(config, prices(queries_failed=40), sets_total=100)
    assert any("40 of 100" in p for p in problems)


def test_a_blocked_run_that_wrote_nothing_is_a_problem(config):
    problems = check_price_health(config, prices(coverage=0.0, unpriced_count=1000, success=0, queries_failed=100), sets_total=100)
    assert any("no price snapshots" in p for p in problems)
