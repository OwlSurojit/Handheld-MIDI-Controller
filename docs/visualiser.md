# Visualiser Documentation — ICM-20948 Quaternion Orientation Visualiser

## Overview

Real-time 3D orientation and sensor visualiser. Receives UDP data from the Pico W and renders a live PCB-shaped box with acceleration and angular-velocity arrows, plus a toggleable graph panel.

**Dependencies:** `pip install pygame PyOpenGL`  
**Run:** `python utils/visualiser.py`

---

## Architecture

```
UDP socket thread  ──writes──►  shared state (_quat, _accel, _gyro)
                                      │
                               main() render loop (60 fps)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                  ▼
              3D scene           graph panel         window title
           (glViewport top)   (glViewport bottom)    (HUD fallback)
```

The listener runs in a daemon thread and writes under `_quat_lock`. The render loop reads under the same lock to avoid torn quaternion updates.

---

## UDP Parsing

```python
_PACKET_RE = re.compile(r"(\w+):([-\d.eE+]+)\|")
```

A single regex pass over the raw packet text extracts all `key:value` pairs into a dict. Fields: `quat_w/x/y/z`, `accel_x/y/z`, `gyro_x/y/z`. Missing fields are silently ignored.

A `STALE_TIMEOUT` of 2 s triggers a grey-out and "NO SIGNAL" display.

---

## Quaternion Pipeline

1. **Receive** raw sensor quaternion (w, x, y, z).
2. **Apply offset** via `_apply_offset()` — multiplies by the conjugate of the reference quaternion (`_quat_ref`). Space zeroes the current pose; pressing Space again resets.
3. **Axis remap** via `_sensor_to_gl()` — maps ICM-20948 body frame to OpenGL world frame:

   | ICM-20948 | OpenGL |
   |-----------|--------|
   | X (right) | X (right) |
   | Y (forward) | −Z (into screen) |
   | Z (up) | Y (up) |

4. **GL matrix** — `_quat_to_gl_matrix()` converts the unit quaternion to a 16-element column-major rotation matrix for `glMultMatrixf`.

---

## 3D Scene

- **PCB box** (`_draw_box`) — flat rectangle (0.8 × 2.0 × 0.18 GL units). Six faces with distinct colours (green top = component side). Fades to grey when signal is stale.
- **World axes** — X red, Y green, Z blue, 3 GL units long.
- **Grid** — flat Y=0 plane, 16×16 cells, slightly brighter on X/Z axes.
- **Acceleration arrow** (`_draw_accel_vector`) — cyan, capped at 4 g (1 g = 1.5 GL units). Drawn in sensor body frame so it rotates with the box.
- **Angular velocity arrow** (`_draw_gyro_vector`) — magenta, capped at 1000 °/s (500 °/s = 1.5 GL units).

Both arrows use `_draw_arrow()` — a shared helper that normalises the vector, builds a capped shaft, constructs an orthonormal basis for the cone head, and draws it with `GL_TRIANGLE_FAN`.

The sensor→GL axis remap is applied inside each vector function (`ax, az, -ay`), keeping the body-frame drawing consistent with the quaternion rotation.

### Camera

Spherical-coordinate orbit camera:

| Input | Action |
|-------|--------|
| LMB drag | azimuth / elevation |
| Scroll wheel | zoom (clamped 2–50 units) |
| Elevation | clamped ±89° to prevent flip |

---

## Graph Panel (Tab)

Toggled with **Tab**. The window grows by `_PANEL_H = 200 px`; the 3D viewport shifts up by the same amount. Closing restores the original size.

Two scrolling magnitude plots, each holding the last 500 samples (~8 s at 60 fps):

| Graph | Signal | Colour | Y range | Grid lines |
|-------|--------|--------|---------|-----------|
| Left | `\|a\|` = √(ax²+ay²+az²) | Cyan | 0–8 g | 1, 2, 4, 6 g |
| Right | `\|ω\|` = √(gx²+gy²+gz²) | Magenta | 0–2000 °/s | 500, 1k, 1.5k |

The panel uses a separate `glViewport` and `glOrtho` projection, pushed/popped cleanly around the draw call, with depth test disabled for the duration.

### Text labels

The window is `DOUBLEBUF | OPENGL` — there is no pygame 2D surface to blit onto. Text is rendered via:

```
pygame.font.render()  →  RGBA Surface  →  GL_TEXTURE_2D  →  textured quad
```

`_draw_text(font, text, x, y, color)` creates, uses, and immediately deletes a texture each call. At the panel's draw rate this is cheap. Labels rendered:
- Graph title + live value in each half's top row
- Y-axis tick annotations at each grid line

---

## HUD (Window Title)

`_update_title()` writes `|a|`, `|ω|`, FPS, quaternion components, and key hints to the window title bar. Zero overhead — no GL texture allocation.

---

## Key Bindings

| Key | Action |
|-----|--------|
| Space | Zero current pose / reset zero |
| Tab | Toggle graph panel |
| Esc | Quit |
| LMB drag | Orbit camera |
| Scroll | Zoom |
