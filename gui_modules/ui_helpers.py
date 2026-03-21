import customtkinter as ctk

def sidebar_section(parent, title):
    if title:
        ctk.CTkLabel(parent, text="─" * 30, text_color="gray40").pack(padx=20, pady=(10, 0))
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(4, 6))

def card(parent, title):
    f = ctk.CTkFrame(parent, corner_radius=8)
    f.pack(fill="x", padx=8, pady=6)
    ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(10, 2))
    return f
