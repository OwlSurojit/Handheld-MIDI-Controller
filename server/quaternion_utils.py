import numpy as np

def quat_conjugate(q):
    """Returns the conjugate of a quaternion (w, x, y, z)."""
    return np.array([q[0], -q[1], -q[2], -q[3]])

def quat_mul(q1, q2):
    """Hamilton product of two quaternions."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ])

def quat_normalize(q):
    """Normalize a quaternion to unit length."""
    norm = np.linalg.norm(q)
    if norm == 0:
        return np.array([1.0, 0.0, 0.0, 0.0])
    if norm == np.inf or norm == -np.inf:
        print(f"Infinite quaternion norm detected: q={q}, norm={norm}")
        return np.array([1.0, 0.0, 0.0, 0.0])
    return q / norm

def quat_to_yaw(q):
    """
    Extract yaw from a quaternion, avoiding gimbal lock.
    Returns yaw in degrees (0-360).
    """
    w, x, y, z = q
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    print(siny_cosp, cosy_cosp)
    yaw = np.arctan2(siny_cosp, cosy_cosp)
    print(yaw)
    return (np.degrees(yaw) + 360) % 360

def quat_to_angle_axis(q):
    """Convert quaternion to angle-axis representation."""
    w, x, y, z = q
    angle = 2 * np.atan2(np.sqrt(x*x + y*y + z*z), w)
    s = np.sqrt(1 - w*w)
    if s < 0.001:
        return angle, np.array([1, 0, 0])  # Arbitrary axis
    else:
        return angle, np.array([x/s, y/s, z/s])