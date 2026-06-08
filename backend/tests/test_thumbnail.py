from app.services.thumbnail import generate_thumbnail

def test_generate_thumbnail_returns_none_for_invalid_input():
    assert generate_thumbnail("not_valid_base64") is None

def test_generate_thumbnail_returns_none_for_empty_string():
    assert generate_thumbnail("") is None