import tkinter as tk
from tkinter import ttk
import json
import os

SETTINGS_FILE = 'settings.json'

settings = {
    "work_time": 25,
    "short_break": 5,
    "long_break": 15,
    "long_break_interval": 4,
    "sound_enabled": True,
    "unfocus_transparency": 0.8,
    "label_font_size": 14
}

current_mode = "Work"
completed_pomodoros = 0
timer_running = False
pomodoro_time = 0

def load_settings():
    global settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                loaded = json.load(f)
                settings.update(loaded)
        except Exception as e:
            print(f"Error loading settings: {e}")

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

load_settings()

def on_focus_in(event):
    root.wm_attributes("-alpha", 1.0)

def on_focus_out(event):
    root.wm_attributes("-alpha", settings["unfocus_transparency"])

def open_settings_dialog():
    settings_win = tk.Toplevel(root)
    settings_win.title("Settings")
    settings_win.geometry("260x300")
    settings_win.attributes("-topmost", True)
    
    ttk.Label(settings_win, text="Work Time (min):").pack(pady=2)
    work_var = tk.IntVar(value=settings["work_time"])
    ttk.Entry(settings_win, textvariable=work_var, width=10).pack(pady=2)

    ttk.Label(settings_win, text="Short Break (min):").pack(pady=2)
    short_var = tk.IntVar(value=settings["short_break"])
    ttk.Entry(settings_win, textvariable=short_var, width=10).pack(pady=2)

    ttk.Label(settings_win, text="Long Break (min):").pack(pady=2)
    long_var = tk.IntVar(value=settings["long_break"])
    ttk.Entry(settings_win, textvariable=long_var, width=10).pack(pady=2)

    ttk.Label(settings_win, text="Long Break Interval:").pack(pady=2)
    interval_var = tk.IntVar(value=settings["long_break_interval"])
    ttk.Entry(settings_win, textvariable=interval_var, width=10).pack(pady=2)

    sound_var = tk.BooleanVar(value=settings["sound_enabled"])
    ttk.Checkbutton(settings_win, text="Play Sound on Finish", variable=sound_var).pack(pady=5)

    ttk.Label(settings_win, text="Unfocused Transparency (0.1 - 1.0):").pack(pady=2)
    trans_var = tk.DoubleVar(value=settings["unfocus_transparency"])
    ttk.Entry(settings_win, textvariable=trans_var, width=10).pack(pady=2)
    
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
                set_mode(current_mode)
            settings_win.destroy()
        except ValueError:
            pass # Ignore invalid inputs

    ttk.Button(settings_win, text="Save", command=save).pack(pady=10)

def set_mode(mode):
    global current_mode, pomodoro_time
    current_mode = mode
    if mode == "Work":
        pomodoro_time = settings["work_time"] * 60
    elif mode == "Short Break":
        pomodoro_time = settings["short_break"] * 60
    elif mode == "Long Break":
        pomodoro_time = settings["long_break"] * 60
    
    minutes, seconds = divmod(pomodoro_time, 60)
    timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
    if mode == "Work":
        mode_label.config(text=f"{mode} {completed_pomodoros + 1}/{settings['long_break_interval']}")
    else:
        mode_label.config(text=mode)

def start_pomodoro():
    global timer_running
    if not timer_running:
        timer_running = True
        start_btn.config(text="Pause", command=pause_pomodoro)
        update_timer()
    else:
        pause_pomodoro()

def pause_pomodoro():
    global timer_running
    timer_running = False
    start_btn.pack_forget()
    continue_btn.pack(pady=5)
    stop_btn.pack(pady=5)

def continue_pomodoro():
    global timer_running
    timer_running = True
    continue_btn.pack_forget()
    stop_btn.pack_forget()
    start_btn.config(text="Pause", command=pause_pomodoro)
    start_btn.pack(pady=5)
    update_timer()

def stop_pomodoro():
    global timer_running
    timer_running = False
    
    continue_btn.pack_forget()
    stop_btn.pack_forget()
    
    start_btn.config(text="Start", command=start_pomodoro)
    start_btn.pack(pady=5)
    set_mode(current_mode)

def update_timer():
    global pomodoro_time, timer_running, completed_pomodoros, current_mode
    if timer_running:
        if pomodoro_time > 0:
            minutes, seconds = divmod(pomodoro_time, 60)
            timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
            pomodoro_time -= 1
            root.after(1000, update_timer)
        else:
            if settings["sound_enabled"]:
                root.bell()
            
            timer_running = False
            start_btn.config(text="Start", command=start_pomodoro)
            
            if current_mode == "Work":
                completed_pomodoros += 1
                if completed_pomodoros > 0 and completed_pomodoros % settings["long_break_interval"] == 0:
                    set_mode("Long Break")
                else:
                    set_mode("Short Break")
            else:
                if current_mode == "Long Break":
                    completed_pomodoros = 0 # reset tracking after long break 
                set_mode("Work")

def create_app():
    global root, mode_label, timer_label, start_btn, continue_btn, stop_btn
    root = tk.Tk()
    root.title("Pomodoro Timer")
    root.geometry("200x160")
    root.attributes("-topmost", True)

    mode_label = ttk.Label(root, text="", font=("Arial", 10))
    mode_label.pack(pady=5)

    timer_label = ttk.Label(
        root, text="", font=("Arial", settings["label_font_size"], "bold")
    )
    timer_label.pack(pady=5)

    start_btn = ttk.Button(root, text="Start", command=start_pomodoro)
    start_btn.pack(pady=5)

    continue_btn = ttk.Button(root, text="Continue", command=continue_pomodoro)
    stop_btn = ttk.Button(root, text="Stop", command=stop_pomodoro)

    def increase_font():
        settings["label_font_size"] = min(settings["label_font_size"] + 2, 32)
        timer_label.configure(font=("Arial", settings["label_font_size"], "bold"))
        save_settings()

    def decrease_font():
        settings["label_font_size"] = max(settings["label_font_size"] - 2, 8)
        timer_label.configure(font=("Arial", settings["label_font_size"], "bold"))
        save_settings()

    menu_bar = tk.Menu(root, tearoff=0)
    root.config(menu=menu_bar)

    menu_bar.add_command(label="🔧", command=open_settings_dialog)
    menu_bar.add_command(label="➕", command=increase_font)
    menu_bar.add_command(label="➖", command=decrease_font)

    root.bind("<FocusIn>", on_focus_in)
    root.bind("<FocusOut>", on_focus_out)
    root.attributes("-alpha", settings["unfocus_transparency"])
    
    set_mode("Work")

    root.mainloop()


if __name__ == "__main__":
    create_app()
