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


@pytest.mark.parametrize("base_name, render_bucket, expected", (
    ("vehicle_mesh", 0, "vehicle_mesh.sps"),
    # Multiple presets share these base name+render bucket pairs; the first one listed in Shaders.xml must win
    ("vehicle_vehglass", 1, "vehicle_vehglass.sps"),  # not vehicle_lights.sps
    ("default", 0, "default.sps"),  # not gta_default.sps or default_noedge.sps
    ("spec", 0, "spec.sps"),  # not gta_spec.sps
    ("normal", 3, "normal_cutout.sps"),  # not normal_screendooralpha.sps
    # Lookup by base name hash
    ("hash_7c98d207", 1, "vehicle_vehglass.sps"),
    ("hash_E4DF46D5", 0, "default.sps"),
))
def test_find_shader_preset_name(base_name: str, render_bucket: int, expected: str):
    assert ShaderManager.find_shader_preset_name(base_name, render_bucket) == expected


@pytest.mark.parametrize("base_name, render_bucket", (
    ("unknown", 0),
    ("hash_1234ABCD", 0),
    ("vehicle_vehglass", 0),  # known base name but no preset in this render bucket
    ("", 0),
))
def test_find_shader_preset_name_unknown_returns_none(base_name: str, render_bucket: int):
    assert ShaderManager.find_shader_preset_name(base_name, render_bucket) is None
