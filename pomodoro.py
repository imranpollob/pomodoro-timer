import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import os
import sys
from pathlib import Path
from datetime import datetime, date

# Use a proper config directory for settings
if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "pomodoro-timer"
else:
    CONFIG_DIR = Path.home() / ".config" / "pomodoro-timer"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = CONFIG_DIR / "settings.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
TODOS_FILE = CONFIG_DIR / "todos.json"

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
    "window_width": 290,
    "window_height": 290,
    "maximized_window_width": 240,
    "maximized_window_height": 80,
    "is_maximized_state": False,
    "todo_sidebar_visible": False,
    "todo_sidebar_width": 250,
}

current_mode = "Work"
completed_pomodoros = 0
timer_running = False
pomodoro_time = 0
stopwatch_start_time = None
stopwatch_accumulated_seconds = 0
is_maximized = False

# Global UI references initialized later in create_app()
root = None
mode_label = None
timer_label = None
start_btn = None
continue_btn = None
stop_btn = None
skip_btn = None
mode_frame = None
mode_var = None
maximize_btn = None
minimize_btn = None
menu_bar = None
timer_frame = None
main_container = None
todo_container = None
todo_entry = None
todo_list_frame = None
todo_list_canvas = None
sash_toggle_btn = None
editing_todo_ids = set()
todos = []
paned = None
is_updating_layout = True


class SashToggleButton(tk.Canvas):
    def __init__(self, master, command=None, **kwargs):
        style = tb.Style()
        self.bg_normal = style.colors.secondary
        self.bg_hover = style.colors.info
        self.fg_color = "white"
        
        super().__init__(
            master,
            width=18,
            bg=self.bg_normal,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            **kwargs
        )
        self.command = command
        self.text_val = "SHOW TODOS"
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.bind("<Configure>", lambda e: self.draw())

    def on_enter(self, event):
        self.configure(bg=self.bg_hover)

    def on_leave(self, event):
        self.configure(bg=self.bg_normal)

    def on_click(self, event):
        if self.command:
            self.command()

    def set_text(self, text):
        if "\n" in text:
            text = text.replace("\n", "")
        self.text_val = text.upper()
        self.draw()

    def configure(self, cnf=None, **kwargs):
        if cnf is not None:
            if isinstance(cnf, dict) and "text" in cnf:
                self.set_text(cnf.pop("text"))
        if "text" in kwargs:
            self.set_text(kwargs.pop("text"))
        
        if "bootstyle" in kwargs:
            bootstyle = kwargs.pop("bootstyle")
            style = tb.Style()
            if "info" in bootstyle:
                self.configure(bg=style.colors.info)
            elif "secondary" in bootstyle:
                self.configure(bg=style.colors.secondary)
                
        return super().configure(cnf, **kwargs)

    config = configure

    def draw(self):
        self.delete("all")
        h = self.winfo_height()
        w = self.winfo_width()
        if h > 20:
            self.create_text(
                w / 2,
                h / 2,
                text=self.text_val,
                angle=270,
                fill=self.fg_color,
                font=(FONT_FAMILY, 9, "bold")
            )


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


def load_todos():
    global todos
    if TODOS_FILE.exists():
        try:
            with open(TODOS_FILE, "r") as f:
                todos = json.load(f)
        except Exception as e:
            print(f"Error loading todos: {e}")
            todos = []
    else:
        todos = []


def save_todos():
    try:
        with open(TODOS_FILE, "w") as f:
            json.dump(todos, f, indent=4)
    except Exception as e:
        print(f"Error saving todos: {e}")


def add_todo_item():
    text = todo_entry.get().strip()
    if text:
        todo_id = int(datetime.now().timestamp() * 1000)
        todos.append({
            "id": todo_id,
            "text": text,
            "done": False
        })
        save_todos()
        todo_entry.delete(0, tk.END)
        render_todos()


def toggle_todo_status(todo, is_done):
    todo["done"] = is_done
    save_todos()
    render_todos()


def start_edit(todo_id):
    editing_todo_ids.add(todo_id)
    render_todos()


def delete_todo_item(todo):
    if todo in todos:
        todos.remove(todo)
        save_todos()
        render_todos()


def reset_updating_layout():
    global is_updating_layout
    is_updating_layout = False


def on_pane_configure(event):
    if is_updating_layout:
        return
    if settings.get("todo_sidebar_visible", False) and not is_maximized:
        try:
            if todo_container is not None and str(event.widget) == str(todo_container):
                w_todo = todo_container.winfo_width()
                if w_todo > 10:
                    settings["todo_sidebar_width"] = w_todo
            if main_container is not None and str(event.widget) == str(main_container):
                w_main = main_container.winfo_width()
                if w_main > 10:
                    settings["window_width"] = w_main
        except Exception:
            pass


def toggle_todo_sidebar():
    visible = not settings.get("todo_sidebar_visible", False)
    settings["todo_sidebar_visible"] = visible
    save_settings()
    update_todo_layout()


def update_todo_layout():
    global is_updating_layout
    is_updating_layout = True
    try:
        if is_maximized:
            if todo_container is not None and paned is not None:
                try:
                    paned.forget(todo_container)
                except Exception:
                    pass
            return

        visible = settings.get("todo_sidebar_visible", False)
        geom = root.geometry()
        size_pos = geom.split("+")
        size = size_pos[0]
        w, h = map(int, size.split("x"))
        
        sidebar_w = settings.get("todo_sidebar_width", 250)
        
        if visible:
            if paned is not None and str(todo_container) not in paned.panes():
                paned.add(todo_container, weight=1)
            sash_toggle_btn.config(text="Hide Todos".upper())
            if w < 400:
                new_w = w + sidebar_w
                if len(size_pos) > 1:
                    x, y = size_pos[1], size_pos[2]
                    root.geometry(f"{new_w}x{h}+{x}+{y}")
                else:
                    root.geometry(f"{new_w}x{h}")
                
                root.update_idletasks()
                try:
                    paned.sashpos(0, w)
                except Exception:
                    pass
            else:
                root.update_idletasks()
                try:
                    paned.sashpos(0, settings.get("window_width", 290))
                except Exception:
                    pass
        else:
            if paned is not None:
                try:
                    paned.forget(todo_container)
                except Exception:
                    pass
            sash_toggle_btn.config(text="Show Todos".upper())
            if w >= 400:
                new_w = w - sidebar_w
                if len(size_pos) > 1:
                    x, y = size_pos[1], size_pos[2]
                    root.geometry(f"{new_w}x{h}+{x}+{y}")
                else:
                    root.geometry(f"{new_w}x{h}")
    finally:
        root.after(100, reset_updating_layout)


def render_todos():
    global todo_list_frame, todo_list_canvas
    if todo_list_frame is None:
        return
        
    for widget in todo_list_frame.winfo_children():
        widget.destroy()
        
    for todo in todos:
        item_frame = tb.Frame(todo_list_frame)
        item_frame.pack(fill="x", pady=4, padx=5)
        
        todo_id = todo["id"]
        if todo_id in editing_todo_ids:
            edit_var = tk.StringVar(value=todo["text"])
            edit_entry = tb.Entry(
                item_frame,
                textvariable=edit_var,
                font=(FONT_FAMILY, 10),
                bootstyle="info",
            )
            edit_entry.pack(side="left", fill="x", expand=True, padx=2)
            edit_entry.focus_set()
            edit_entry.select_range(0, tk.END)
            edit_entry.icursor(tk.END)
            
            def save_edit(event=None, t=todo, var=edit_var):
                new_text = var.get().strip()
                if new_text:
                    t["text"] = new_text
                    save_todos()
                editing_todo_ids.discard(t["id"])
                render_todos()
                
            edit_entry.bind("<Return>", save_edit)
            
            save_btn = tb.Button(
                item_frame,
                text="✔",
                bootstyle="success-link",
                width=2,
                command=save_edit
            )
            save_btn.pack(side="right", padx=2)
        else:
            var = tk.BooleanVar(value=todo["done"])
            cb = tb.Checkbutton(
                item_frame,
                variable=var,
                bootstyle="success",
                command=lambda t=todo, v=var: toggle_todo_status(t, v.get())
            )
            cb.pack(side="left", padx=2)
            
            fg_color = "gray" if todo["done"] else "white"
            font_style = (FONT_FAMILY, 10, "overstrike") if todo["done"] else (FONT_FAMILY, 10)
            
            lbl = tb.Label(
                item_frame,
                text=todo["text"],
                font=font_style,
                foreground=fg_color,
                anchor="w",
                justify="left",
                wraplength=140
            )
            lbl.pack(side="left", fill="x", expand=True, padx=2)
            lbl.bind("<Double-1>", lambda e, tid=todo_id: start_edit(tid))
            
            edit_btn = tb.Button(
                item_frame,
                text="✏",
                bootstyle="secondary-link",
                width=2,
                command=lambda tid=todo_id: start_edit(tid)
            )
            edit_btn.pack(side="right", padx=2)
            
            del_btn = tb.Button(
                item_frame,
                text="❌",
                bootstyle="danger-link",
                width=2,
                command=lambda t=todo: delete_todo_item(t)
            )
            del_btn.pack(side="right", padx=2)
            
    todo_list_frame.update_idletasks()
    todo_list_canvas.configure(scrollregion=todo_list_canvas.bbox("all"))


load_todos()


def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def log_session(session_type, duration_seconds):
    if duration_seconds < 10:
        return  # Ignore very short sessions
    history = load_history()
    history.append(
        {
            "date": date.today().isoformat(),
            "type": session_type,
            "duration_seconds": int(duration_seconds),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    )
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Error saving history: {e}")


def reset_today_stats():
    today = date.today().isoformat()
    history = load_history()
    new_history = [s for s in history if s.get("date") != today]
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(new_history, f, indent=4)
        return True
    except Exception as e:
        print(f"Error resetting history: {e}")
        return False


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
    if event.widget == root:
        root.wm_attributes("-alpha", 1.0)


def on_focus_out(event):
    if event.widget == root:
        root.wm_attributes("-alpha", settings["unfocus_transparency"])


def open_settings_dialog():
    settings_win = tb.Toplevel(root)
    apply_window_icon(settings_win)
    settings_win.title("Settings")
    settings_win.geometry("320x460")
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

    def reset_stats():
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "Confirm Reset",
            "Are you sure you want to reset today's statistics? This cannot be undone.",
            parent=settings_win
        )
        if confirm:
            if reset_today_stats():
                messagebox.showinfo("Reset Complete", "Today's statistics have been reset.", parent=settings_win)
            else:
                messagebox.showerror("Error", "Could not reset today's statistics.", parent=settings_win)

    tb.Button(
        settings_win,
        text="🗑  Reset Today's Stats",
        command=reset_stats,
        bootstyle="danger-outline",
        width=20
    ).pack(pady=5)

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
    global timer_running, stopwatch_start_time, stopwatch_accumulated_seconds
    if not timer_running:
        timer_running = True
        start_btn.config(text="Pause", command=pause_pomodoro, bootstyle="warning")

        # Track start time for stopwatch
        if current_mode == "Stopwatch":
            stopwatch_accumulated_seconds = 0
            stopwatch_start_time = datetime.now()

        # Disable mode toggle buttons while timer is running
        for child in mode_frame.winfo_children():
            child.configure(state="disabled")

        try:
            maximize_btn.pack(side="left", padx=(5, 0), anchor="center")
        except NameError:
            pass

        update_timer()
    else:
        pause_pomodoro()


def pause_pomodoro():
    global timer_running, stopwatch_start_time, stopwatch_accumulated_seconds
    timer_running = False
    if current_mode == "Stopwatch" and stopwatch_start_time is not None:
        stopwatch_accumulated_seconds += (datetime.now() - stopwatch_start_time).total_seconds()
        stopwatch_start_time = None
    start_btn.pack_forget()
    try:
        maximize_btn.pack_forget()
    except NameError:
        pass
    continue_btn.pack(pady=5)
    stop_btn.pack(pady=5)
    if current_mode in ["Short Break", "Long Break"]:
        try:
            skip_btn.pack_forget()
            skip_btn.pack(pady=4)
        except NameError:
            pass


def continue_pomodoro():
    global timer_running, stopwatch_start_time
    timer_running = True
    # Re-start stopwatch tracking on continue
    if current_mode == "Stopwatch":
        stopwatch_start_time = datetime.now()
    continue_btn.pack_forget()
    stop_btn.pack_forget()
    start_btn.config(text="Pause", command=pause_pomodoro, bootstyle="warning")
    start_btn.pack(pady=5)
    try:
        maximize_btn.pack(side="left", padx=(5, 0), anchor="center")
    except NameError:
        pass
    if current_mode in ["Short Break", "Long Break"]:
        try:
            skip_btn.pack_forget()
            skip_btn.pack(pady=4)
        except NameError:
            pass
    update_timer()


def stop_pomodoro():
    global timer_running, stopwatch_start_time, pomodoro_time, stopwatch_accumulated_seconds
    timer_running = False

    # Log time spent depending on mode
    if current_mode == "Stopwatch":
        if stopwatch_start_time is not None:
            stopwatch_accumulated_seconds += (datetime.now() - stopwatch_start_time).total_seconds()
            stopwatch_start_time = None
        log_session("Stopwatch", stopwatch_accumulated_seconds)
        stopwatch_accumulated_seconds = 0
    elif current_mode == "Work":
        # Calculate how much work time was actually spent
        spent = settings["work_time"] * 60 - pomodoro_time
        log_session("Work", spent)

    try:
        continue_btn.pack_forget()
        stop_btn.pack_forget()
        skip_btn.pack_forget()
        maximize_btn.pack_forget()
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
        stop_btn.pack_forget()
        skip_btn.pack_forget()
        maximize_btn.pack_forget()
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
                timer_running = False

                if is_maximized:
                    minimize_timer()

                if settings["sound_enabled"]:
                    if sys.platform == "linux":
                        sound_file = get_resource_path("complete.oga")
                        os.system(f'paplay "{sound_file}" 2>/dev/null &')
                    else:
                        root.bell()

                start_btn.config(
                    text="Start", command=start_pomodoro, bootstyle="primary"
                )

                # Re-enable mode toggle buttons on completion
                for child in mode_frame.winfo_children():
                    child.configure(state="normal")

                if current_mode == "Work":
                    completed_pomodoros += 1
                    log_session("Work", settings["work_time"] * 60)
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


def maximize_timer():
    global is_maximized, is_updating_layout
    is_updating_layout = True
    try:
        if not is_maximized:
            try:
                geom = root.geometry()
                size = geom.split("+")[0]
                w, h = map(int, size.split("x"))
                w_base = w - settings.get("todo_sidebar_width", 250) if settings.get("todo_sidebar_visible", False) else w
                settings["window_width"] = w_base
                settings["window_height"] = h
                save_settings()
            except Exception as e:
                print(f"Error saving window size: {e}")

        is_maximized = True

        # Hide regular layout controls
        mode_frame.pack_forget()
        mode_label.pack_forget()
        start_btn.pack_forget()
        continue_btn.pack_forget()
        stop_btn.pack_forget()
        try:
            skip_btn.pack_forget()
        except NameError:
            pass
        try:
            maximize_btn.pack_forget()
        except NameError:
            pass
        if todo_container is not None and paned is not None:
            try:
                paned.forget(todo_container)
            except Exception:
                pass
        if sash_toggle_btn is not None:
            try:
                sash_toggle_btn.pack_forget()
            except Exception:
                pass

        # Hide menu bar
        root.config(menu="")

        # Resize window to a compact centered widget layout
        width = settings.get("maximized_window_width", 240)
        height = settings.get("maximized_window_height", 80)
        root.geometry(f"{width}x{height}")

        # Repack timer_frame with top padding to center beautifully
        timer_frame.pack_forget()
        timer_frame.pack(pady=(15, 5))

        # Show minimize button next to the timer
        minimize_btn.pack(side="left", padx=(5, 0), anchor="center")
    finally:
        root.after(100, reset_updating_layout)


def minimize_timer():
    global is_maximized, is_updating_layout
    is_updating_layout = True
    try:
        if is_maximized:
            try:
                geom = root.geometry()
                size = geom.split("+")[0]
                w, h = map(int, size.split("x"))
                settings["maximized_window_width"] = w
                settings["maximized_window_height"] = h
                save_settings()
            except Exception as e:
                print(f"Error saving maximized window size: {e}")

        is_maximized = False

        # Hide minimize button next to the timer
        minimize_btn.pack_forget()

        # Restore menu bar
        root.config(menu=menu_bar)

        # Restore saved window geometry
        width = settings.get("window_width", 290)
        if settings.get("todo_sidebar_visible", False):
            width += settings.get("todo_sidebar_width", 250)
        height = settings.get("window_height", 290)
        root.geometry(f"{width}x{height}")

        # Restore standard timer_frame packing
        timer_frame.pack_forget()
        timer_frame.pack(pady=0)

        # Pack core widgets back
        mode_frame.pack(pady=(12, 0))
        mode_label.pack(pady=(8, 0))

        if settings.get("todo_sidebar_visible", False) and paned is not None:
            if str(todo_container) not in paned.panes():
                paned.add(todo_container, weight=1)
            root.update_idletasks()
            try:
                paned.sashpos(0, settings.get("window_width", 290))
            except Exception:
                pass

        if sash_toggle_btn is not None:
            try:
                sash_toggle_btn.pack(side="right", fill="y")
            except Exception:
                pass

        # Restore controls based on whether the timer is running
        if timer_running:
            start_btn.pack(pady=4)
            try:
                maximize_btn.pack(side="left", padx=(5, 0), anchor="center")
            except NameError:
                pass
        else:
            start_btn.pack(pady=4)
    finally:
        root.after(100, reset_updating_layout)


def create_app():
    global root, mode_label, timer_label, start_btn, continue_btn, stop_btn, skip_btn, mode_frame, mode_var, maximize_btn, minimize_btn, menu_bar, timer_frame
    global main_container, todo_container, todo_entry, todo_list_frame, todo_list_canvas, sash_toggle_btn, editing_todo_ids, paned
    root = tb.Window(themename="superhero")
    apply_window_icon(root)
    root.title("Pomodoro")
    
    # Force todo list to be invisible at startup
    settings["todo_sidebar_visible"] = False
    
    sidebar_visible = False
    sidebar_w = settings.get("todo_sidebar_width", 250)
    if settings.get("is_maximized_state", False):
        width = settings.get("maximized_window_width", 240)
        height = settings.get("maximized_window_height", 80)
    else:
        width = settings.get("window_width", 290)
        height = settings.get("window_height", 290)
    root.geometry(f"{width}x{height}")
    root.attributes("-topmost", True)

    paned = tb.Panedwindow(root, orient="horizontal")
    paned.pack(fill="both", expand=True)

    main_container = tb.Frame(paned)
    paned.add(main_container, weight=0)

    # Left pane layout: timer_controls_frame for standard centered controls, sash_toggle_btn on the right edge
    timer_controls_frame = tb.Frame(main_container)
    timer_controls_frame.pack(side="left", fill="both", expand=True)

    sash_toggle_btn = SashToggleButton(
        main_container,
        command=toggle_todo_sidebar
    )
    sash_toggle_btn.pack(side="right", fill="y")

    # Added toggle mode frame to main UI
    mode_var = tk.StringVar(value=settings.get("timer_mode", "Pomodoro"))
    mode_frame = tb.Frame(timer_controls_frame)
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

    mode_label = tb.Label(timer_controls_frame, text="", font=(FONT_FAMILY, 12, "bold"))
    mode_label.pack(pady=(8, 0))

    timer_frame = tb.Frame(timer_controls_frame)
    timer_frame.pack(pady=0)

    timer_label = tb.Label(
        timer_frame, text="", font=(FONT_FAMILY, settings["label_font_size"], "bold")
    )
    timer_label.pack(side="left")

    start_btn = tb.Button(
        timer_controls_frame, text="Start", command=start_pomodoro, bootstyle="primary", width=12
    )
    start_btn.pack(pady=4)

    continue_btn = tb.Button(
        timer_controls_frame, text="Continue", command=continue_pomodoro, bootstyle="success", width=12
    )
    stop_btn = tb.Button(
        timer_controls_frame, text="Stop", command=stop_pomodoro, bootstyle="danger", width=12
    )
    skip_btn = tb.Button(
        timer_controls_frame, text="Skip Break", command=skip_break, bootstyle="secondary", width=12
    )

    maximize_btn = tb.Label(
        timer_frame, text="⛶", cursor="hand2", font=(FONT_FAMILY, 18), bootstyle="info"
    )
    maximize_btn.bind("<Button-1>", lambda e: maximize_timer())
    minimize_btn = tb.Label(
        timer_frame, text="⤡", cursor="hand2", font=(FONT_FAMILY, 18), bootstyle="info"
    )
    minimize_btn.bind("<Button-1>", lambda e: minimize_timer())

    # Todo UI layout
    editing_todo_ids = set()
    todo_container = tb.Frame(paned)
    todo_container.bind("<Configure>", on_pane_configure)
    main_container.bind("<Configure>", on_pane_configure)
    
    todo_title = tb.Label(todo_container, text="📝 Todos", font=(FONT_FAMILY, 12, "bold"), bootstyle="info")
    todo_title.pack(anchor="w", pady=(5, 5), padx=5)
    
    input_frame = tb.Frame(todo_container)
    input_frame.pack(fill="x", pady=2, padx=5)
    
    todo_entry = tb.Entry(input_frame, font=(FONT_FAMILY, 10), bootstyle="secondary")
    todo_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
    todo_entry.bind("<Return>", lambda e: add_todo_item())
    
    add_btn = tb.Button(input_frame, text="Add", command=add_todo_item, bootstyle="info", width=5)
    add_btn.pack(side="right")
    
    list_container = tb.Frame(todo_container)
    list_container.pack(fill="both", expand=True, pady=5)
    
    bg_color = tb.Style().colors.bg
    todo_list_canvas = tk.Canvas(list_container, borderwidth=0, highlightthickness=0, bg=bg_color)
    todo_scrollbar = tb.Scrollbar(list_container, orient="vertical", command=todo_list_canvas.yview)
    
    todo_list_frame = tb.Frame(todo_list_canvas)
    canvas_window = todo_list_canvas.create_window((0, 0), window=todo_list_frame, anchor="nw", width=220)
    
    def on_canvas_configure(event):
        todo_list_canvas.itemconfig(canvas_window, width=event.width)
        
    todo_list_canvas.bind("<Configure>", on_canvas_configure)
    
    todo_list_frame.bind(
        "<Configure>",
        lambda e: todo_list_canvas.configure(
            scrollregion=todo_list_canvas.bbox("all")
        )
    )
    
    todo_list_canvas.configure(yscrollcommand=todo_scrollbar.set)
    todo_list_canvas.pack(side="left", fill="both", expand=True)
    todo_scrollbar.pack(side="right", fill="y")
    
    def _on_mousewheel(event):
        if sys.platform == "win32":
            todo_list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif sys.platform == "darwin":
            todo_list_canvas.yview_scroll(int(-1 * event.delta), "units")
        else:
            if event.num == 4:
                todo_list_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                todo_list_canvas.yview_scroll(1, "units")
                
    def bind_mousewheel(event):
        todo_list_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        if sys.platform == "linux":
            todo_list_canvas.bind_all("<Button-4>", _on_mousewheel)
            todo_list_canvas.bind_all("<Button-5>", _on_mousewheel)

    def unbind_mousewheel(event):
        todo_list_canvas.unbind_all("<MouseWheel>")
        if sys.platform == "linux":
            todo_list_canvas.unbind_all("<Button-4>")
            todo_list_canvas.unbind_all("<Button-5>")

    todo_list_canvas.bind("<Enter>", bind_mousewheel)
    todo_list_canvas.bind("<Leave>", unbind_mousewheel)
    
    render_todos()
    update_todo_layout()

    def increase_font():
        settings["label_font_size"] = min(settings["label_font_size"] + 2, 72)
        timer_label.configure(font=(FONT_FAMILY, settings["label_font_size"], "bold"))
        save_settings()

    def decrease_font():
        settings["label_font_size"] = max(settings["label_font_size"] - 2, 8)
        timer_label.configure(font=(FONT_FAMILY, settings["label_font_size"], "bold"))
        save_settings()

    def open_report_dialog():
        today = date.today().isoformat()
        history = load_history()
        today_sessions = [s for s in history if s.get("date") == today]

        work_sessions = [s for s in today_sessions if s["type"] == "Work"]
        stopwatch_sessions = [s for s in today_sessions if s["type"] == "Stopwatch"]

        total_work_secs = sum(s["duration_seconds"] for s in work_sessions)
        total_sw_secs = sum(s["duration_seconds"] for s in stopwatch_sessions)
        total_focus_secs = total_work_secs + total_sw_secs

        num_work = len(work_sessions)

        def fmt_time(secs):
            h, rem = divmod(int(secs), 3600)
            m, s = divmod(rem, 60)
            if h > 0:
                return f"{h}h {m}m {s}s"
            elif m > 0:
                return f"{m}m {s}s"
            return f"{s}s"

        report_win = tb.Toplevel(root)
        apply_window_icon(report_win)
        report_win.title("Daily Report")
        report_win.geometry("300x260")
        report_win.attributes("-topmost", True)
        report_win.resizable(False, False)

        tb.Label(
            report_win,
            text="📊 Daily Report",
            font=(FONT_FAMILY, 14, "bold"),
            bootstyle="primary",
        ).pack(pady=(16, 4))

        tb.Label(
            report_win,
            text=today,
            font=(FONT_FAMILY, 9),
            bootstyle="secondary",
            foreground="white",
        ).pack(pady=(0, 12))

        # Stats frame
        stats_frame = tb.Frame(report_win, padding=10)
        stats_frame.pack(fill="x", padx=20)

        def stat_row(label, value, style="default"):
            row = tb.Frame(stats_frame)
            row.pack(fill="x", pady=4)
            tb.Label(row, text=label, font=(FONT_FAMILY, 10), foreground="white").pack(
                side="left"
            )
            tb.Label(
                row, text=value, font=(FONT_FAMILY, 10, "bold"), foreground="white"
            ).pack(side="right")

        tb.Separator(stats_frame).pack(fill="x", pady=(0, 8))
        stat_row("🕐 Total Focus Time", fmt_time(total_focus_secs), "info")
        total_sessions = len(today_sessions)
        stat_row("💼 Total Sessions", str(total_sessions), "primary")
        stat_row("⏱  Pomodoro Time", fmt_time(total_work_secs), "primary")
        stat_row("⏩ Stopwatch Time", fmt_time(total_sw_secs), "success")

        if not today_sessions:
            tb.Label(
                report_win,
                text="No sessions recorded today yet.",
                font=(FONT_FAMILY, 9),
                bootstyle="secondary",
            ).pack(pady=10)

    menu_bar = tk.Menu(root, tearoff=0)
    root.config(menu=menu_bar)

    menu_bar.add_command(label="🔧", command=open_settings_dialog)
    menu_bar.add_command(label="📋", command=toggle_todo_sidebar)
    menu_bar.add_command(label="📊", command=open_report_dialog)
    menu_bar.add_command(label="➕", command=increase_font)
    menu_bar.add_command(label="➖", command=decrease_font)

    root.bind("<FocusIn>", on_focus_in)
    root.bind("<FocusOut>", on_focus_out)
    root.attributes("-alpha", settings["unfocus_transparency"])

    if settings.get("timer_mode") == "Stopwatch":
        set_mode("Stopwatch")
    else:
        set_mode("Work")

    if settings.get("is_maximized_state", False):
        maximize_timer()

    def on_close():
        try:
            settings["is_maximized_state"] = is_maximized
            geom = root.geometry()
            size = geom.split("+")[0]
            w, h = map(int, size.split("x"))
            if is_maximized:
                settings["maximized_window_width"] = w
                settings["maximized_window_height"] = h
            else:
                if not settings.get("todo_sidebar_visible", False):
                    settings["window_width"] = w
                settings["window_height"] = h
            save_settings()
        except Exception as e:
            print(f"Error saving window size on close: {e}")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.after(150, reset_updating_layout)
    root.mainloop()


if __name__ == "__main__":
    create_app()
