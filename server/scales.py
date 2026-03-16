# Defines musical scales as lists of semitone offsets from a root note.
# A scale is a dictionary of scale_name -> list_of_semitones.

SCALES = {
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "ionian":           [0, 2, 4, 5, 7, 9, 11],  # Major
    "dorian":           [0, 2, 3, 5, 7, 9, 10],
    "phrygian":         [0, 1, 3, 5, 7, 8, 10],
    "lydian":           [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":       [0, 2, 4, 5, 7, 9, 10],
    "aeolian":          [0, 2, 3, 5, 7, 8, 10],  # Natural Minor
    "locrian":          [0, 1, 3, 5, 6, 8, 10],
    "blues":            [0, 3, 5, 6, 7, 10],
    "chromatic":        list(range(12)),
}

def get_scale(name: str, custom_scale: list = None):
    """
    Returns a scale by name from the SCALES dictionary.
    If name is 'custom', returns the provided custom_scale list.
    """
    if name == "custom":
        return custom_scale if custom_scale is not None else []
    return SCALES.get(name, SCALES["pentatonic_major"])
