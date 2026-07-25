from xml.etree import ElementTree as ET

import pytest

from szio.gta5.cwxml.ymap import HexColorProperty
from szio.xml.element import (
    ElementTree,
    Matrix33Property,
    MatrixProperty,
    TextProperty,
    ValueProperty,
    VectorProperty,
    get_str_type,
)


@pytest.mark.parametrize("string, expected", (
    ("true", True),
    ("True", True),
    ("TrUE", True),
    ("false", False),
    ("False", False),
    ("FALsE", False),
))
def test_xml_bool(string, expected):
    assert get_str_type(string) == expected


@pytest.mark.parametrize("bool_value, expected", (
    (True, "true"),
    (False, "false"),
))
def test_xml_bool_output(bool_value: bool, expected: str):
    class Data(ElementTree):
        tag_name = "Data"

        def __init__(self):
            self.v = ValueProperty("v")

    d = Data()
    d.v = bool_value
    xml = d.to_xml()
    assert xml.find("v").attrib["value"] == expected


@pytest.mark.parametrize("argb_hex, expected_rgba", (
    ("0x00FF0000", (1.0, 0.0, 0.0, 0.0)),
    ("0x0000FF00", (0.0, 1.0, 0.0, 0.0)),
    ("0x000000FF", (0.0, 0.0, 1.0, 0.0)),
    ("0xFF000000", (0.0, 0.0, 0.0, 1.0)),
    ("0x90909090", (0x90 / 0xFF,) * 4),
))
def test_argb_hex_to_rgba(argb_hex, expected_rgba):
    assert HexColorProperty.argb_hex_to_rgba(argb_hex) == expected_rgba


@pytest.mark.parametrize("rgba, expected_argb_hex", (
    ((1.0, 0.0, 0.0, 0.0), "0x00FF0000"),
    ((0.0, 1.0, 0.0, 0.0), "0x0000FF00"),
    ((0.0, 0.0, 1.0, 0.0), "0x000000FF"),
    ((0.0, 0.0, 0.0, 1.0), "0xFF000000"),
    ((0x90 / 0xFF,) * 4, "0x90909090"),
))
def test_rgba_to_argb_hex(rgba, expected_argb_hex):
    assert HexColorProperty.rgba_to_argb_hex(rgba) == expected_argb_hex


# ---------------------------------------------------------------------------
# Missing element handling tests
# ---------------------------------------------------------------------------

class Inner(ElementTree):
    tag_name = "Inner"

    def __init__(self):
        super().__init__()
        self.name = TextProperty("Name")
        self.count = ValueProperty("Count", 5)


class Outer(ElementTree):
    tag_name = "Outer"

    def __init__(self):
        super().__init__()
        self.label = TextProperty("Label")
        self.score = ValueProperty("Score", 42)
        self.inner = Inner()


class TestMissingElementTreeChildIsNone:
    """ElementTree children missing from XML should be set to None."""

    def test_missing_element_tree_child_is_none(self):
        xml = ET.fromstring("<Outer><Label>hello</Label><Score value='10' /></Outer>")
        obj = Outer.from_xml(xml)
        assert obj.inner is None

    def test_present_element_tree_child_is_parsed(self):
        xml = ET.fromstring(
            "<Outer><Label>hello</Label><Score value='10' />"
            "<Inner><Name>world</Name><Count value='3' /></Inner></Outer>"
        )
        obj = Outer.from_xml(xml)
        assert obj.inner is not None
        assert obj.inner.name == "world"
        assert obj.inner.count == 3


class TestMissingElementPropertyKeepsDefault:
    """ElementProperty children missing from XML should keep their default values."""

    def test_missing_value_property_keeps_default(self):
        xml = ET.fromstring("<Outer><Label>hello</Label></Outer>")
        obj = Outer.from_xml(xml)
        assert obj.score == 42

    def test_missing_text_property_keeps_default(self):
        xml = ET.fromstring("<Outer><Score value='10' /></Outer>")
        obj = Outer.from_xml(xml)
        assert obj.label == ""

    def test_nested_missing_property_keeps_default(self):
        xml = ET.fromstring("<Outer><Inner><Name>test</Name></Inner></Outer>")
        obj = Outer.from_xml(xml)
        assert obj.inner is not None
        assert obj.inner.count == 5


class TestToXmlOmitsNoneChildren:
    """to_xml() should skip None ElementTree children."""

    def test_none_child_omitted_from_xml(self):
        obj = Outer()
        obj.inner = None
        obj.label = "test"
        xml = obj.to_xml()
        assert xml.find("Inner") is None
        assert xml.find("Label") is not None

    def test_present_child_included_in_xml(self):
        obj = Outer()
        obj.label = "test"
        xml = obj.to_xml()
        assert xml.find("Inner") is not None


class TestRoundtripWithNoneChildren:
    """Parsing XML with missing children and re-serializing should be consistent."""

    def test_roundtrip_missing_child(self):
        xml = ET.fromstring("<Outer><Label>hello</Label><Score value='10' /></Outer>")
        obj = Outer.from_xml(xml)
        assert obj.inner is None

        # Serialize back
        xml_out = obj.to_xml()
        assert xml_out.find("Inner") is None
        assert xml_out.find("Label").text == "hello"
        assert xml_out.find("Score").attrib["value"] == "10"

        # Parse again
        obj2 = Outer.from_xml(xml_out)
        assert obj2.inner is None
        assert obj2.label == "hello"
        assert obj2.score == 10

    def test_roundtrip_with_child(self):
        xml = ET.fromstring(
            "<Outer><Label>hello</Label><Score value='10' />"
            "<Inner><Name>world</Name><Count value='3' /></Inner></Outer>"
        )
        obj = Outer.from_xml(xml)
        xml_out = obj.to_xml()
        obj2 = Outer.from_xml(xml_out)
        assert obj2.inner is not None
        assert obj2.inner.name == "world"
        assert obj2.inner.count == 3


IDENTITY_4X4 = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


@pytest.mark.parametrize("text", (
    # newline rows with space indentation and space-separated values (CodeWalker style)
    "\n   1 0 0 0\n   0 1 0 0\n   0 0 1 0\n   0 0 0 1\n",
    # tab-separated values with tab indentation (#1217)
    "\n\t1\t0\t0\t0\n\t0\t1\t0\t0\n\t0\t0\t1\t0\n\t0\t0\t0\t1\n",
    # mixed: spaces and runs of tabs inside a row (#1217)
    "\n   1 0 0 0\n   0\t\t\t\t\t1 0 0\n   0 0 1 0\n   0 0 0 1\n",
), ids=("spaces", "tabs", "mixed_tabs"))
def test_matrix_property_whitespace_tolerant(text):
    elem = ET.Element("CompositeTransform")
    elem.text = text
    prop = MatrixProperty.from_xml(elem)
    for r in range(4):
        for c in range(4):
            assert float(prop.value[r][c]) == IDENTITY_4X4[r][c]


@pytest.mark.parametrize("text", (
    # CodeWalker writes fragment bound matrices as 4 rows x 3 columns;
    # the 4th column of each row must keep its identity default
    "\n   1 0 0\n   0 1 0\n   0 0 1\n   5 6 7\n",
    "\n\t1\t0\t0\n\t0\t1\t0\n\t0\t0\t1\n\t5\t6\t7\n",
), ids=("spaces", "tabs"))
def test_matrix_property_4x3_rows_keep_last_column_default(text):
    elem = ET.Element("Matrix")
    elem.text = text
    prop = MatrixProperty.from_xml(elem)
    expected = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (5, 6, 7, 1))
    for r in range(4):
        for c in range(4):
            assert float(prop.value[r][c]) == expected[r][c]


def test_matrix_property_partial_rows_keep_default():
    # 12 values only fill the first 3 rows; the last identity row is untouched
    elem = ET.Element("Transform")
    elem.text = "\n   2 0 0 0\n   0 2 0 0\n   0 0 2 0\n"
    prop = MatrixProperty.from_xml(elem)
    expected = ((2, 0, 0, 0), (0, 2, 0, 0), (0, 0, 2, 0), (0, 0, 0, 1))
    for r in range(4):
        for c in range(4):
            assert float(prop.value[r][c]) == expected[r][c]


def test_matrix_property_roundtrip():
    elem = ET.Element("Transform")
    elem.text = "\n   1 2 3 4\n   5 6 7 8\n   9 10 11 12\n   13 14 15 16\n"
    prop = MatrixProperty.from_xml(elem)
    prop.tag_name = "Transform"
    out = prop.to_xml()
    prop2 = MatrixProperty.from_xml(out)
    for r in range(4):
        for c in range(4):
            assert float(prop2.value[r][c]) == float(prop.value[r][c])


@pytest.mark.parametrize("text", (
    "\n   1 2 3\n   4 5 6\n   7 8 9\n",
    "\n\t1\t2\t3\n\t4\t5\t6\n\t7\t8\t9\n",
), ids=("spaces", "tabs"))
def test_matrix33_property_whitespace_tolerant(text):
    elem = ET.Element("Rotation")
    elem.text = text
    prop = Matrix33Property.from_xml(elem)
    assert isinstance(prop, Matrix33Property)
    expected = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    for r in range(3):
        for c in range(3):
            assert float(prop.value[r][c]) == expected[r][c]
