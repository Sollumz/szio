import io
import os
from pathlib import Path
from typing import IO, TYPE_CHECKING, Sequence, TypeAlias

import numpy as np

__all__ = [
    "Vector",
    "Quaternion",
    "Matrix",
    "use_math_types",
    "DataSource",
]


class VectorImpl(np.ndarray):
    def __new__(cls, xyz: Sequence[float] | np.ndarray = (0.0, 0.0, 0.0)) -> "VectorImpl":
        if len(s := np.shape(xyz)) != 1 or not (2 <= s[0] <= 4):
            raise ValueError("Vector expects 2, 3 or 4 values")

        return np.array(xyz).view(cls)

    def __bool__(self) -> bool:
        """Always evaluate a Vector as True, overriding NumPy's default
        behavior that disallows array-to-bool conversion.
        """
        return True

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    @property
    def z(self) -> float:
        return self[2]

    @property
    def w(self) -> float:
        return self[3]


class QuaternionImpl(np.ndarray):
    def __new__(cls, wxyz: Sequence[float] | np.ndarray = (1.0, 0.0, 0.0, 0.0)) -> "QuaternionImpl":
        if np.shape(wxyz) != (4,):
            raise ValueError("Quaternion expects 4 values")

        return np.array(wxyz).view(cls)

    def __bool__(self) -> bool:
        """Always evaluate a Quaternion as True, overriding NumPy's default
        behavior that disallows array-to-bool conversion.
        """
        return True

    @property
    def x(self) -> float:
        return self[1]

    @property
    def y(self) -> float:
        return self[2]

    @property
    def z(self) -> float:
        return self[3]

    @property
    def w(self) -> float:
        return self[0]


class MatrixImpl(np.ndarray):
    def __new__(
        cls,
        values: Sequence[Sequence[float]] | np.ndarray = (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
    ) -> "MatrixImpl":
        s = np.shape(values)
        if len(s) != 2:
            raise ValueError(f"Matrix must be 2D, got shape {s}")
        rows, cols = s
        if not (2 <= rows <= 4 and 2 <= cols <= 4):
            raise ValueError(f"Matrix dimensions must be between 2x2 and 4x4, got {rows}x{cols}")

        return np.array(values).view(cls)

    def __bool__(self) -> bool:
        """Always evaluate a Matrix as True, overriding NumPy's default
        behavior that disallows array-to-bool conversion.
        """
        return True

    def transposed(self) -> "MatrixImpl":
        return MatrixImpl(self.T)


if TYPE_CHECKING:
    Vector: TypeAlias = VectorImpl
    Quaternion: TypeAlias = QuaternionImpl
    Matrix: TypeAlias = MatrixImpl

_vector_hook = VectorImpl
_quaternion_hook = QuaternionImpl
_matrix_hook = MatrixImpl


def use_math_types(vector_cls: type, quaternion_cls: type, matrix_cls: type):
    """Override the math types used throughout the library with your own types.
    Call this before importing any other module of the library.

    See `VectorImpl`, `QuaternionImpl` and `MatrixImpl` for the minimal interface required.
    """

    global _vector_hook, _quaternion_hook, _matrix_hook
    _vector_hook = vector_cls
    _quaternion_hook = quaternion_cls
    _matrix_hook = matrix_cls


class DataSource:
    __slots__ = ("name",)

    name: str

    def open(self) -> IO[bytes]:
        """Open the data source and return a file-like object."""
        raise NotImplementedError("DataSource.open() must be implemented by subclasses")

    @staticmethod
    def create(source: str | os.PathLike | bytes, name: str | None = None) -> "DataSource":
        """Factory method to create appropriate DataSource from various input types.

        Args:
            source: File path (str or PathLike) or bytes data.
            name: Optional name for the data source.

        Returns:
            DataSource instance appropriate for the input type

        Raises:
            TypeError: If source type is not supported
        """
        if isinstance(source, (str, os.PathLike)):
            return _DataSourceFile(name, source)
        elif isinstance(source, bytes):
            return _DataSourceBytes(name or "bytes_data", source)
        else:
            raise TypeError(f"Unsupported source type: {type(source).__name__}. Expected str, os.PathLike, or bytes")


class _DataSourceFile(DataSource):
    __slots__ = ("filepath",)

    def __init__(self, name: str | None, filepath: str | os.PathLike):
        self.filepath = Path(filepath)
        self.name = self.filepath.name if name is None else name

    def open(self) -> IO[bytes]:
        return open(self.filepath, "rb")


class _DataSourceBytes(DataSource):
    __slots__ = ("data",)

    def __init__(self, name: str, data: bytes):
        self.name = name
        self.data = data

    def open(self) -> IO[bytes]:
        return io.BytesIO(self.data)


def __getattr__(name: str):
    match name:
        case "Vector":
            return _vector_hook
        case "Quaternion":
            return _quaternion_hook
        case "Matrix":
            return _matrix_hook
        case _:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
