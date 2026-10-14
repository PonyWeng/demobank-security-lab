from pathlib import Path

def pytest_sessionstart(session):
    Path('test-results').mkdir(exist_ok=True)
