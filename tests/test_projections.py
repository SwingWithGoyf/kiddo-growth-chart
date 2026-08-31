import datetime as dt

from kiddo_growth_chart.loader import parse
from kiddo_growth_chart.projections import Clock, frames, project

TWO_KIDS = {
    "kids": [
        {"key": "a", "name": "A", "dob": "2014-01-01", "measurements": [
            {"date": "2020-02-01", "cm": 118.0, "method": "clinical"},
            {"date": "2021-02-01", "cm": 124.0, "method": "clinical"}]},
        {"key": "b", "name": "B", "dob": "2018-01-01", "measurements": [
            {"date": "2024-03-01", "cm": 119.0, "method": "clinical"}]},
    ]
}


def test_the_two_views_are_the_same_points_under_a_different_x():
    d = parse(TWO_KIDS)
    by_date, by_age = project(d, Clock.DATE), project(d, Clock.AGE)
    assert [p.cm for s in by_date.series for p in s.points] == \
           [p.cm for s in by_age.series for p in s.points]
    # Six years apart on the calendar; nearly on top of each other by age.
    a0 = by_date.series[0].points[0].x
    b0 = by_date.series[1].points[0].x
    assert abs(a0 - b0) > 1400
    assert abs(by_age.series[0].points[0].x - by_age.series[1].points[0].x) < 90


def test_segments_only_join_measurements_and_flag_mixed_methods():
    d = parse({"kids": [{"key": "a", "name": "A", "dob": "2014-01-01", "measurements": [
        {"date": "2020-01-01", "cm": 118, "method": "clinical"},
        {"date": "2021-01-01", "cm": 124, "method": "doorframe"},
        {"date": "2022-01-01", "cm": 130, "method": "doorframe"}]}]})
    segs = project(d).series[0].segments
    assert len(segs) == 2                 # n points -> n-1 segments, never more
    assert [s.mixed_method for s in segs] == [True, False]


def test_empty_dataset_yields_a_drawable_projection_not_a_crash():
    d = parse({"kids": [{"key": "a", "name": "A", "dob": "2014-01-01"}]})
    p = project(d)
    assert p.empty and p.x_max > p.x_min


def test_frames_cut_at_real_dates_and_never_spring_everyone_together():
    """Visit dates differ, so a shared beat would assert simultaneous growth."""
    fs = frames(parse(TWO_KIDS), Clock.DATE)
    assert [f.grew for f in fs] == [("a",), ("a",), ("b",)]
    assert all(len(f.grew) == 1 for f in fs)


def test_a_kid_with_no_measurement_this_frame_holds_their_last_height():
    fs = frames(parse(TWO_KIDS), Clock.DATE)
    last = fs[-1]                          # b's frame; a was not measured then
    assert last.heights["a"] == 124.0      # held, not dropped and not drifted
    assert "a" not in last.grew


def test_a_kid_is_absent_until_their_first_measurement():
    fs = frames(parse(TWO_KIDS), Clock.DATE)
    assert "b" not in fs[0].heights        # nothing to draw, so draw nothing


def test_on_the_age_clock_the_childhoods_play_in_parallel():
    fs = frames(parse(TWO_KIDS), Clock.AGE)
    xs = [f.x for f in fs]
    assert xs == sorted(xs)
    assert xs[0] < 2600                    # both start near age 6, not 2020
