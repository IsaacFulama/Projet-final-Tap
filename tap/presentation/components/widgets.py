import customtkinter as ctk

from tap.config.theme import C


class StatCard(ctk.CTkFrame):
    def __init__(self, master, icon: str, label: str, color: str, **kwargs):
        super().__init__(master, fg_color=C["bg_card"], corner_radius=12,
                         border_width=1, border_color=C["border"], **kwargs)
        ctk.CTkFrame(self, height=3, fg_color=color, corner_radius=3).pack(fill="x")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)
        self.lbl_value = ctk.CTkLabel(inner, text="0",
                                      font=ctk.CTkFont(family="Georgia", size=28, weight="bold"),
                                      text_color=color)
        self.lbl_value.pack(anchor="w")
        self.lbl_sub = ctk.CTkLabel(inner, text="—",
                                     font=ctk.CTkFont(size=10),
                                     text_color=C["text_lo"])
        self.lbl_sub.pack(anchor="w")
        bottom = ctk.CTkFrame(inner, fg_color="transparent")
        bottom.pack(fill="x", anchor="w", pady=(4, 0))
        ctk.CTkLabel(bottom, text=icon, font=ctk.CTkFont(size=12),
                     text_color=C["text_lo"]).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(bottom, text=label, font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(side="left")

    def update(self, value, sub: str = ""):
        self.lbl_value.configure(text=str(value))
        self.lbl_sub.configure(text=sub)


class SidebarButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        defaults = dict(
            height=42, corner_radius=8, font=ctk.CTkFont(size=13), anchor="w",
            fg_color=C["bg_section"], hover_color=C["border"],
            text_color=C["text_hi"], border_spacing=12,
        )
        defaults.update(kwargs)
        super().__init__(master, **defaults)
