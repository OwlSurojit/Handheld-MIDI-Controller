# Defines musical scales as lists of semitone offsets from a root note.
# A scale is a dictionary of scale_name -> list_of_semitones.

CUSTOM_SCALE_NAME = "Custom"

SCALES = {
    "Major (Ionian)":       [0, 2, 4, 5, 7, 9, 11],  
    "Minor (Aeolian)":      [0, 2, 3, 5, 7, 8, 10],
    "Chromatic":            list(range(12)),
    "Pentatonic (Major)":   [0, 2, 4, 7, 9],
    "Pentatonic (Minor)":   [0, 3, 5, 7, 10],
    "Dorian":               [0, 2, 3, 5, 7, 9, 10],
    "Phrygian":             [0, 1, 3, 5, 7, 8, 10],
    "Lydian":               [0, 2, 4, 6, 7, 9, 11],
    "Mixolydian":           [0, 2, 4, 5, 7, 9, 10],
    "Locrian":              [0, 1, 3, 5, 6, 8, 10],
    "Blues":                [0, 3, 5, 6, 7, 10],
}

def get_scale(name: str, custom_scale: list | None = None):
    """
    Returns a scale by name from the SCALES dictionary.
    If name is 'Custom', returns the provided custom_scale list.
    """
    name_value = str(name or "").strip()
    if name_value.lower() == "custom":
        return list(custom_scale) if custom_scale is not None else []
    return SCALES.get(name_value, SCALES["Major (Ionian)"])


def get_absolute_scale(name: str, root_note: int | None, custom_scale: list | None = None) -> list[int]:
    """Return absolute MIDI notes for the selected scale."""
    root_value = 60 if root_note is None else int(root_note)
    if str(name or "").strip().lower() == "custom":
        raw_notes = custom_scale or []
        notes = sorted({int(note) for note in raw_notes if 0 <= int(note) <= 127})
        if notes:
            return notes
        root_value = min(127, max(0, root_value))
        return [root_value]

    offsets = get_scale(name, None)
    notes = [root_value + int(offset) for offset in offsets]
    return [note for note in notes if 0 <= note <= 127]
