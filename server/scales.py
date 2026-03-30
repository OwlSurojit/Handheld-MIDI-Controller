# Defines musical scales as lists of semitone offsets from a root note.
# A scale is a dictionary of scale_name -> list_of_semitones.

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
    If name is 'custom', returns the provided custom_scale list.
    """
    if name == "custom":
        return custom_scale if custom_scale is not None else []
    return SCALES.get(name, SCALES["Major (Ionian)"])
