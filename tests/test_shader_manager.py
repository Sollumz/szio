import pytest
from szio.gta5 import ShaderManager


@pytest.mark.parametrize("filename, expected", (
    ("default.sps", "default.sps"),
    ("hash_18ad1594", "default.sps"),
    ("hash_18AD1594", "default.sps"),
    ("terrain_cb_4lyr.sps", "terrain_cb_4lyr.sps"),
    ("hash_C8D15397", "terrain_cb_4lyr.sps"),
))
def test_find_shader(filename: str, expected: str):
    shader = ShaderManager.find_shader(filename)
    assert shader is not None
    assert shader.filename == expected


@pytest.mark.parametrize("filename", (
    "unknown.sps",
    "hash_1234ABCD",
    "",
))
def test_find_shader_unknown_returns_none(filename: str):
    shader = ShaderManager.find_shader(filename)
    assert shader is None
