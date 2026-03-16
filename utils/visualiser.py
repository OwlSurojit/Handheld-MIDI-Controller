#!/usr/bin/env python3
"""
ICM-20948 Quaternion Orientation Visualizer
Receives UDP packets on port 5006 and renders a real-time 3D box.

Dependencies:
    pip install pygame PyOpenGL
"""

import math
import socket
import threading
import time
from collections import deque

import pygame
from OpenGL.GL import (
    GL_BLEND,
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_LINEAR,
    GL_LINES,
    GL_MODELVIEW,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_PROJECTION,
    GL_QUADS,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TRIANGLE_FAN,
    GL_LINE_STRIP,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glBlendFunc,
    glClear,
    glClearColor,
    glColor3f,
    glColor4f,
    glDeleteTextures,
    glDisable,
    glEnable,
    glEnd,
    glGenTextures,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glMultMatrixf,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glVertex3f,
    glViewport,
)
from OpenGL.GLU import gluLookAt, gluPerspective
from pygame.locals import (
    DOUBLEBUF, KEYDOWN, K_ESCAPE, K_SPACE, K_TAB, MOUSEBUTTONDOWN,
    MOUSEBUTTONUP, MOUSEMOTION, OPENGL, QUIT,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
UDP_IP = "0.0.0.0"
UDP_PORT = 5006
_WIN_W    = 900
_WIN_3D_H = 600
_PANEL_H  = 200
WINDOW_SIZE = (_WIN_W, _WIN_3D_H)
TARGET_FPS = 60
STALE_TIMEOUT = 2.0   # seconds before "no signal" state

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
class ControllerState:
    def __init__(self, controller_id):
        self.id = controller_id
        self.quat = [1.0, 0.0, 0.0, 0.0]  # w, x, y, z
        self.accel = [0.0, 0.0, 0.0]
        self.gyro = [0.0, 0.0, 0.0]
        self.last_packet_time = 0.0
        self.quat_ref = [1.0, 0.0, 0.0, 0.0]

_controllers = {}  # controller_id -> ControllerState
_active_controller_id = -1
_state_lock = threading.Lock()
_running = True
_font_panel = None   # initialised in main() after pygame.init()

# ---------------------------------------------------------------------------
# UDP listener thread
# ---------------------------------------------------------------------------
import struct

# ... existing code ...

# ---------------------------------------------------------------------------
# UDP listener thread
# ---------------------------------------------------------------------------
_PACKET_FORMAT = '<BIffffffffff'
_PACKET_SIZE = struct.calcsize(_PACKET_FORMAT)


def _udp_listener():
    global _active_controller_id
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.1)
    while _running:
        try:
            raw, _ = sock.recvfrom(_PACKET_SIZE)
            if len(raw) != _PACKET_SIZE:
                continue

            cid, ts, qw, qx, qy, qz, ax, ay, az, gx, gy, gz = struct.unpack(_PACKET_FORMAT, raw)

            with _state_lock:
                if cid not in _controllers:
                    _controllers[cid] = ControllerState(cid)
                    if _active_controller_id == -1:
                        _active_controller_id = cid
                
                state = _controllers[cid]
                state.quat = [qw, qx, qy, qz]
                state.accel = [ax, ay, az]
                state.gyro = [gx, gy, gz]
                state.last_packet_time = time.monotonic()

        except socket.timeout:
            pass
        except Exception as e:
            print(f"UDP listener error: {e}")
            pass
    sock.close()


# ---------------------------------------------------------------------------
# Quaternion math
# ---------------------------------------------------------------------------
def _quat_mul(q1, q2):
    """Hamilton product q1 * q2. Both are (w, x, y, z) tuples."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    )


def _quat_conjugate(w, x, y, z):
    """Inverse of a unit quaternion."""
    return (w, -x, -y, -z)


def _apply_offset(state: ControllerState):
    """Remove the reference orientation so the zeroed pose reads as identity."""
    ref_inv = _quat_conjugate(*state.quat_ref)
    return _quat_mul(ref_inv, state.quat)


def _sensor_to_gl(w, x, y, z):
    """Remap ICM-20948 body frame to OpenGL world frame.

    ICM-20948 body axes (datasheet Figure 12):
        X = right,   Y = forward (into screen),  Z = up
    OpenGL world axes (camera at (0,5,8), Y-up):
        X = right,   Y = up,                     Z = toward camera

    Mapping:
        OGL X  <- sensor X  ( right  -> right         )
        OGL Y  <- sensor Z  ( Z-up   -> Y-up           )
        OGL Z  <- -sensor Y ( forward -> -Z = into screen )
    """
    return w, x, z, -y


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _quat_to_gl_matrix(w, x, y, z):
    """Return a 16-element column-major GL rotation matrix from a unit quaternion."""
    x2, y2, z2 = x + x, y + y, z + z
    xx, yy, zz = x * x2, y * y2, z * z2
    xy, xz, yz = x * y2, x * z2, y * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    # Row-major first, then transpose for OpenGL column-major
    return [
        1 - (yy + zz),  xy + wz,        xz - wy,        0,
        xy - wz,        1 - (xx + zz),  yz + wx,        0,
        xz + wy,        yz - wx,        1 - (xx + yy),  0,
        0,              0,              0,              1,
    ]


# PCB-shaped box: wide and flat
_W, _D, _H = 0.8, 2.0, 0.18
_VERTS = [
    (-_W, -_H, -_D), ( _W, -_H, -_D), ( _W,  _H, -_D), (-_W,  _H, -_D),  # back  0-3
    (-_W, -_H,  _D), ( _W, -_H,  _D), ( _W,  _H,  _D), (-_W,  _H,  _D),  # front 4-7
]
_FACES = [
    ((4, 5, 6, 7), (0.20, 0.80, 0.35)),  # top (green)  – component side
    ((0, 1, 2, 3), (0.15, 0.50, 0.20)),  # bottom
    ((4, 5, 1, 0), (0.20, 0.55, 1.00)),  # front edge (blue)
    ((7, 6, 2, 3), (0.15, 0.40, 0.75)),  # back edge
    ((4, 0, 3, 7), (1.00, 0.80, 0.10)),  # left  (yellow)
    ((5, 1, 2, 6), (1.00, 0.55, 0.05)),  # right (orange)
]
_EDGES = [
    (0,1),(1,2),(2,3),(3,0),
    (4,5),(5,6),(6,7),(7,4),
    (0,4),(1,5),(2,6),(3,7),
]


def _draw_box(stale: bool):
    alpha = 0.35 if stale else 1.0
    glBegin(GL_QUADS)
    for face_idx, (idxs, rgb) in enumerate(_FACES):
        glColor3f(rgb[0] * alpha, rgb[1] * alpha, rgb[2] * alpha)
        for i in idxs:
            glVertex3f(*_VERTS[i])
    glEnd()

    glLineWidth(1.5)
    edge_grey = 0.08 if stale else 0.0
    glColor3f(edge_grey, edge_grey, edge_grey)
    glBegin(GL_LINES)
    for a, b in _EDGES:
        glVertex3f(*_VERTS[a])
        glVertex3f(*_VERTS[b])
    glEnd()


def _draw_axes():
    glLineWidth(2.5)
    glBegin(GL_LINES)
    glColor3f(1.0, 0.2, 0.2); glVertex3f(0, 0, 0); glVertex3f(3, 0, 0)  # X red
    glColor3f(0.2, 1.0, 0.2); glVertex3f(0, 0, 0); glVertex3f(0, 3, 0)  # Y green
    glColor3f(0.2, 0.4, 1.0); glVertex3f(0, 0, 0); glVertex3f(0, 0, 3)  # Z blue
    glEnd()

def _draw_arrow(gx: float, gy: float, gz: float,
                shaft_color: tuple, head_color: tuple,
                gl_scale: float, cap: float):
    """Draw a vector arrow from origin in GL body frame.

    gl_scale: GL units per sensor unit. cap: sensor magnitude at which display length saturates.
    """
    mag = math.sqrt(gx*gx + gy*gy + gz*gz)
    if mag < 0.01:
        return
    display_len = min(mag, cap) * gl_scale
    nx, ny, nz = gx / mag, gy / mag, gz / mag
    shaft_end = (nx * display_len * 0.82,
                 ny * display_len * 0.82,
                 nz * display_len * 0.82)
    tip = (nx * display_len, ny * display_len, nz * display_len)

    glLineWidth(2.5)
    glColor3f(*shaft_color)
    glBegin(GL_LINES)
    glVertex3f(0.0, 0.0, 0.0)
    glVertex3f(*shaft_end)
    glEnd()

    perp = (0.0, -nz, ny) if abs(nx) < 0.9 else (-nz, 0.0, nx)
    perp_len = math.sqrt(perp[0]**2 + perp[1]**2 + perp[2]**2)
    ux, uy, uz = perp[0]/perp_len, perp[1]/perp_len, perp[2]/perp_len
    vx = ny*uz - nz*uy; vy = nz*ux - nx*uz; vz = nx*uy - ny*ux
    radius = display_len * 0.09
    glColor3f(*head_color)
    glBegin(GL_TRIANGLE_FAN)
    glVertex3f(*tip)
    for i in range(13):
        angle = 2.0 * math.pi * i / 12
        glVertex3f(
            shaft_end[0] + radius*(math.cos(angle)*ux + math.sin(angle)*vx),
            shaft_end[1] + radius*(math.cos(angle)*uy + math.sin(angle)*vy),
            shaft_end[2] + radius*(math.cos(angle)*uz + math.sin(angle)*vz),
        )
    glEnd()


def _draw_accel_vector(ax: float, ay: float, az: float):
    """Cyan arrow: acceleration in sensor body frame. 1 g = 1.5 GL units, cap 4 g."""
    _draw_arrow(ax, az, -ay, (0.0, 0.85, 0.85), (0.0, 0.65, 0.65), 1.5, 4.0)


def _draw_gyro_vector(gx: float, gy: float, gz: float):
    """Magenta arrow: angular velocity in sensor body frame. 500 dps = 1.5 GL units, cap 1000 dps."""
    _draw_arrow(gx, gz, -gy, (0.9, 0.2, 1.0), (0.7, 0.1, 0.8), 1.5 / 500.0, 1000.0)


def _draw_grid(half=8, step=1):
    """Draw a flat grid on Y=0, spanning [-half, half] in X and Z."""
    glLineWidth(1.0)
    glBegin(GL_LINES)
    for i in range(-half, half + 1):
        # Lines along Z
        if i == 0:
            glColor3f(0.35, 0.35, 0.40)   # slightly brighter on the axes
        else:
            glColor3f(0.20, 0.20, 0.24)
        glVertex3f(i * step, 0, -half * step)
        glVertex3f(i * step, 0,  half * step)
        # Lines along X
        if i == 0:
            glColor3f(0.35, 0.35, 0.40)
        else:
            glColor3f(0.20, 0.20, 0.24)
        glVertex3f(-half * step, 0, i * step)
        glVertex3f( half * step, 0, i * step)
    glEnd()


# ---------------------------------------------------------------------------
# Text rendering helper  (pygame font → one-shot OpenGL texture → quad)
# ---------------------------------------------------------------------------
def _draw_text(font, text: str, x: float, y: float, color):
    """Render *text* at ortho coord (x, y) as bottom-left corner.

    Renders via pygame font → RGBA surface → GL texture → textured quad.
    Texture is created and deleted each call (cheap for the small panel).
    """
    r, g, b = color
    raw = font.render(text, True, (int(r * 255), int(g * 255), int(b * 255)))
    raw.set_colorkey((0, 0, 0))          # make black background transparent
    tw, th = raw.get_size()
    surf = pygame.Surface((tw, th), pygame.SRCALPHA, 32)
    surf.fill((0, 0, 0, 0))
    surf.blit(raw, (0, 0))
    data = pygame.image.tostring(surf, "RGBA", True)   # True = flip for GL y-origin

    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1.0, 1.0, 1.0, 1.0)
    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 0.0); glVertex3f(x,      y,      0)
    glTexCoord2f(1.0, 0.0); glVertex3f(x + tw, y,      0)
    glTexCoord2f(1.0, 1.0); glVertex3f(x + tw, y + th, 0)
    glTexCoord2f(0.0, 1.0); glVertex3f(x,      y + th, 0)
    glEnd()
    glDisable(GL_BLEND)
    glDisable(GL_TEXTURE_2D)
    glDeleteTextures([tex])


# ---------------------------------------------------------------------------
# Graph panel  (2D scrolling plots rendered in the bottom strip)
# ---------------------------------------------------------------------------
def _draw_panel(win_w: int, amag_hist, wmag_hist):
    """Render two scrolling magnitude graphs in the bottom _PANEL_H pixels.

    Left  graph: |a| in g      (cyan,    0–8 g)
    Right graph: |ω| in °/s   (magenta, 0–2000 °/s)
    """
    PAD  = 10
    half = win_w // 2
    gb   = PAD              # graph bottom y (OpenGL y=0 is bottom of window)
    gt   = _PANEL_H - PAD   # graph top y
    gh   = gt - gb

    glViewport(0, 0, win_w, _PANEL_H)
    glDisable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, win_w, 0, _PANEL_H, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Background
    glColor3f(0.05, 0.05, 0.09)
    glBegin(GL_QUADS)
    glVertex3f(0,      0,        0)
    glVertex3f(win_w,  0,        0)
    glVertex3f(win_w,  _PANEL_H, 0)
    glVertex3f(0,      _PANEL_H, 0)
    glEnd()

    # Top border
    glLineWidth(1.5)
    glColor3f(0.35, 0.35, 0.42)
    glBegin(GL_LINES)
    glVertex3f(0,     _PANEL_H - 1, 0)
    glVertex3f(win_w, _PANEL_H - 1, 0)
    glEnd()

    # Centre divider
    glColor3f(0.22, 0.22, 0.28)
    glBegin(GL_LINES)
    glVertex3f(half, 1,            0)
    glVertex3f(half, _PANEL_H - 2, 0)
    glEnd()

    def _graph(hist, x0, gw, rgb, y_max, grid_vals):
        # Horizontal grid lines at notable values
        glLineWidth(1.0)
        for gv in grid_vals:
            gy = gb + (gv / y_max) * gh
            glColor3f(0.18, 0.18, 0.22)
            glBegin(GL_LINES)
            glVertex3f(x0,      gy, 0)
            glVertex3f(x0 + gw, gy, 0)
            glEnd()
        # Baseline
        glColor3f(0.28, 0.28, 0.32)
        glBegin(GL_LINES)
        glVertex3f(x0,      gb, 0)
        glVertex3f(x0 + gw, gb, 0)
        glEnd()
        # Scrolling waveform
        if len(hist) < 2:
            return
        n = len(hist)
        glLineWidth(1.5)
        glColor3f(*rgb)
        glBegin(GL_LINE_STRIP)
        for i, v in enumerate(hist):
            px = x0 + (i / (n - 1)) * gw
            py = gb + min(v / y_max, 1.05) * gh
            glVertex3f(px, py, 0)
        glEnd()

    _graph(amag_hist,
           x0=PAD,        gw=half - 2 * PAD,
           rgb=(0.0, 0.85, 0.85), y_max=8.0,
           grid_vals=[1.0, 2.0, 4.0, 6.0])
    _graph(wmag_hist,
           x0=half + PAD, gw=half - 2 * PAD,
           rgb=(0.85, 0.2, 1.0), y_max=2000.0,
           grid_vals=[500.0, 1000.0, 1500.0])

    # --- Text labels: titles, tick values, live readings ---
    if _font_panel is not None:
        CYAN   = (0.0,  0.85, 0.85)
        CYAN_D = (0.0,  0.50, 0.50)
        MAG    = (0.85, 0.20, 1.00)
        MAG_D  = (0.50, 0.10, 0.65)
        gw_l = half - 2 * PAD

        # Left graph — title
        _draw_text(_font_panel, "|a| Accel. (g)", PAD + 2, gt - 14, CYAN)
        # Left graph — live value (top-right corner of left half)
        if amag_hist:
            _draw_text(_font_panel, f"{amag_hist[-1]:.2f}g",
                       PAD + gw_l - 42, gt - 14, CYAN)
        # Left graph — y-axis tick labels
        for gv, lbl in [(1.0, "1g"), (2.0, "2g"), (4.0, "4g"), (6.0, "6g")]:
            gy = gb + (gv / 8.0) * gh
            _draw_text(_font_panel, lbl, PAD + 2, gy + 2, CYAN_D)

        # Right graph — title
        _draw_text(_font_panel, "|\u03c9| Gyro (\u00b0/s)", half + PAD + 2, gt - 14, MAG)
        # Right graph — live value (top-right corner of right half)
        if wmag_hist:
            _draw_text(_font_panel, f"{wmag_hist[-1]:.0f}\u00b0/s",
                       half + PAD + gw_l - 54, gt - 14, MAG)
        # Right graph — y-axis tick labels
        for gv, lbl in [(500.0, "500"), (1000.0, "1k"), (1500.0, "1.5k")]:
            gy = gb + (gv / 2000.0) * gh
            _draw_text(_font_panel, lbl, half + PAD + 2, gy + 2, MAG_D)

    # Restore projection and modelview
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)


# ---------------------------------------------------------------------------
# HUD via pygame surface -> window title  (zero-cost approach)
# ---------------------------------------------------------------------------
def _update_title(state: ControllerState, fps: float, stale: bool, zeroed: bool):
    status = "NO SIGNAL" if stale else f"FPS {fps:4.0f}"
    offset_tag = "  [SPACE: zero]" if not zeroed else "  [SPACE: reset zero]"
    controller_tag = f"  [TAB: switch]  ID: {state.id}"
    
    ax, ay, az = state.accel
    gx, gy, gz = state.gyro
    amag = math.sqrt(ax*ax + ay*ay + az*az)
    wmag = math.sqrt(gx*gx + gy*gy + gz*gz)
    accel_tag = f"  |a|={amag:.2f}g"
    gyro_tag = f"  |ω|={wmag:.0f}°/s"
    
    pygame.display.set_caption(
        f"Handheld MIDI Controller Visualiser | {status}{controller_tag}{offset_tag}{accel_tag}{gyro_tag}"
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    global _running, _font_panel, _active_controller_id

    pygame.init()
    pygame.display.set_mode(WINDOW_SIZE, DOUBLEBUF | OPENGL)
    _font_panel = pygame.font.Font(None, 18)
    clock = pygame.time.Clock()

    listener_thread = threading.Thread(target=_udp_listener, daemon=True)
    listener_thread.start()

    cam_radius = 8.0
    cam_angle_x = 65.0
    cam_angle_y = -45.0
    mouse_down = False
    last_mouse_pos = None

    # History for panel graphs
    accel_mag_hist = deque(maxlen=_WIN_W // 2 - 20)
    gyro_mag_hist = deque(maxlen=_WIN_W // 2 - 20)

    while _running:
        # --- Event handling ---
        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                _running = False
            elif event.type == KEYDOWN:
                if event.key == K_SPACE:
                    with _state_lock:
                        if _active_controller_id in _controllers:
                            state = _controllers[_active_controller_id]
                            # If already zeroed, reset. Otherwise, set new zero.
                            if state.quat_ref != [1.0, 0.0, 0.0, 0.0]:
                                state.quat_ref = [1.0, 0.0, 0.0, 0.0]
                            else:
                                state.quat_ref = list(state.quat)
                elif event.key == K_TAB:
                    with _state_lock:
                        if len(_controllers) > 1:
                            ids = sorted(_controllers.keys())
                            try:
                                current_idx = ids.index(_active_controller_id)
                                next_idx = (current_idx + 1) % len(ids)
                                _active_controller_id = ids[next_idx]
                            except ValueError:
                                if ids: _active_controller_id = ids[0]

            # Camera rotation
            elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                mouse_down = True
                last_mouse_pos = event.pos
            elif event.type == MOUSEBUTTONUP and event.button == 1:
                mouse_down = False
            elif event.type == MOUSEMOTION and mouse_down:
                dx, dy = event.pos[0] - last_mouse_pos[0], event.pos[1] - last_mouse_pos[1]
                cam_angle_y += dx * 0.25
                cam_angle_x = max(-89, min(89, cam_angle_x - dy * 0.25))
                last_mouse_pos = event.pos
            # Camera zoom
            elif event.type == MOUSEBUTTONDOWN and event.button == 4: # scroll up
                cam_radius = max(2.0, cam_radius * 0.9)
            elif event.type == MOUSEBUTTONDOWN and event.button == 5: # scroll down
                cam_radius = min(25.0, cam_radius * 1.1)

        # --- Get current state ---
        state = None
        with _state_lock:
            if _active_controller_id in _controllers:
                state = _controllers[_active_controller_id]

        if state is None:
            glClearColor(0.0, 0.0, 0.0, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            _draw_text(_font_panel, "Waiting for controller data on UDP port 5006...", 20, WINDOW_SIZE[1] / 2, (1,1,1))
            pygame.display.flip()
            clock.tick(10)
            continue

        is_stale = (time.monotonic() - state.last_packet_time) > STALE_TIMEOUT
        is_zeroed = state.quat_ref != [1.0, 0.0, 0.0, 0.0]

        # --- Update graphs ---
        ax, ay, az = state.accel
        gx, gy, gz = state.gyro
        accel_mag_hist.append(math.sqrt(ax*ax + ay*ay + az*az))
        gyro_mag_hist.append(math.sqrt(gx*gx + gy*gy + gz*gz))

        # --- 3D Scene Rendering ---
        glViewport(0, _PANEL_H, _WIN_W, _WIN_3D_H)
        glClearColor(0.1, 0.12, 0.18, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (WINDOW_SIZE[0] / (_WIN_3D_H)), 0.1, 50.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Camera position
        eye_x = cam_radius * math.cos(math.radians(cam_angle_y)) * math.cos(math.radians(cam_angle_x))
        eye_y = cam_radius * math.sin(math.radians(cam_angle_x))
        eye_z = cam_radius * math.sin(math.radians(cam_angle_y)) * math.cos(math.radians(cam_angle_x))
        gluLookAt(eye_x, eye_y, eye_z, 0, 0, 0, 0, 1, 0)

        _draw_grid()
        _draw_axes()

        # Apply rotation from quaternion
        glPushMatrix()
        q_offset = _apply_offset(state)
        q_gl = _sensor_to_gl(*q_offset)
        glMultMatrixf(_quat_to_gl_matrix(*q_gl))

        _draw_box(is_stale)
        if not is_stale:
            _draw_accel_vector(*state.accel)
            _draw_gyro_vector(*state.gyro)
        glPopMatrix()

        # --- 2D Panel Rendering ---
        _draw_panel(_WIN_W, accel_mag_hist, gyro_mag_hist)

        # --- Update title and flip buffer ---
        _update_title(state, clock.get_fps(), is_stale, is_zeroed)
        pygame.display.flip()
        clock.tick(TARGET_FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
