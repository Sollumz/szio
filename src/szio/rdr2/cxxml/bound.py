from abc import ABC as AbstractClass
from xml.etree import ElementTree as ET
from typing import ClassVar
from dataclasses import dataclass
from collections.abc import Sequence

from ...types import Vector
from ...xml import (
    AttributeProperty,
    ElementProperty,
    ElementTree,
    FlagsProperty,
    ListProperty,
    MatrixProperty,
    ValueProperty,
    VectorProperty,
    TextProperty,
)


class Bound(ElementTree, AbstractClass):
    tag_name = "Bounds"
    type_tag = None

    def __init__(self):
        super().__init__()
        self.type = AttributeProperty("type", self.type_tag)
        self.version = AttributeProperty("version", 2)

        self.box_min = VectorProperty("BoxMin")
        self.box_max = VectorProperty("BoxMax")
        self.box_center = VectorProperty("BoxCenter")
        self.sphere_center = VectorProperty("SphereCenter")
        self.sphere_radius = ValueProperty("SphereRadius", 0.0)
        self.margin = ValueProperty("Margin", 0)
        self.mass = ValueProperty("Mass", 0)
        self.inertia = VectorProperty("Inertia")
        self.unknown_11 = ValueProperty("Unknown_11h", 0)
        self.ref_count = ValueProperty("Unknown_3Ch", 1)
        self.material_name = TextProperty("MaterialName", "")
        self.material_procedural_id = ValueProperty("MaterialProcID", 0)
        self.material_room_id = ValueProperty("MaterialRoomID", 0)
        self.material_ped_density = ValueProperty("MaterialPedDens", 0)
        self.material_flags = FlagsProperty("MaterialFlags")
        self.material_unk = ValueProperty("MaterialUnk", 0)
        self.composite_transform = MatrixProperty("Transform")
        self.composite_type_flags = FlagsProperty("TypeFlags")
        self.composite_include_flags = FlagsProperty("IncludeFlags")


class BoundAny(Bound):
    @staticmethod
    def from_xml(element: ET.Element) -> "Bound":
        if "type" in element.attrib:
            bound_type = element.get("type")
            if bound_type == BoundComposite.type_tag:
                return BoundComposite.from_xml(element)
            elif bound_type == BoundBox.type_tag:
                return BoundBox.from_xml(element)
            elif bound_type == BoundSphere.type_tag:
                return BoundSphere.from_xml(element)
            elif bound_type == BoundCapsule.type_tag:
                return BoundCapsule.from_xml(element)
            elif bound_type == BoundCylinder.type_tag:
                return BoundCylinder.from_xml(element)
            elif bound_type == BoundDisc.type_tag:
                return BoundDisc.from_xml(element)
            elif bound_type == BoundTaperedCapsule.type_tag:
                return BoundTaperedCapsule.from_xml(element)
            # elif bound_type == "Cloth":
            #     return BoundPlane.from_xml(element)
            elif bound_type == BoundGeometry.type_tag:
                return BoundGeometry.from_xml(element)
            elif bound_type == BoundGeometryBVH.type_tag:
                return BoundGeometryBVH.from_xml(element)
            elif bound_type == "null":
                return None

        return None


class BoundComposite(Bound):
    type_tag = "Composite"

    def __init__(self):
        super().__init__()
        self.children = BoundList()


class BoundList(ListProperty):
    list_type = Bound
    tag_name = "Bounds"
    item_tag_name = "Item"
    allow_none_items = True

    @classmethod
    def from_xml(cls, element: ET.Element) -> "BoundList":
        new = cls(element.tag)
        for child in element.findall(new.item_tag_name):
            new.value.append(BoundAny.from_xml(child))
        return new

    def create_element_for_none_item(self) -> ET.Element:
        return ET.Element(self.item_tag_name, attrib={"type": "null"})


class BoundBox(Bound):
    type_tag = "Box"


class BoundSphere(Bound):
    type_tag = "Sphere"


class BoundCapsule(Bound):
    type_tag = "Capsule"


class BoundCylinder(Bound):
    type_tag = "Cylinder"


class BoundDisc(Bound):
    type_tag = "Disc"


class BoundTaperedCapsule(Bound):
    type_tag = "TaperedCapsule"

    def __init__(self):
        super().__init__()
        # TODO: extra fields from TaperedCapsule


class Material(ElementTree):
    tag_name = "Item"

    def __init__(self):
        super().__init__()
        self.name = TextProperty("Name", 0)
        self.procedural_id = ValueProperty("ProcID", 0)
        self.room_id = ValueProperty("RoomID", 0)
        self.ped_density = ValueProperty("PedDens", 0)
        self.flags = FlagsProperty("Flags")
        self.unk = ValueProperty("Unk", 0)


class MaterialsList(ListProperty):
    list_type = Material
    tag_name = "Materials"


class VerticesProperty(ElementProperty):
    value_types = list

    def __init__(self, tag_name: str = "Vertices", value=None):
        super().__init__(tag_name, value or [])

    @staticmethod
    def from_xml(element: ET.Element):
        new = VerticesProperty(element.tag, [])
        text = element.text.strip().split("\n")
        if len(text) > 0:
            for line in text:
                coords = line.strip().split(",")
                if not len(coords) == 3:
                    return VerticesProperty.read_value_error(element)

                new.value.append(Vector((float(coords[0]), float(coords[1]), float(coords[2]))))

        return new

    def to_xml(self):
        element = ET.Element(self.tag_name)
        text = ["\n"]

        if not self.value:
            return

        for vertex in self.value:
            if not isinstance(vertex, Vector):
                raise TypeError(f"VerticesProperty can only contain Vector objects, not '{type(self.value)}'!")
            for index, component in enumerate(vertex):
                text.append(str(component))
                if index < len(vertex) - 1:
                    text.append(", ")
            text.append("\n")

        element.text = "".join(text)

        return element


@dataclass(slots=True)
class Polygon:
    kind: ClassVar[str]
    material_index: int

    @property
    def vertices(self) -> Sequence[int]:
        raise NotImplementedError

    def to_line(self) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class PolyBox(Polygon):
    kind: ClassVar[str] = "Box"
    v1: int
    v2: int
    v3: int
    v4: int

    @property
    def vertices(self) -> Sequence[int]:
        return self.v1, self.v2, self.v3, self.v4

    @classmethod
    def from_parts(cls, material_index: int, parts: list[str]) -> "PolyBox":
        v1, v2, v3, v4 = (int(p) for p in parts)
        return cls(material_index, v1, v2, v3, v4)

    def to_line(self) -> str:
        return f"{self.kind} {self.material_index} {self.v1} {self.v2} {self.v3} {self.v4}"


@dataclass(slots=True)
class PolySphere(Polygon):
    kind: ClassVar[str] = "Sph"
    vertex: int
    radius: float

    @property
    def vertices(self) -> Sequence[int]:
        return (self.vertex,)

    @classmethod
    def from_parts(cls, material_index: int, parts: list[str]) -> "PolySphere":
        vertex, radius = parts
        return cls(material_index, int(vertex), float(radius))

    def to_line(self) -> str:
        return f"{self.kind} {self.material_index} {self.vertex} {self.radius}"


@dataclass(slots=True)
class PolyCapsule(Polygon):
    kind: ClassVar[str] = "Cap"
    v1: int
    v2: int
    radius: float

    @property
    def vertices(self) -> Sequence[int]:
        return self.v1, self.v2

    @classmethod
    def from_parts(cls, material_index: int, parts: list[str]) -> "PolyCapsule":
        v1, v2, radius = parts
        return cls(material_index, int(v1), int(v2), float(radius))

    def to_line(self) -> str:
        return f"{self.kind} {self.material_index} {self.v1} {self.v2} {self.radius}"


@dataclass(slots=True)
class PolyCylinder(Polygon):
    kind: ClassVar[str] = "Cyl"
    v1: int
    v2: int
    radius: float

    @property
    def vertices(self) -> Sequence[int]:
        return self.v1, self.v2

    @classmethod
    def from_parts(cls, material_index: int, parts: list[str]) -> "PolyCylinder":
        v1, v2, radius = parts
        return cls(material_index, int(v1), int(v2), float(radius))

    def to_line(self) -> str:
        return f"{self.kind} {self.material_index} {self.v1} {self.v2} {self.radius}"


@dataclass(slots=True)
class PolyTriangle(Polygon):
    kind: ClassVar[str] = "Tri"
    v1: int
    v2: int
    v3: int

    @property
    def vertices(self) -> Sequence[int]:
        return self.v1, self.v2, self.v3

    @classmethod
    def from_parts(cls, material_index: int, parts: list[str]) -> "PolyTriangle":
        v1, v2, v3 = (int(p) for p in parts)
        return cls(material_index, v1, v2, v3)

    def to_line(self) -> str:
        return f"{self.kind} {self.material_index} {self.v1} {self.v2} {self.v3}"


_POLYGON_TYPES: dict[str, type[Polygon]] = {
    cls.kind: cls for cls in (PolyBox, PolySphere, PolyCapsule, PolyCylinder, PolyTriangle)
}


class PolygonListProperty(ElementProperty):
    value_types = list

    def __init__(self, tag_name: str = "Polygons", value: list[Polygon] | None = None):
        super().__init__(tag_name, value if value is not None else [])

    @staticmethod
    def from_xml(element: ET.Element) -> "PolygonListProperty":
        new = PolygonListProperty(element.tag, [])
        if not element.text:
            return new

        for line in element.text.strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            kind, material_index, *rest = parts
            poly_cls = _POLYGON_TYPES.get(kind, None)
            if poly_cls is None:
                raise ValueError(f"Unknown polygon kind: {kind!r}")
            new.value.append(poly_cls.from_parts(int(material_index), rest))
        return new

    def to_xml(self) -> ET.Element | None:
        if not self.value:
            return None

        element = ET.Element(self.tag_name)
        element.text = "\n" + "\n".join(poly.to_line() for poly in self.value) + "\n"
        return element


class BoundGeometry(Bound):
    type_tag = "Geometry"

    def __init__(self):
        super().__init__()
        self.materials = MaterialsList()
        # TODO: "MaterialColours" tag
        self.vertices = VerticesProperty("Vertices")
        # TODO: "VertexColours" tag
        self.polygons = PolygonListProperty("Polygons")


class BoundGeometryBVH(BoundGeometry):
    type_tag = "GeometryBVH"

    def __init__(self):
        super().__init__()
        self.unknown_142 = ValueProperty("Unknown_142h", 0)
