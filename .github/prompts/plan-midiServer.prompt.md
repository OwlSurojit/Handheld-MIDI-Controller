# Plan: MIDI Server for Handheld IMU Controllers

**TL;DR**: Python 3.11+ server, binary UDP broadcast (45 bytes, firmware with raw sensor values), two OS threads, One-Euro filtered IMU data, YAML-driven MIDI mapping with hot-update PyQt5 UI, yaw-zone note selection quantized to a musical scale, and a forwarding loopback port so the visualiser runs decoupled in a separate process. No scipy — quaternion ops in plain numpy. Virtual MIDI port via `python-rtmidi`. Workshop leader controls all settings through desktop UI.

---

## Context
- Firmware: Pico W + ICM-20948, DMP Quat6 + **raw accel** + **raw gyro** (no firmware scaling)
- Transport: UDP port **5005** (IMU data), **5006** (visualizer forward) — binary 45-byte struct
- DMP max ODR ~55 Hz; one packet per FIFO frame; no rate cap
- Up to 16 controllers on same LAN; target DAW: Ardour (MIDI 1.0 only)
- Target users: non-musicians playing together; workshop leader via PyQt5 UI; must sound good without effort
- Existing visualiser refactored to binary on port **5006** (forwarded by server)

---

## Decisions
- **Ardour + MIDI 1.0 only.** No MIDI 2.0.
- **No rate cap.** All ~55 Hz frames forwarded to Ardour.
- **≤16 controllers now.** Forward-compatible second-port path in `midi_output.py`, not implemented.
- **Auto-discovery** via firmware broadcast; server assigns IDs on first packet from each IP.
- **No scipy.** Quaternion ops (conjugate, multiply, normalize, →Euler) implemented in `quaternion_utils.py` using numpy only (~50 lines).
- **OneEuroFilter** for One-Euro filter.
- **Yaw for note zone selection** (test drift empirically; Quat9 migration trivial if needed).
- **Teleplot compatibility dropped.** Visualiser refactored to parse binary.
- **Settings UI: PyQt5 desktop app.** Not web — runs on workshop leader's laptop. Hot config updates (changes in UI immediately affect server behavior). Presets save/load for gesture mappings and interface config, NOT instrument assignments (that's DAW's job).
- **UDP ports: 5005 & 5006.** Meaningful names in RTP-MIDI adjacent range; more discoverable than arbitrary 47xxx.

---

## Architecture

```
Firmware (Pico W)
  UDP broadcast 255.255.255.255:5005
  45-byte binary packet → any host on LAN

            MIDI Server (main process)
            ┌────────────────────────────────────────────────────┐
            │  Receiver Thread  (0.0.0.0:5005)                   │
            │  recvfrom → parse 45-byte struct                   │
            │  source IP → auto-assign controller ID             │
            │  writes → deque(maxlen=1) per controller           │
            │  AND forwards raw packet → 127.0.0.1:5006          │
            │       ↓                                            │
            │  Processing Thread (poll, 0.5ms sleep)             │
            │  per active controller:                            │
            │    1. pop deque                                    │
            │    2. Scale raw accel/gyro to physical units (g,°/s)
            │    3. One-Euro filter (all 10 signals)             │
            │    4. Rotation → Euler (quaternion_utils)          │
            │    5. Hit detector (gyro onset + accel check)      │
            │    6. Yaw zone → scale degree → MIDI note          │
            │    7. CC/Pitch Bend mapper                         │
            │    8. Delta gate (skip unchanged 7-bit CC)         │
            │    9. rtmidi send                                  │
            │       ↓                                            │
            │  rtmidi Virtual Port                               │
            │  "Handheld MIDI Controller"                        │
            └────────────────────────────────────────────────────┘
                   ↓                      ↓
              Ardour                 PyQt5 Settings UI
          (JACK MIDI Linux,        (workshop leader control:
           CoreMIDI macOS,          mapping editor, scale, thresholds,
           loopMIDI Windows)        presets, re-zero, live status)

Visualiser (separate process)
  binds 0.0.0.0:5006 ← forwarded loopback packets
  parses same 45-byte struct
  unchanged 3D render logic
```

---

## 1. Binary Packet — 45 bytes


`struct.unpack_from('<BIffffffffff', data)` — 1×uint8 + 1×uint32 + 10×float32

| Bytes | Field | Type | Notes |
|-------|-------|------|-------|
| 0 | `controller_id` | `uint8` | hardcoded per device |
| 1–4 | `timestamp_ms` | `uint32 LE` | `millis()` — latency measurement |
| 5–8 | `quat_w` | `float32 LE` | |
| 9–12 | `quat_x` | `float32 LE` | |
| 13–16 | `quat_y` | `float32 LE` | |
| 17–20 | `quat_z` | `float32 LE` | |
| 21–24 | `accel_x` | `float32 LE` | g |
| 25–28 | `accel_y` | `float32 LE` | g |
| 29–32 | `accel_z` | `float32 LE` | g |
| 33–36 | `gyro_x` | `float32 LE` | °/s |
| 37–40 | `gyro_y` | `float32 LE` | °/s |
| 41–44 | `gyro_z` | `float32 LE` | °/s |


## 2. Auto-Discovery
Firmware broadcasts to `255.255.255.255:5005`. Server listens on `0.0.0.0:5005`. First packet from an unknown source IP → auto-assign next available controller ID and log it. Overrides in YAML `known_controllers`. `controller_id` byte is authoritative; IP is for logging only.

## 3. Libraries (minimal)
- **numpy** — already a transitive dep; used for quaternion math and array ops
- **`quaternion_utils.py`** (written by us, ~50 lines) — conjugate, Hamilton product, normalize, quat→Euler (ZYX intrinsic: roll/pitch/yaw). No scipy.
- **`OneEuroFilter`** — One-Euro filter. One instance per signal per controller (10 × N). Parameters tunable per mapping in YAML.
- **`python-rtmidi`** — C++ RtMidi backend for MIDI I/O.
- **PyQt5** — Desktop UI for settings, mapping editor, presets, live control.

## 4. Filtering
One-Euro applied to all 10 raw signals (after scaling accel/gyro, before any mapping). At sensor rest: strong low-pass kills jitter. During fast gestures: cutoff rises to pass through the motion. Quat components filtered independently, then `q /= np.linalg.norm(q)` after each frame.

## 5. Yaw Drift
Quat6 yaw drifts because there is no magnetometer. Pitch and roll are gravity-anchored and stable. Expected drift: 1–5°/min depending on temperature and dynamics.

For note-zone purposes this means the "hit north = root note" reference drifts slowly. Mitigations:
- **Re-zero button** in PyQt UI sends re-zero signal to devices. Users can re-zero whenever they feel drift.
- The yaw zone system works on *relative* yaw from the re-zero reference, not absolute heading.
- Quat9 migration path: swap DMP config in firmware. Server needs no changes.
- Empirical drift test is a verification step (see §Verification).

## 6. MIDI Channel Assignment
Controller ID 0 → channel 1, …, ID 15 → channel 16. Each channel drives a separate Ardour instrument track. Second-port interface is stubbed in `midi_output.py` but not implemented.

## 7. MIDI Mapping

**Default continuous mappings:**

| Source | MIDI | Resolution | Rationale |
|--------|------|------------|-----------|
| `euler_pitch` (fwd/back tilt) | CC7 Volume | 7-bit | Tilting wrist controls loudness — intuitive |
| `euler_roll` (left/right tilt) | CC74 Filter Cutoff | 7-bit | Side-tilting controls brightness |
| `gyro_mag` | CC11 Expression | 7-bit | Overall movement energy → dynamics |
| `accel_mag` | CC2 Breath | 7-bit | Impact/motion intensity |

Pitch Bend is available as a mapping option in YAML for any continuous source — use it for whichever axis needs 14-bit resolution. Yaw is used only for zone-based note selection (not as a continuous CC) to avoid interference from drift.

All overridable in PyQt UI (visual editor + YAML export).

**Hit detection:**
1. **Onset**: gyro magnitude > `gyro_onset_threshold` (default 150°/s). Gyro fires before accel during a wrist-flick.
2. **Confirmation**: accel magnitude > `accel_confirm_threshold` (default 1.5g) within the same 3-sample window.
3. **Velocity**: `v = α·gyro_peak + (1-α)·accel_peak` (both normalised) over a 5-sample post-onset window. Default α=0.6 (gyro-weighted). α is a 1-parameter empirical tunable.
4. **MIDI velocity**: v mapped to [`velocity_min`=20, `velocity_max`=127].
5. **Refractory period**: 250ms — prevents double-trigger.
6. **Note Off**: sent after `note_duration_ms` (default 100ms).

**Note selection — Yaw Zone system:**

The user rotates their wrist/body around the yaw axis (turning the device as if pointing at things around them in a horizontal circle) to select which note fires on the next hit.

- After re-zero, yaw wraps 0°–360° and is divided into N equal sectors
- N = number of notes in the configured scale
- Each sector → scale degree → `root_note + scale[sector]` = MIDI note number
- Sector boundaries have ±3° hysteresis deadband to prevent chatter at crossings
- "Hitting in front of you" = yaw 0° (anchored by re-zero) = root note
- Turning right → higher notes; full rotation wraps back to root

**Musical scale system (`scales.py`):**

| `scale:` value | Semitone offsets | Notes |
|---------------|------------------|-------|
| `pentatonic_major` | [0, 2, 4, 7, 9] | Default — always sounds good |
| `pentatonic_minor` | [0, 3, 5, 7, 10] | |
| `ionian` | [0, 2, 4, 5, 7, 9, 11] | Major scale — 7 zones |
| `dorian` | [0, 2, 3, 5, 7, 9, 10] | |
| `blues` | [0, 3, 5, 6, 7, 10] | |
| `custom` | `custom_scale: [...]` | arbitrary semitone list in YAML |

### 8. Settings UI — PyQt5 Desktop Application

**Purpose:** Workshop leader (non-technical) controls all server behavior without touching terminal or YAML. Changes apply hot (immediately).

**Architecture:**
- **Main window** (`ui/main_window.py`) — tabbed interface
  - **Controllers tab** — list of connected devices (ID, IP, name, channel, signal strength/latency)
  - **Mapping editor tab** — visual editor for gesture→MIDI mappings (drag-drop CC assignment, range tweaks)
  - **Scale & zones tab** — dropdown preset (pentatonic_major, minor, ionian, blues, custom) + visual zone wheel showing yaw sectors
  - **Hit detector tab** — sliders for `gyro_onset_threshold`, `accel_confirm_threshold`, velocity range
  - **Presets tab** — save/load interface configs (NOT instruments), includes templates (minimal, full, custom)
  - **Status tab** — real-time metrics (FPS, latency p50/p99, frame drops, per-controller signal health)

- **Re-zero control** — button to send re-zero signal to all active controllers (broadcasts to port 5005)

- **Hot config updates** (`config_sync.py`) — `threading.RWLock` around config dict; UI writes via REST-like internal API; processing thread reads with read lock

- **Preset system** — save current mappings/scales/thresholds as `.preset.yaml`; load preset and hot-update server state

- **Technology stack:**
  - **PyQt5** — native desktop app, cross-platform
  - **pyqtgraph** (optional) — for zone wheel visualization, latency graph
  - **YAML serialization** — mappings stored as YAML blocks, human-readable/editable
  - **threading.RWLock** — config sync between UI and processing threads

**UX flow:**
1. Leader launches `python server/main.py --ui`
2. PyQt window opens; shows discovered controllers as they appear
3. Leader selects scale preset (pentatonic_major by default) from dropdown
4. Zone wheel updates visually
5. Leader adjusts CC mappings by dragging in the editor or clicking presets
6. Leader sets thresholds via sliders
7. All changes apply to server immediately; MIDI events reflect new config in <100ms
8. Leader can save current config as a preset for next workshop
9. Press "re-zero" button → server broadcasts re-zero signal to all controllers

**Implementation phases:**
- **Phase 1 (MVP):** Controllers tab + basic scale/zone selector + preset load/save
- **Phase 2:** Mapping editor (visual or YAML text box)
- **Phase 3:** Hit detector sliders + threshold tuning
- **Phase 4:** Pre-built templates and UX polish

## 9. Thread Model
- **Receiver thread**: tight `recvfrom` loop → unpack struct → scale raw values → `deque[id].append(pkt)` → `sendto(127.0.0.1:5006)`. No heavy work; GIL released during syscall.
- **Processing thread**: iterate active controllers → `popleft` if non-empty → filter → Euler → hit FSM → zone → CC map → delta gate → rtmidi send → `time.sleep(0.0005)` only if all deques empty.
- **Config update thread** (optional): UI writes to config dict via lock; processing thread reads with lock. No busy-wait.
- `os.nice(-10)` on Linux/macOS; `psutil.Process().nice(-10)` cross-platform; `HIGH_PRIORITY_CLASS` on Windows via `ctypes`.

## 10. Virtual MIDI Port — Windows clarification

RtMidi's WinMM backend **does not support `openVirtualPort()`** — it raises `RtMidiError: INVALID_USE` because WinMM has no virtual port concept. The UWP/Windows MIDI Services backend exists in RtMidi source but is **not compiled into standard `python-rtmidi` PyPI wheels**. Therefore on Windows, loopMIDI remains the practical requirement.

What the Windows user does: install loopMIDI (free), create a port named `"Handheld MIDI Controller"`, start the server — it finds and opens that port by name.

| OS | Backend | Virtual port |
|----|---------|-------------|
| Linux + Ardour | **JACK** (preferred) | Native virtual port; appears in Ardour's JACK MIDI matrix |
| Linux ALSA | ALSA | Native virtual port |
| macOS | CoreMIDI | Native virtual port |
| Windows | WinMM | `openPort()` to existing loopMIDI port (not `openVirtualPort()`) |

`midi_output.py` handles backend detection and selection. Prints a clear error message if on Windows and no loopMIDI port is found.

## 11. Visualiser Refactoring (`utils/visualiser.py`)
Changes are minimal — only the ingest path:
- `UDP_PORT = 5006`
- `_udp_listener`: replace regex parse with `struct.unpack_from('<BIffffffffff', raw)` → extract controller_id, timestamp_ms, quat, accel, gyro
- Add multi-controller selector (Tab cycles through active controllers)
- All 3D rendering, graph panel, quaternion math, camera controls unchanged
- `SO_REUSEADDR` already present; no other socket changes

## 12. YAML Config (default)
```yaml
# Network
udp_port: 5005
visualiser_forward_port: 5006       # null to disable forwarding
midi_port_name: "Handheld MIDI Controller"
midi_backend: auto                  # auto | jack | alsa | coremidi | winmm

# Controllers
controllers:
  auto_assign: true
  known:
    "192.168.1.50": { id: 0, channel: 1, name: "Player 1" }

# Scale and zones
scale: pentatonic_major
root_note: 60                       # C4
yaw_zone_hysteresis: 3              # degrees deadband at zone boundaries

# MIDI Mappings
mappings:
  volume:
    source: euler_pitch
    type: cc
    cc_number: 7
    range: [-60, 60]
    filter: { min_cutoff: 2.0, beta: 0.02 }
  filter_cutoff:
    source: euler_roll
    type: cc
    cc_number: 74
    range: [-45, 45]
    filter: { min_cutoff: 1.5, beta: 0.01 }
  expression:
    source: gyro_mag
    type: cc
    cc_number: 11
    range: [0, 500]
    filter: { min_cutoff: 3.0, beta: 0.05 }
  breath:
    source: accel_mag
    type: cc
    cc_number: 2
    range: [0, 4]
    filter: { min_cutoff: 3.0, beta: 0.05 }

# Hit detection thresholds
hit_detector:
  gyro_onset_threshold: 150         # °/s
  accel_confirm_threshold: 1.5      # g
  velocity_min: 20
  velocity_max: 127
  refractory_ms: 250
  note_duration_ms: 100
```

---

## File Structure
```
server/
  main.py              — entry point, arg parsing (--ui flag for PyQt), thread startup, SIGINT handler
  config.py            — YAML loader + schema validation (clear errors on bad config)
  receiver.py          — UDP receiver thread + visualiser forward
  controller_state.py  — per-controller state: deque, filters, re-zero ref, hit FSM
  scales.py            — built-in scale table + custom scale loader
  quaternion_utils.py  — conjugate, multiply, normalize, →Euler (numpy only, ~50 lines)
  midi_mapper.py       — CC/Pitch Bend mapper + hit detector + yaw zone mapper + raw→physical scaling
  midi_output.py       — rtmidi port wrapper + backend selection (stub for future multi-port)
  config_sync.py       — threading.RWLock + config hot-update API
  config.yaml          — default config
  requirements.txt     — python-rtmidi, PyYAML, numpy, OneEuroFilter, PyQt5

ui/
  main_window.py       — PyQt5 main window, tab widget layout
  widgets/
    controller_list.py  — QListWidget showing connected controllers
    mapping_editor.py   — visual editor for gesture→CC mappings (or YAML text box)
    scale_selector.py   — dropdown + zone wheel visualization
    hit_detector_panel.py — threshold sliders + visual feedback
    preset_manager.py   — save/load config presets
    status_monitor.py   — FPS, latency, signal health gauges
  dialogs/
    settings_dialog.py  — advanced config dialog
  resources.qrc        — icons, stylesheet (optional)

utils/
  visualiser.py        — (existing, refactored to binary on port 5006)
```

---

## Firmware Changes Required
1. `UDP_REMOTE_IP` → `IPAddress(255, 255, 255, 255)` (broadcast)
2. `UDP_REMOTE_PORT` → `5005` (new port)
3. Enable broadcast on the `WiFiUDP` socket: `udp.enableBroadcast(true)` (or equivalent lwIP option)
4. Replace `snprintf`/`sendUdpMessage` with packed struct:
   ```cpp
   struct __attribute__((packed)) Packet {
     uint8_t id; uint32_t ts;
     float qw, qx, qy, qz, ax, ay, az, gx, gy, gz;
   };
   Packet pkt = { CONTROLLER_ID, (uint32_t)millis(), q0,q1,q2,q3, ax,ay,az, gx,gy,gz };
   udp.beginPacket(UDP_REMOTE_IP, UDP_REMOTE_PORT);
   udp.write((uint8_t*)&pkt, sizeof(pkt));
   udp.endPacket();
   ```
5. Keep DMP, sensor, and calibration unchanged.
6. Optional: keep `#ifdef DEBUG_TELEPLOT` path on port 47269 for debugging (disabled by default).

---

## Verification
1. **Binary packet size:** `python -c "import struct; print(struct.calcsize('<BIffffffffff'))"` → assert **45**
2. **Port declaration:** Wireshark shows broadcast packets on :5005, 45 bytes, field values match serial log
3. **Auto-discovery:** Two Pico Ws simultaneously → IDs 0 and 1 auto-assigned, MIDI on channels 1 and 2, logged in server stdout
4. **Unit tests** (`midi_mapper.py`): Note On velocity, refractory period, zone transitions with hysteresis
5. **Unit tests** (`scales.py`): all built-in scales produce correct MIDI note per zone
6. **Unit tests** (`quaternion_utils.py`): identity, 90° rotations, Euler extraction vs known values
7. **PyQt UI launch:** `python server/main.py --ui` opens window, discovers controllers
8. **Hot config update:** change scale in UI → zone wheel updates → next note change reflects new scale (no server restart)
9. **Ardour (Linux+JACK):** port visible in MIDI connections, events arrive on correct channels, scale changes in UI affect note output in real-time
10. **Latency:** log `receive_time_ms − pkt.timestamp_ms` over 60s; p99 < 15ms; verify PyQt UI does not increase jitter
11. **Yaw drift:** device stationary 5 min → measure accumulated yaw → document in README
12. **Visualiser + server simultaneously:** both run, no measurable increase in MIDI jitter

