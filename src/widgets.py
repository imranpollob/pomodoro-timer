import tkinter as tk
import ttkbootstrap as tb

FONT_FAMILY = "Helvetica"


class SashToggleButton(tk.Canvas):
    """A custom toggle button used to show or hide the sidebar."""

    def __init__(self, master, command=None, bg_normal=None, bg_hover=None, **kwargs):
        """Initializes the SashToggleButton with customizable colors and a command callback."""
        style = tb.Style()
        self.bg_normal = bg_normal if bg_normal else style.colors.secondary
        self.bg_hover = bg_hover if bg_hover else style.colors.info
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
        """Handles mouse enter event by changing the background color to hover state."""
        self.configure(bg=self.bg_hover)

    def on_leave(self, event):
        """Handles mouse leave event by reverting the background color to normal state."""
        self.configure(bg=self.bg_normal)

    def on_click(self, event):
        """Executes the assigned command when the button is clicked."""
        if self.command:
            self.command()

    def set_text(self, text):
        """Sets the text of the button and redraws it."""
        if "\n" in text:
            text = text.replace("\n", "")
        self.text_val = text.upper()
        self.draw()

    def configure(self, cnf=None, **kwargs):
        """Overrides configure to handle text and bootstyle parameters."""
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
        """Draws the text vertically on the canvas."""
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

