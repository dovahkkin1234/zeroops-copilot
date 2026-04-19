from auth import validate_token  # BUG 5: stale import, test crashes on collection


def test_valid():
    assert validate_token("valid_abc")
