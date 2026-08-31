import math

import pytest
from kiddo_growth_chart.growth import LMSRow, cm_to_percentile, percentile_to_cm


def test_median_is_m_regardless_of_skew():
    for l in (-1.5, 0.0, 0.7):
        row = LMSRow("f", 3000, l, 128.0, 0.045)
        assert percentile_to_cm(row, 50) == pytest.approx(128.0, abs=1e-6)


def test_percentile_and_height_are_inverses():
    row = LMSRow("m", 3650, -1.2, 133.4, 0.043)
    for p in (3, 25, 50, 85, 97):
        assert cm_to_percentile(row, percentile_to_cm(row, p)) == pytest.approx(p, abs=1e-4)


def test_l_zero_uses_the_lognormal_branch():
    row = LMSRow("f", 1000, 0.0, 100.0, 0.05)
    assert percentile_to_cm(row, 84.134) == pytest.approx(100.0 * math.exp(0.05), abs=0.01)


def test_percentile_must_be_strictly_inside_the_range():
    row = LMSRow("f", 1000, -1.0, 100.0, 0.05)
    for bad in (0, 100, -5, 140):
        with pytest.raises(ValueError):
            percentile_to_cm(row, bad)


def test_no_reference_table_ships_so_bands_stay_off():
    """Inventing plausible reference values would be worse than shipping none."""
    from kiddo_growth_chart.growth import available_tables
    assert available_tables() == []
