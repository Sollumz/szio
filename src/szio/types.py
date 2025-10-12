from typing import TYPE_CHECKING, Sequence, TypeAlias

import numpy as np

__all__ = [
    "Vector",
    "Quaternion",
    "Matrix",
    "use_math_types",
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
