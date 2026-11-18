from xml.etree import ElementTree as ET

from numpy import float32

from ...xml import (
    AttributeProperty,
    ElementProperty,
    ElementTree,
    ListProperty,
    PolymorphicListProperty,
    QuaternionProperty,
    StructListProperty,
    TextProperty,
    ValueListPropertyRequired,
    ValueProperty,
    VectorProperty,
)
from .ymap import EntityList, ExtensionsList


class YTYP:
    file_extension = ".ytyp.xml"

    @staticmethod
    def from_xml_file(filepath):
        return CMapTypes.from_xml_file(filepath)

    @staticmethod
    def write_xml(cmap_types, filepath):
        return cmap_types.write_xml(filepath)


class BaseArchetype(ElementTree):
    tag_name = "Item"

    def __init__(self):
        super().__init__()
        self.type = AttributeProperty("type", "CBaseArchetypeDef")
        self.lod_dist = ValueProperty("lodDist")
        self.flags = ValueProperty("flags")
        self.special_attribute = ValueProperty("specialAttribute")
        self.bb_min = VectorProperty("bbMin")
        self.bb_max = VectorProperty("bbMax")
        self.bs_center = VectorProperty("bsCentre")
        self.bs_radius = ValueProperty("bsRadius")
        self.hd_texture_dist = ValueProperty("hdTextureDist")
        self.name = TextProperty("name")
        self.texture_dictionary = TextProperty("textureDictionary")
        self.clip_dictionary = TextProperty("clipDictionary")
        self.drawable_dictionary = TextProperty("drawableDictionary")
        self.physics_dictionary = TextProperty("physicsDictionary")
        self.asset_type = TextProperty("assetType")
        self.asset_name = TextProperty("assetName")
        self.extensions = ExtensionsList()


class TimeArchetype(BaseArchetype):
    def __init__(self):
        super().__init__()
        self.type = AttributeProperty("type", "CTimeArchetypeDef")
        self.time_flags = ValueProperty("timeFlags")


class Corner(ElementProperty):
    value_types = tuple
    tag_name = "Item"

    def __init__(self, tag_name=None, value=None):
        super().__init__("Item", value or tuple())

    @staticmethod
    def from_xml(element):
        value = element.text.split(",")
        value = [float(val) for val in value]
        if len(value) > 3:
            value = value[:3]
        return Corner(value=tuple(value))

    def to_xml(self):
        if not self.value or len(self.value) < 1:
            return None

        elem = ET.Element(self.tag_name)
        elem.text = ",".join([str(float32(val)) for val in self.value])
        return elem


class CornersList(ListProperty):
    list_type = Corner
    tag_name = "corners"


class AttachedObjectsBuffer(ValueListPropertyRequired):
    tag_name = "attachedObjects"
    item_type = int


class Portal(ElementTree):
    tag_name = "Item"

    def __init__(self):
        super().__init__()
        self.room_from = ValueProperty("roomFrom")
        self.room_to = ValueProperty("roomTo")
        self.flags = ValueProperty("flags")
        self.mirror_priority = ValueProperty("mirrorPriority")
        self.opacity = ValueProperty("opacity")
        self.audio_occlusion = ValueProperty("audioOcclusion")
        self.corners = CornersList()
        self.attached_objects = AttachedObjectsBuffer()


class PortalsList(StructListProperty):
    tag_name = "portals"
    list_type = Portal
    item_type_name = "CMloPortalDef"


class Room(ElementTree):
    tag_name = "Item"

    def __init__(self):
        super().__init__()
        self.name = TextProperty("name")
        self.bb_min = VectorProperty("bbMin")
        self.bb_max = VectorProperty("bbMax")
        self.blend = ValueProperty("blend", 1)
        self.timecycle_name = TextProperty("timecycleName")
        self.secondary_timecycle_name = TextProperty("secondaryTimecycleName")
        self.flags = ValueProperty("flags")
        self.portal_count = ValueProperty("portalCount")
        self.floor_id = ValueProperty("floorId")
        self.exterior_visibility_depth = ValueProperty("exteriorVisibiltyDepth", -1)
        self.attached_objects = AttachedObjectsBuffer()


class RoomsList(StructListProperty):
    tag_name = "rooms"
    list_type = Room
    item_type_name = "CMloRoomDef"


class LocationsBuffer(ValueListPropertyRequired):
    tag_name = "locations"
    item_type = int


class EntitySet(ElementTree):
    tag_name = "Item"

    def __init__(self):
        super().__init__()
        self.name = TextProperty("name")
        self.locations = LocationsBuffer()
        self.entities = EntityList()


class EntitySetsList(StructListProperty):
    tag_name = "entitySets"
    list_type = EntitySet
    item_type_name = "CMloEntitySet"


class TimeCycleModifier(ElementTree):
    tag_name = "Item"

    def __init__(self):
        self.name = TextProperty("name")
        self.sphere = QuaternionProperty("sphere")
        self.percentage = ValueProperty("percentage")
        self.range = ValueProperty("range")
        self.start_hour = ValueProperty("startHour")
        self.end_hour = ValueProperty("endHour")


class TimeCycleModifiersList(StructListProperty):
    tag_name = "timeCycleModifiers"
    list_type = TimeCycleModifier
    item_type_name = "CMloTimeCycleModifier"


class MloArchetype(BaseArchetype):
    def __init__(self):
        super().__init__()
        self.type = AttributeProperty("type", "CMloArchetypeDef")
        self.mlo_flags = ValueProperty("mloFlags")
        self.entities = EntityList()
        self.rooms = RoomsList()
        self.portals = PortalsList()
        self.entity_sets = EntitySetsList()
        self.timecycle_modifiers = TimeCycleModifiersList()


class ArchetypesList(PolymorphicListProperty):
    list_type = BaseArchetype
    tag_name = "archetypes"
    item_classes = {
        "CBaseArchetypeDef": BaseArchetype,
        "CMloArchetypeDef": MloArchetype,
        "CTimeArchetypeDef": TimeArchetype,
    }


class CompositeEntityType(ElementTree):
    tag_name = "Item"

    def __init__(self):
        super().__init__()
        self.name = TextProperty("Name")
        self.lod_dist = ValueProperty("lodDist")
        self.flags = ValueProperty("flags")
        self.special_attribute = ValueProperty("specialAttribute")
        self.bb_min = VectorProperty("bbMin")
        self.bb_max = VectorProperty("bbMax")
        self.bs_center = VectorProperty("bsCentre")
        self.bs_radius = ValueProperty("bsRadius")
        self.start_model = TextProperty("StartModel")
        self.end_model = TextProperty("EndModel")
        self.start_imap_file = TextProperty("StartImapFile")
        self.end_imap_file = TextProperty("EndImapFile")
        self.ptfx_assetname = TextProperty("PtFxAssetName")
        # TODO
        # self.animations = AnimationsList()


class CompositeEntityTypeList(StructListProperty):
    list_type = CompositeEntityType
    tag_name = "compositeEntityTypes"
    item_type_name = "CCompositeEntityType"


class CMapTypes(ElementTree):
    tag_name = "CMapTypes"

    def __init__(self):
        super().__init__()
        self.extensions = ExtensionsList()
        self.archetypes = ArchetypesList()
        self.name = TextProperty("name")
        # TODO: Investigate: Not used in any ytyp file in the game?
        # self.dependencies = DependenciesListProperty()
        self.composite_entity_type = CompositeEntityTypeList()
