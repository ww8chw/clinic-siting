from clinic_siting.scoring.normalize import minmax_score


def test_value_at_low_bound_scores_zero():
    assert minmax_score(0, lo=0, hi=100) == 0.0


def test_value_at_high_bound_scores_hundred():
    assert minmax_score(100, lo=0, hi=100) == 100.0


def test_value_below_low_is_clamped_to_zero():
    assert minmax_score(-50, lo=0, hi=100) == 0.0


def test_value_above_high_is_clamped_to_hundred():
    assert minmax_score(200, lo=0, hi=100) == 100.0


def test_midpoint():
    assert minmax_score(50, lo=0, hi=100) == 50.0


def test_invert_flips_score():
    # 競爭越多分數越低：invert=True
    assert minmax_score(100, lo=0, hi=100, invert=True) == 0.0
    assert minmax_score(0, lo=0, hi=100, invert=True) == 100.0


def test_equal_bounds_returns_fifty():
    assert minmax_score(5, lo=5, hi=5) == 50.0
