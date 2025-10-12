"""Module for managing CodeWalker XML files in an object oriented way."""

# flake8: noqa: F401
from .bound import (
    YBN,
    Bound,
    BoundBox,
    BoundCapsule,
    BoundChild,
    BoundComposite,
    BoundCylinder,
    BoundDisc,
    BoundFile,
    BoundGeometry,
    BoundGeometryBVH,
    BoundList,
    BoundPlane,
    BoundSphere,
    PolyBox,
    PolyCapsule,
    PolyCylinder,
    Polygon,
    Polygons,
    PolySphere,
    PolyTriangle,
)
from .bound import (
    Material as ColMaterial,
)
from .bound import (
    MaterialsList as ColMaterialsList,
)
from .clipdictionary import (
    YCD,
    Animation,
    ChannelsList,
    Clip,
    ClipAnimationsList,
    ClipDictionary,
    ClipsList,
    ClipType,
)
from .clipdictionary import (
    AttributesList as ClipAttributesList,
)
from .clipdictionary import (
    Property as ClipProperty,
)
from .cloth import (
    YLD,
    CharacterCloth,
    CharacterClothBinding,
    CharacterClothBindingList,
    CharacterClothController,
    ClothBridgeSimGfx,
    ClothController,
    ClothDictionary,
    ClothInstanceTuning,
    EnvironmentCloth,
    EnvironmentClothList,
    MorphController,
    MorphMapData,
    VerletCloth,
    VerletClothEdge,
    VerletClothEdgeList,
    VerletClothVerticesProperty,
)
from .drawable import (
    YDD,
    YDR,
    ArrayShaderParameter,
    Bone,
    BoneIDProperty,
    BoneLimit,
    BonesList,
    Drawable,
    DrawableDictionary,
    DrawableMatrices,
    DrawableModel,
    DrawableModelList,
    GeometriesList,
    Geometry,
    IndexBuffer,
    Joints,
    Light,
    Lights,
    ParametersList,
    RotationLimit,
    RotationLimitsList,
    Shader,
    ShaderGroup,
    ShaderParameter,
    ShadersList,
    Skeleton,
    Texture,
    TextureDictionaryList,
    TextureShaderParameter,
    TranslationLimitsList,
    VectorShaderParameter,
    VertexBuffer,
    VertexLayoutList,
)
from .fragment import (
    YFT,
    Archetype,
    BoneTransform,
    BoneTransformsList,
    DrawablesList,
    Fragment,
    GlassWindow,
    GlassWindows,
    Physics,
    PhysicsChild,
    PhysicsGroup,
    PhysicsLOD,
    ShatterMapProperty,
    Transform,
    TransformsList,
    VehicleGlassWindows,
    Window,
)
from .fragment import (
    ChildrenList as PhysicsChildrenList,
)
from .fragment import (
    GroupsList as PhysicsGroupsList,
)
from .navmesh import (
    YNV,
    Navmesh,
    NavPoint,
    NavPointList,
    NavPolygon,
    NavPolygonList,
    NavPolygonVertices,
    NavPortal,
    NavPortalList,
)
from .provider import (
    CWProviderG8,
    CWProviderG9,
)
from .ymap import (
    YMAP,
    Block,
    BoxOccluder,
    BoxOccludersList,
    CarGenerator,
    CarGeneratorsList,
    CMapData,
    ContainerLodsList,
    Entity,
    EntityList,
    Extension,
    ExtensionAudioCollision,
    ExtensionAudioEmitter,
    ExtensionBuoyancy,
    ExtensionDoor,
    ExtensionExplosionEffect,
    ExtensionExpression,
    ExtensionLadder,
    ExtensionLightEffect,
    ExtensionLightShaft,
    ExtensionParticleEffect,
    ExtensionProcObject,
    ExtensionsList,
    ExtensionSpawnPoint,
    ExtensionSpawnPointOverride,
    ExtensionWindDisturbance,
    LightInstance,
    LightInstancesList,
    OccludeModel,
    OccludeModelsList,
    PhysicsDictionariesList,
    TimeCycleModifier,
    TimeCycleModifiersList,
)
from .ytyp import (
    YTYP,
    ArchetypesList,
    AttachedObjectsBuffer,
    BaseArchetype,
    CMapTypes,
    CompositeEntityType,
    CompositeEntityTypeList,
    EntitySet,
    EntitySetsList,
    LocationsBuffer,
    MloArchetype,
    Portal,
    PortalsList,
    Room,
    RoomsList,
    TimeArchetype,
)
from .ytyp import (
    Corner as PortalCorner,
)
from .ytyp import (
    CornersList as PortalCornersList,
)
from .ytyp import (
    TimeCycleModifier as MloTimeCycleModifier,
)
from .ytyp import (
    TimeCycleModifiersList as MloTimeCycleModifiersList,
)

IS_BACKEND_AVAILABLE = True
