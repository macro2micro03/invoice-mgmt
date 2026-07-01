from app import config, photos


def test_save_photo_writes_file_and_returns_relative_path():
    rel_path = photos.save_photo(b"fake-bytes", "invoice.jpg")
    full_path = config.STORAGE_DIR / rel_path
    assert full_path.exists()
    assert full_path.read_bytes() == b"fake-bytes"
    assert rel_path.startswith("photos")


def test_save_photo_preserves_extension():
    rel_path = photos.save_photo(b"data", "scan.png")
    assert rel_path.endswith(".png")


def test_save_photo_defaults_to_jpg_when_no_extension():
    rel_path = photos.save_photo(b"data", "noext")
    assert rel_path.endswith(".jpg")
