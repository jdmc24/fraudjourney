from app.evaluations import run_evaluations


def test_controlled_evaluations_pass_and_include_overrides():
    results = run_evaluations()

    assert len(results) >= 4
    assert all(result.passed for result in results)
    assert any(result.guardrail_fired for result in results)
    assert any(result.pii_redacted for result in results)
