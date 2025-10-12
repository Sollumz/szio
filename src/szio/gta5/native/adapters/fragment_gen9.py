import pymateria.gta5.gen9 as pmg9

from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
)
from .drawable_gen9 import NativeFragDrawableG9
from .fragment import NativeFragment


class NativeFragmentG9(NativeFragment):
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN9
    ASSET_TYPE = AssetType.FRAGMENT

    def __init__(self, f: pmg9.Fragment):
        super().__init__(f)
        self._inner = f

    def _create_physics_lod_group(self) -> pmg9.FragmentPhysicsLodGroup:
        return pmg9.FragmentPhysicsLodGroup()

    def _create_physics_lod(self) -> pmg9.FragmentPhysicsLod:
        return pmg9.FragmentPhysicsLod()

    def _create_physics_child(self) -> pmg9.FragmentTypeChild:
        return pmg9.FragmentTypeChild()

    def _create_bg_pane_model_info(self) -> pmg9.BGPaneModelInfoBase:
        C = pmg9.FvfChannel
        F = pmg9.BufferFormat
        fvf = pmg9.Fvf()
        fvf.vertex_data_size = 44
        fvf.enable_channel(C.POSITION0, 0, 44, F.R32G32B32_FLOAT)
        fvf.enable_channel(C.NORMAL0, 12, 44, F.R32G32B32_FLOAT)
        fvf.enable_channel(C.COLOR0, 24, 44, F.R8G8B8A8_UNORM)
        fvf.enable_channel(C.TEXCOORD0, 28, 44, F.R32G32_FLOAT)
        fvf.enable_channel(C.TEXCOORD1, 36, 44, F.R32G32_FLOAT)
        p = pmg9.BGPaneModelInfoBase()
        p.fvf = fvf
        return p

    def _create_vehicle_window(self) -> pmg9.VehicleWindow:
        return pmg9.VehicleWindow()

    def _create_env_cloth(self) -> pmg9.FragmentEnvCloth:
        return pmg9.FragmentEnvCloth()

    @property
    def _cls_NativeFragDrawable(self) -> type:
        return NativeFragDrawableG9
