import pytest

from szio.jenkhash import hash_string, hash_string_literal, name_to_hash_literal


@pytest.mark.parametrize(
    "text, expected",
    (
        ("CMapTypes", 0xD98BB561),
        ("CMloArchetypeDef", 0x10506455),
        ("txdRelationships", 0x069ADF93),
        ("zqNiUDA_0x07D164A8", 0x07D164A8),
    ),
)
def test_hash_string_literal_matches_the_engine(text: str, expected: int):
    assert hash_string_literal(text) == expected


def test_hash_string_literal_does_not_fold_case():
    assert hash_string_literal("CMapTypes") != hash_string_literal("cmaptypes")


def test_hash_string_folds_case():
    assert hash_string("CMapTypes") == hash_string("cmaptypes")


@pytest.mark.parametrize(
    "name, expected",
    (
        ("timeCycleVolumes", 0x8471928B),
        ("hash_8471928B", 0x8471928B),
        ("hash_8471928b", 0x8471928B),
        ("awOyxCA_0x8471928B", 0x8471928B),
        ("gdghaain_0x8471928b", 0x8471928B),
        ("timecyclevolumes", 0x40F3BEAC),
        ("hash_nothex", hash_string_literal("hash_nothex")),
    ),
)
def test_name_to_hash_literal(name: str, expected: int):
    assert name_to_hash_literal(name) == expected
