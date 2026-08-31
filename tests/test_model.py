import datetime as dt

import pytest
from kiddo_growth_chart.loader import DatasetError, parse
from kiddo_growth_chart.model import Kid, Measurement, Method, Unit


def test_inches_convert_to_canonical_cm_and_keep_the_source():
    m = Measurement.from_source(dt.date(2020, 5, 1), 48.5, "in", Method.CLINICAL)
    assert m.cm == pytest.approx(123.19, abs=0.01)
    # The source survives conversion: a bare number with no unit is unrecoverable.
    assert (m.source_value, m.source_unit) == (48.5, Unit.IN)


def test_age_is_measured_not_assumed():
    """A visit near a birthday is not the birthday, and the gap is real height."""
    kid = Kid(key="k", name="K", dob=dt.date(2016, 11, 27))
    assert kid.age_days_at(dt.date(2024, 11, 27)) == 2922
    # 3 weeks before the 8th birthday is still 7, and must not round to 8.
    assert kid.age_years_at(dt.date(2024, 11, 6)) < 8.0


def test_leap_day_birthday_does_not_crash_age_maths():
    kid = Kid(key="k", name="K", dob=dt.date(2016, 2, 29))
    assert kid.age_days_at(dt.date(2023, 3, 1)) == 2557


def test_measurement_before_birth_is_rejected_with_the_reason():
    with pytest.raises(DatasetError, match="before date of birth"):
        parse({"kids": [{"key": "a", "name": "A", "dob": "2016-01-01",
                         "measurements": [{"date": "2015-06-01", "cm": 70}]}]})


def test_two_heights_on_one_date_is_rejected():
    with pytest.raises(DatasetError, match="two measurements"):
        parse({"kids": [{"key": "a", "name": "A", "dob": "2016-01-01", "measurements": [
            {"date": "2020-01-01", "cm": 100}, {"date": "2020-01-01", "cm": 101}]}]})


def test_unknown_method_names_the_known_ones():
    with pytest.raises(DatasetError, match="known:"):
        parse({"kids": [{"key": "a", "name": "A", "dob": "2016-01-01",
                         "measurements": [{"date": "2020-01-01", "cm": 100,
                                           "method": "eyeballed"}]}]})


def test_mixed_methods_is_visible_on_the_kid():
    d = parse({"kids": [{"key": "a", "name": "A", "dob": "2016-01-01", "measurements": [
        {"date": "2020-01-01", "cm": 100, "method": "clinical"},
        {"date": "2021-01-01", "cm": 107, "method": "doorframe"}]}]})
    assert d.by_key("a").mixed_methods is True


@pytest.mark.parametrize("cm,expected", [
    (152.3, (5, 0.0)),      # 59.96in -- rounds to a whole foot, must not be 4'12.0"
    (152.4, (5, 0.0)),
    (123.19, (4, 0.5)),
    (91.44, (3, 0.0)),
])
def test_feet_inches_rounds_before_splitting(cm, expected):
    m = Measurement(dt.date(2020, 1, 1), cm)
    assert m.feet_inches() == expected
