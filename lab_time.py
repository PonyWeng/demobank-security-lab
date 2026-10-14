"""SQLite stores UTC; render classroom timestamps consistently on every host."""
from datetime import datetime, timezone, timedelta

TAIPEI = timezone(timedelta(hours=8), 'Asia/Taipei')

def taipei_time(value):
    if not value:
        return ''
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return str(value)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(TAIPEI).strftime('%Y-%m-%d %H:%M:%S') + ' UTC+08:00'
