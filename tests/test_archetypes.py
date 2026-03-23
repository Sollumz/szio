import xml.etree.ElementTree as ET

from szio.gta5 import (
    Archetype,
    ArchetypeAssetType,
    ArchetypeType,
    AssetFormat,
    AssetTarget,
    AssetVersion,
    ExtensionAudioEmitter,
    create_asset_map_types,
    save_asset,
    try_load_asset,
)
from szio.types import Quaternion, Vector


def test_archetypes_extension_audio_emitter_effect_hash_is_saved_correctly(tmp_path):
    typ = create_asset_map_types((AssetTarget(AssetFormat.CWXML, AssetVersion.GEN8),))

    expected_effect_hash_str = "test_effect"
    expected_effect_hash = 0x2CA1BFAB

    audio_emitter = ExtensionAudioEmitter(
        name="test_audio_emitter",
        offset_position=Vector(),
        offset_rotation=Quaternion(),
        effect_hash=expected_effect_hash_str,
    )
    arch = Archetype(
        name="test_archetype",
        type=ArchetypeType.BASE,
        flags=0,
        lod_dist=0.0,
        special_attribute=0,
        hd_texture_dist=0.0,
        texture_dictionary="",
        clip_dictionary="",
        drawable_dictionary="",
        physics_dictionary="",
        bb_min=Vector(),
        bb_max=Vector(),
        bs_center=Vector(),
        bs_radius=0.0,
        asset_name="test_archetype",
        asset_type=ArchetypeAssetType.DRAWABLE,
        extensions=[audio_emitter],
    )
    typ.archetypes = [arch]
    save_asset(typ, tmp_path, "test", targets=(AssetTarget(AssetFormat.CWXML, AssetVersion.GEN8),))

    root = ET.parse(tmp_path / "test.ytyp.xml")
    elem = root.find("./archetypes/Item/extensions/Item/effectHash")
    assert elem is not None
    assert elem.get("value") == str(expected_effect_hash)

    typ_loaded = try_load_asset(tmp_path / "test.ytyp.xml")
    effect_hash_loaded = typ_loaded.archetypes[0].extensions[0].effect_hash
    assert effect_hash_loaded == f"hash_{expected_effect_hash:08X}"
