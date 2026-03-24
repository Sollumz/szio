from xml.etree import ElementTree as ET

import pytest

from szio.xml.element import get_str_type, ElementTree, TextProperty, ValueProperty, VectorProperty
from szio.gta5.cwxml.ymap import HexColorProperty


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
