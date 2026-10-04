"""Validation shared by disk loading and the settings editor."""
import math

DEFAULT_SETTINGS = {
    "work_time": 25, "short_break": 5, "long_break": 15,
    "long_break_interval": 4, "sound_enabled": True,
    "unfocus_transparency": 0.8, "label_font_size": 42,
    "timer_mode": "Pomodoro", "window_width": 290, "window_height": 290,
    "maximized_window_width": 240, "maximized_window_height": 80,
    "jsonbin_bin_id": "", "jsonbin_access_key": "",
}
INTEGER_BOUNDS = {
    "work_time": (1, 60), "short_break": (1, 30), "long_break": (1, 60),
    "long_break_interval": (1, 10), "label_font_size": (8, 144),
    "window_width": (80, 8192), "window_height": (44, 8192),
    "maximized_window_width": (80, 8192), "maximized_window_height": (44, 8192),
}

def validate_settings(values):
    if not isinstance(values, dict):
        raise ValueError("Settings must be a JSON object.")
    candidate = DEFAULT_SETTINGS | values
    for key, (minimum, maximum) in INTEGER_BOUNDS.items():
        value = candidate[key]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{key} must be an integer from {minimum} to {maximum}.")
    opacity = candidate["unfocus_transparency"]
    if (type(opacity) not in (int, float) or not math.isfinite(opacity)
            or not 0.1 <= opacity <= 1.0):
        raise ValueError("Transparency must be between 0.1 and 1.0.")
    if type(candidate["sound_enabled"]) is not bool:
        raise ValueError("Sound enabled must be true or false.")
    if candidate["timer_mode"] not in ("Pomodoro", "Stopwatch"):
        raise ValueError("Timer mode must be Pomodoro or Stopwatch.")
    for key in ("jsonbin_bin_id", "jsonbin_access_key"):
        if not isinstance(candidate[key], str):
            raise ValueError(f"{key} must be text.")
    return candidate
