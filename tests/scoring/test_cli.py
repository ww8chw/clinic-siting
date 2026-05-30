from clinic_siting.cli import run_demo


def test_run_demo_returns_all_specialties_sorted():
    ranking = run_demo()
    # 回傳 list[(specialty, score)]，依分數由高到低
    names = [name for name, _ in ranking]
    scores = [score for _, score in ranking]
    assert len(ranking) == 5
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 100.0 for s in scores)
