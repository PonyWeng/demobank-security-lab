from lab_time import taipei_time

def test_utc_formats_and_date_rollover():
    expected='2026-10-15 01:30:00 UTC+08:00'
    assert taipei_time('2026-10-14T17:30:00.123Z') == expected
    assert taipei_time('2026-10-14 17:30:00') == expected
    assert taipei_time('2026-10-15T01:30:00+08:00') == expected
    assert taipei_time(None)==''
    assert taipei_time('invalid')=='invalid'
