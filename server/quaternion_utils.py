import numpy as np
from typing import Union, Tuple


class Quat:
    """
    Immutable quaternion class (w, x, y, z format).
    Provides quaternion operations for rotations and orientation calculations.
    """
    
    def __init__(self, w: float = 1.0, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """
        Initialize a quaternion.
        
        Args:
            w, x, y, z: Quaternion components
        """
        self._w = float(w)
        self._x = float(x)
        self._y = float(y)
        self._z = float(z)
    
    @classmethod
    def from_array(cls, q: Union[np.ndarray, list]) -> 'Quat':
        """Create a Quat from an array-like object [w, x, y, z]."""
        return cls(q[0], q[1], q[2], q[3])
    
    @classmethod
    def identity(cls) -> 'Quat':
        """Create the identity quaternion [1, 0, 0, 0]."""
        return cls(1.0, 0.0, 0.0, 0.0)
    
    # Properties (read-only)
    @property
    def w(self) -> float:
        return self._w
    
    @property
    def x(self) -> float:
        return self._x
    
    @property
    def y(self) -> float:
        return self._y
    
    @property
    def z(self) -> float:
        return self._z
    
    def __getitem__(self, index: int) -> float:
        """Allow array-like indexing [0]=w, [1]=x, [2]=y, [3]=z."""
        return [self._w, self._x, self._y, self._z][index]
    
    def as_array(self) -> np.ndarray:
        """Return as numpy array [w, x, y, z]."""
        return np.array([self._w, self._x, self._y, self._z])
    
    def __repr__(self) -> str:
        return f"Quat(w={self._w:+.3f}, x={self._x:+.3f}, y={self._y:+.3f}, z={self._z:+.3f})"
    
    def __eq__(self, other: object) -> bool:
        """Check equality between quaternions."""
        if not isinstance(other, Quat):
            return False
        return np.allclose([self._w, self._x, self._y, self._z],
                          [other._w, other._x, other._y, other._z])
    
    def __hash__(self) -> int:
        """Make Quat hashable."""
        return hash((self._w, self._x, self._y, self._z))
    
    def conjugate(self) -> 'Quat':
        """Return the conjugate of this quaternion."""
        return Quat(self._w, -self._x, -self._y, -self._z)
    
    def norm(self) -> float:
        """Return the norm (magnitude) of this quaternion."""
        return np.sqrt(self._w*self._w + self._x*self._x + 
                      self._y*self._y + self._z*self._z)
    
    def normalize(self) -> 'Quat':
        """Return a normalized (unit) version of this quaternion."""
        norm = self.norm()
        if norm == 0:
            return Quat.identity()
        if norm == np.inf or norm == -np.inf:
            print(f"Infinite quaternion norm detected: q={self}, norm={norm}")
            return Quat.identity()
        return Quat(self._w/norm, self._x/norm, self._y/norm, self._z/norm)
    
    def multiply(self, other: 'Quat') -> 'Quat':
        """Return the Hamilton product of this quaternion with another."""
        w1, x1, y1, z1 = self._w, self._x, self._y, self._z
        w2, x2, y2, z2 = other._w, other._x, other._y, other._z
        return Quat(
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2,
        )
    
    def __mul__(self, other: 'Quat') -> 'Quat':
        """Overload * operator for quaternion multiplication."""
        return self.multiply(other)
    
    def inverse(self) -> 'Quat':
        """Return the inverse of this quaternion (conjugate / norm^2)."""
        norm_sq = self._w*self._w + self._x*self._x + self._y*self._y + self._z*self._z
        if norm_sq == 0:
            return Quat.identity()
        conj = self.conjugate()
        return Quat(conj._w/norm_sq, conj._x/norm_sq, conj._y/norm_sq, conj._z/norm_sq)
    
    def to_angle_axis(self) -> Tuple[float, np.ndarray]:
        """
        Convert to angle-axis representation.
        Returns (angle_in_radians, axis_as_unit_vector).
        """
        angle = 2 * np.atan2(np.sqrt(self._x*self._x + self._y*self._y + self._z*self._z), self._w)
        s = np.sqrt(1 - self._w*self._w)
        if s < 0.001:
            axis = np.array([1, 0, 0])  # Arbitrary axis for identity
        else:
            axis = np.array([self._x/s, self._y/s, self._z/s])
        return angle, axis
    
    @staticmethod
    def from_angle_axis(angle: float, axis: np.ndarray) -> 'Quat':
        """Create a quaternion from an angle-axis representation."""
        axis = axis / np.linalg.norm(axis)
        half_angle = angle / 2
        s = np.sin(half_angle)
        return Quat(np.cos(half_angle), axis[0]*s, axis[1]*s, axis[2]*s)
    
    def to_yaw(self) -> float:
        """
        Extract yaw angle from this quaternion, avoiding gimbal lock.
        Returns yaw in degrees (0-360).
        """
        siny_cosp = 2 * (self._w * self._z + self._x * self._y)
        cosy_cosp = 1 - 2 * (self._y * self._y + self._z * self._z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)
        return (np.degrees(yaw) + 360) % 360
    
    def rotate_vector(self, v: np.ndarray) -> np.ndarray:
        """Rotate a 3D vector v by this quaternion."""
        p = Quat(0, v[0], v[1], v[2])
        r = self.multiply(p).multiply(self.conjugate())
        return np.array([r.x, r.y, r.z])
    
    def to_swing_twist(self, twist_axis: np.ndarray) -> Tuple['Quat', 'Quat']:
        """
        Decompose this quaternion into swing and twist components.
        Returns (swing, twist) where twist is rotation around the z-axis.
        """
        p = np.array([self._x, self._y, self._z])

        # if np.dot(p, p) < 1e-8:
        #     rotated_twist_axis = self.rotate_vector(twist_axis)
        #     swing_axis = np.cross(twist_axis, rotated_twist_axis)
        #     if np.dot(swing_axis, swing_axis) < 1e-8:
        #         # If the swing axis is too small, we are aligned with the twist axis
        #         swing = Quat.identity()
        #     else:
        #         swing_angle = np.arctan2(np.linalg.norm(np.cross(twist_axis, rotated_twist_axis)), np.dot(twist_axis, rotated_twist_axis))
        #         swing = Quat.from_angle_axis(swing_angle, swing_axis).normalize()
        #     twist = Quat.from_angle_axis(180, twist_axis).normalize()  # 180 degree twist
        #     return swing, twist
        
        proj = np.dot(p, twist_axis) * twist_axis
        twist = Quat(self._w, proj[0], proj[1], proj[2]).normalize()
        swing = self.multiply(twist.inverse()).normalize()
        return swing, twist
    
    def to_swing_twist_2(self, twist_axis: np.ndarray) -> Tuple['Quat', 'Quat']:
        """
        Alternative swing-twist decomposition that may be more stable.
        """
        p = Quat(0, twist_axis[0], twist_axis[1], twist_axis[2])
        swing = self.multiply(p).multiply(self.conjugate()).normalize()

        proj = np.dot([self._x, self._y, self._z], twist_axis)
        twist = Quat(self._w, proj * twist_axis[0], proj * twist_axis[1], proj * twist_axis[2]).normalize()
        return swing, twist

        

