import os
import tempfile
from pathlib import Path

import pytest

from szio.types import DataSource


def test_data_source_init_with_string_path():
    test_file = "test_file.txt"
    ds = DataSource.create(test_file)
    assert isinstance(ds.filepath, Path)  # should be normalized to Path
    assert str(ds.filepath) == test_file
    assert ds.name == "test_file.txt"


def test_data_source_init_with_pathlike():
    test_path = Path("test_file.txt")
    ds = DataSource.create(test_path)
    assert isinstance(ds.filepath, Path)
    assert ds.filepath == test_path
    assert ds.name == "test_file.txt"


def test_data_source_init_with_absolute_path():
    test_path = Path("some/nested/directory/test_file.txt").absolute()
    ds = DataSource.create(test_path)
    assert ds.filepath == test_path
    assert ds.name == "test_file.txt"  # should only contain basename


def test_data_source_file_open_and_read(tmp_path):
    test_data = b"Hello, World! This is test data."

    temp_file = tmp_path / "test_file.txt"
    temp_file.write_bytes(test_data)

    ds = DataSource.create(temp_file)
    with ds.open() as f:
        content = f.read()
        assert content == test_data


def test_data_source_file_not_found():
    ds = DataSource.create("nonexistent_file.txt")
    with pytest.raises(FileNotFoundError):
        ds.open()


def test_data_source_init_with_bytes():
    test_data = b"Test bytes data"
    ds = DataSource.create(test_data, "test_name")
    assert ds.name == "test_name"
    assert ds.data == test_data


def test_data_source_bytes_open_and_read():
    test_data = b"Hello, World!"
    ds = DataSource.create(test_data, "test_bytes")
    with ds.open() as d:
        content = d.read()
        assert content == test_data


def test_data_source_create_with_unsupported_type():
    with pytest.raises(TypeError, match="Unsupported source type"):
        DataSource.create(123)
