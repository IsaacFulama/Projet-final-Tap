import customtkinter as ctk

from tap.presentation.dialogs.login import LoginDialog
from tap.presentation.views.main_window import AppGestionLoyers

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def launch_app():
    login_dialog = LoginDialog(None)
    login_dialog.mainloop()

    if login_dialog.authenticated:
        try:
            login_dialog.destroy()
        except Exception:
            pass
        app = AppGestionLoyers()
        app.mainloop()
