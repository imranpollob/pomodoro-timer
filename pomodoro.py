import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import os
import sys

SETTINGS_FILE = "settings.json"
FONT_FAMILY = "Helvetica"

settings = {
    "work_time": 25,
    "short_break": 5,
    "long_break": 15,
    "long_break_interval": 4,
    "sound_enabled": True,
    "unfocus_transparency": 0.8,
    "label_font_size": 42,
    "timer_mode": "Pomodoro",
}

current_mode = "Work"
completed_pomodoros = 0
timer_running = False
pomodoro_time = 0


def load_settings():
    global settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                loaded = json.load(f)
                settings.update(loaded)
        except Exception as e:
            print(f"Error loading settings: {e}")


def save_settings():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")


load_settings()


def get_resource_path(filename):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


def apply_window_icon(window):
    icon_path = get_resource_path("stopwatch.ico")
    if os.path.exists(icon_path):
        try:
            window.iconbitmap(icon_path)
        except tk.TclError:
            pass


def on_focus_in(event):
    root.wm_attributes("-alpha", 1.0)


def on_focus_out(event):
    root.wm_attributes("-alpha", settings["unfocus_transparency"])


def open_settings_dialog():
    settings_win = tb.Toplevel(root)
    apply_window_icon(settings_win)
    settings_win.title("Settings")
    settings_win.geometry("320x400")
    settings_win.attributes("-topmost", True)

    def create_slider(parent, label_text, var, from_, to, is_float=False):
        frame = tb.Frame(parent)
        frame.pack(pady=5, fill="x", padx=20)

        val_label = tb.Label(
            frame,
            text=(
                f"{label_text} {var.get():.1f}"
                if is_float
                else f"{label_text} {var.get()}"
            ),
            font=(FONT_FAMILY, 10),
        )
        val_label.pack(anchor="w")

        def update_label(val):
            v = float(val) if is_float else int(float(val))
            var.set(v)
            val_label.config(
                text=f"{label_text} {v:.1f}" if is_float else f"{label_text} {v}"
            )

        scale = tb.Scale(
            frame,
            from_=from_,
            to=to,
            orient="horizontal",
            command=update_label,
            bootstyle="info",
        )
        scale.set(var.get())
        scale.pack(fill="x", pady=2)
        return scale

    work_var = tk.IntVar(value=settings["work_time"])
    create_slider(settings_win, "Work Time (min):", work_var, 1, 60)

    short_var = tk.IntVar(value=settings["short_break"])
    create_slider(settings_win, "Short Break (min):", short_var, 1, 30)

    long_var = tk.IntVar(value=settings["long_break"])
    create_slider(settings_win, "Long Break (min):", long_var, 1, 60)

    interval_var = tk.IntVar(value=settings["long_break_interval"])
    create_slider(settings_win, "Long Break Interval:", interval_var, 1, 10)

    sound_var = tk.BooleanVar(value=settings["sound_enabled"])
    tb.Checkbutton(
        settings_win,
        text="Play Sound on Finish",
        variable=sound_var,
        bootstyle="success, round-toggle",
    ).pack(pady=10)

    trans_var = tk.DoubleVar(value=settings["unfocus_transparency"])
    create_slider(
        settings_win, "Unfocused Transparency:", trans_var, 0.1, 1.0, is_float=True
    )

    def save():
        try:
            settings["work_time"] = int(work_var.get())
            settings["short_break"] = int(short_var.get())
            settings["long_break"] = int(long_var.get())
            settings["long_break_interval"] = int(interval_var.get())
            settings["sound_enabled"] = sound_var.get()
            settings["unfocus_transparency"] = float(trans_var.get())
            save_settings()
            root.attributes("-alpha", settings["unfocus_transparency"])
            if not timer_running:
                if settings["timer_mode"] == "Stopwatch":
                    set_mode("Stopwatch")
                else:
                    if current_mode == "Stopwatch":
                        set_mode("Work")
                    else:
                        set_mode(current_mode)
            settings_win.destroy()
        except ValueError:
            pass  # Ignore invalid inputs

    tb.Button(
        settings_win, text="Save Settings", command=save, bootstyle="success", width=20
    ).pack(pady=15)


def set_mode(mode):
    global current_mode, pomodoro_time
    current_mode = mode
    if mode == "Work":
        pomodoro_time = settings["work_time"] * 60
        mode_label.config(
            text=f"{mode} {completed_pomodoros + 1}/{settings['long_break_interval']}",
            bootstyle="primary",
        )
    elif mode == "Short Break":
        pomodoro_time = settings["short_break"] * 60
        mode_label.config(text=mode, bootstyle="success")
    elif mode == "Long Break":
        pomodoro_time = settings["long_break"] * 60
        mode_label.config(text=mode, bootstyle="info")
    elif mode == "Stopwatch":
        pomodoro_time = 0
        mode_label.config(text="Stopwatch", bootstyle="secondary")

    if mode in ["Short Break", "Long Break"]:
        try:
            skip_btn.pack(pady=4)
        except NameError:
            pass
    else:
        try:
            skip_btn.pack_forget()
        except NameError:
            pass

    minutes, seconds = divmod(pomodoro_time, 60)
    timer_label.config(text=f"{minutes:02d}:{seconds:02d}")


def start_pomodoro():
    global timer_running
    if not timer_running:
        timer_running = True
        start_btn.config(text="Pause", command=pause_pomodoro, bootstyle="warning")

        # Disable mode toggle buttons while timer is running
        for child in mode_frame.winfo_children():
            child.configure(state="disabled")

        update_timer()
    else:
        pause_pomodoro()


def pause_pomodoro():
    global timer_running
    timer_running = False
    start_btn.pack_forget()
    continue_btn.pack(pady=5)
    restart_btn.pack(pady=5)
    if current_mode in ["Short Break", "Long Break"]:
        try:
            skip_btn.pack_forget()
            skip_btn.pack(pady=4)
        except NameError:
            pass


def continue_pomodoro():
    global timer_running
    timer_running = True
    continue_btn.pack_forget()
    restart_btn.pack_forget()
    start_btn.config(text="Pause", command=pause_pomodoro, bootstyle="warning")
    start_btn.pack(pady=5)
    if current_mode in ["Short Break", "Long Break"]:
        try:
            skip_btn.pack_forget()
            skip_btn.pack(pady=4)
        except NameError:
            pass
    update_timer()


def restart_pomodoro():
    global timer_running
    timer_running = False

    try:
        continue_btn.pack_forget()
        restart_btn.pack_forget()
        skip_btn.pack_forget()
    except NameError:
        pass

    start_btn.config(text="Start", command=start_pomodoro, bootstyle="primary")
    start_btn.pack(pady=5)

    # Re-enable mode toggle buttons
    for child in mode_frame.winfo_children():
        child.configure(state="normal")

    if settings.get("timer_mode") == "Stopwatch":
        set_mode("Stopwatch")
    else:
        set_mode(current_mode)


def skip_break():
    global timer_running, completed_pomodoros
    timer_running = False

    try:
        continue_btn.pack_forget()
        restart_btn.pack_forget()
        skip_btn.pack_forget()
    except NameError:
        pass

    start_btn.config(text="Start", command=start_pomodoro, bootstyle="primary")
    start_btn.pack(pady=4)

    # Re-enable mode toggle buttons
    for child in mode_frame.winfo_children():
        child.configure(state="normal")

    if current_mode == "Long Break":
        completed_pomodoros = 0
        
    set_mode("Work")


def update_timer():
    global pomodoro_time, timer_running, completed_pomodoros, current_mode
    if timer_running:
        if current_mode == "Stopwatch":
            minutes, seconds = divmod(pomodoro_time, 60)
            timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
            pomodoro_time += 1
            root.after(1000, update_timer)
        else:
            if pomodoro_time > 0:
                minutes, seconds = divmod(pomodoro_time, 60)
                timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
                pomodoro_time -= 1
                root.after(1000, update_timer)
            else:
                if settings["sound_enabled"]:
                    if sys.platform == "linux":
                        sound_file = get_resource_path("complete.oga")
                        os.system(f'paplay "{sound_file}" 2>/dev/null &')
                    else:
                        root.bell()

                timer_running = False
                start_btn.config(
                    text="Start", command=start_pomodoro, bootstyle="primary"
                )

                # Re-enable mode toggle buttons on completion
                for child in mode_frame.winfo_children():
                    child.configure(state="normal")

                if current_mode == "Work":
                    completed_pomodoros += 1
                    if (
                        completed_pomodoros > 0
                        and completed_pomodoros % settings["long_break_interval"] == 0
                    ):
                        set_mode("Long Break")
                    else:
                        set_mode("Short Break")
                else:
                    if current_mode == "Long Break":
                        completed_pomodoros = 0  # reset tracking after long break
                    set_mode("Work")


def create_app():
    global root, mode_label, timer_label, start_btn, continue_btn, restart_btn, skip_btn, mode_frame, mode_var
    root = tb.Window(themename="superhero")
    apply_window_icon(root)
    root.title("Pomodoro")
    root.geometry("290x290")
    root.attributes("-topmost", True)

    # Added toggle mode frame to main UI
    mode_var = tk.StringVar(value=settings.get("timer_mode", "Pomodoro"))
    mode_frame = tb.Frame(root)
    mode_frame.pack(pady=(12, 0))

    def on_mode_change(*args):
        if not timer_running:
            settings["timer_mode"] = mode_var.get()
            save_settings()
            if settings["timer_mode"] == "Stopwatch":
                set_mode("Stopwatch")
            else:
                set_mode("Work")

    mode_var.trace_add("write", on_mode_change)

    tb.Radiobutton(
        mode_frame, text="Pomodoro", variable=mode_var, value="Pomodoro"
    ).pack(side="left", padx=5)
    tb.Radiobutton(
        mode_frame, text="Stopwatch", variable=mode_var, value="Stopwatch"
    ).pack(side="left", padx=5)

    mode_label = tb.Label(root, text="", font=(FONT_FAMILY, 12, "bold"))
    mode_label.pack(pady=(8, 0))

    timer_label = tb.Label(
        root, text="", font=(FONT_FAMILY, settings["label_font_size"], "bold")
    )
    timer_label.pack(pady=0)

    start_btn = tb.Button(
        root, text="Start", command=start_pomodoro, bootstyle="primary", width=12
    )
    start_btn.pack(pady=4)

    continue_btn = tb.Button(
        root, text="Continue", command=continue_pomodoro, bootstyle="success", width=12
    )
    restart_btn = tb.Button(
        root, text="Restart", command=restart_pomodoro, bootstyle="danger", width=12
    )
    skip_btn = tb.Button(
        root, text="Skip Break", command=skip_break, bootstyle="secondary", width=12
    )

    def increase_font():
        settings["label_font_size"] = min(settings["label_font_size"] + 2, 72)
        timer_label.configure(font=(FONT_FAMILY, settings["label_font_size"], "bold"))
        save_settings()

    def decrease_font():
        settings["label_font_size"] = max(settings["label_font_size"] - 2, 8)
        timer_label.configure(font=(FONT_FAMILY, settings["label_font_size"], "bold"))
        save_settings()

    menu_bar = tk.Menu(root, tearoff=0)
    root.config(menu=menu_bar)

    menu_bar.add_command(label="🔧", command=open_settings_dialog)
    menu_bar.add_command(label="➕", command=increase_font)
    menu_bar.add_command(label="➖", command=decrease_font)

    root.bind("<FocusIn>", on_focus_in)
    root.bind("<FocusOut>", on_focus_out)
    root.attributes("-alpha", settings["unfocus_transparency"])

    if settings.get("timer_mode") == "Stopwatch":
        set_mode("Stopwatch")
    else:
        set_mode("Work")

    root.mainloop()


if __name__ == "__main__":
    create_app()
