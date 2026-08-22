from __future__ import annotations

import json
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .analyzer import detect_profile
from .pipeline import (
    analyze,
    create_project,
    export_csv,
    extract,
    import_csv,
    inject,
    latest_build,
    list_entries,
    launchable_executable,
    restore_latest_build,
    update_translation,
    validate,
)

SETTINGS_PATH = Path(os.getenv("LOCALAPPDATA", Path.home() / ".config")) / "unity-translator" / "settings.json"
APP_ICON = Path(__file__).parent / "assets" / "app-icon.ico"
DESIGN_COLORS = {
    "background": "#0F1115",
    "panel": "#171A21",
    "panel_alt": "#1E222B",
    "border": "#2B313C",
    "border_subtle": "#232830",
    "text": "#F3F4F6",
    "text_secondary": "#9CA3AF",
    "muted": "#6B7280",
    "accent": "#38BDF8",
    "accent_dim": "#0EA5E9",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error": "#EF4444",
}

TUTORIAL_STEPS = (
    {
        "title": "1. Seleccioná el juego",
        "body": "Elegí la carpeta que contiene el ejecutable y su carpeta *_Data. Analizar solo inspecciona: no modifica archivos.",
        "where": "En la ventana principal: Juego → Elegir… → 1 Analizar",
    },
    {
        "title": "2. Creá el proyecto y extraé",
        "body": "Elegí un perfil compatible, creá una carpeta de proyecto y extraé los textos al Translation IR.",
        "where": "En la ventana principal: 2 Crear proyecto → 3 Extraer",
    },
    {
        "title": "3. Traducí y validá",
        "body": "Usá el Editor o exportá el CSV. Después importá y validá IDs, placeholders, tags y hashes.",
        "where": "En la ventana principal: 4 Abrir editor → 7 Validar",
    },
    {
        "title": "4. Inyectá sobre una copia",
        "body": "Generar crea un backup y una copia separada. Abrí la carpeta, ejecutá el juego para probarlo o restaurá ese build sin tocar el original.",
        "where": "En la ventana principal: 8 Generar copia → Resultado",
    },
)

STATUS_FILTERS = {
    "Todas": "all",
    "Sin traducir": "untranslated",
    "Traducidas": "translated",
    "Vacías intencionales": "intentionally_empty",
}
STATUS_LABELS = {value: label for label, value in STATUS_FILTERS.items() if value != "all"}


def _required_path(value: str, label: str) -> str:
    """Validate a path field before dispatching work to the pipeline."""
    normalized = value.strip()
    if not normalized or normalized in {".", "./", ".\\"}:
        raise ValueError(f"Seleccioná una ruta válida para {label}; no puede estar vacía ni ser '.'")
    return normalized


def open_folder(path: str | Path, launcher: Callable[[str], object] | None = None) -> Path:
    target = Path(path).resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"No se encontró la carpeta: {target}")
    system_launcher = launcher or os.startfile
    system_launcher(str(target))
    return target


def start_executable(
    path: str | Path,
    launcher: Callable[..., object] | None = None,
) -> Path:
    executable = Path(path).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"No se encontró el ejecutable: {executable}")
    process_launcher = launcher or subprocess.Popen
    process_launcher([str(executable)], cwd=str(executable.parent))
    return executable


def load_tutorial_preference(path: Path = SETTINGS_PATH) -> bool:
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return True
    return bool(settings.get("show_tutorial_on_startup", True))


def save_tutorial_preference(path: Path = SETTINGS_PATH, show_on_startup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"show_tutorial_on_startup": show_on_startup}, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def format_analysis(result: dict) -> str:
    if not result.get("is_unity"):
        return f"No se detectó un juego Unity: {result.get('reason', 'motivo desconocido')}"
    version = result.get("unity_version", "unknown")
    unity_label = f"Unity {version} detectado" if version != "unknown" else "Unity detectado (versión desconocida)"
    return "\n".join(
        [
            unity_label,
            f"Ejecución: {result.get('runtime', 'desconocida')}",
            f"StreamingAssets: {'sí' if result.get('streaming_assets') else 'no'}",
            f"Assets detectados: {len(result.get('asset_files', []))}",
            f"Compatibilidad: {result.get('compatibility', 'desconocida')}",
        ]
    )


def format_validation(result: dict) -> str:
    return (
        f"Revisadas: {result['checked']} | Errores: {result['errors']} | "
        f"Advertencias: {result['warnings']} | Pendientes: {result['pending']}"
    )


def filter_entries(entries: list[dict], query: str, status: str = "all") -> list[dict]:
    needle = query.casefold().strip()
    filtered = []
    for entry in entries:
        if status != "all" and entry["status"] != status:
            continue
        haystack = "\n".join(
            (entry["id"], entry["original_text"], entry.get("translated_text", ""))
        ).casefold()
        if needle and needle not in haystack:
            continue
        filtered.append(entry)
    return filtered


class TutorialDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.page = 0
        self.show_on_startup = tk.BooleanVar(value=load_tutorial_preference())
        self.window = tk.Toplevel(parent)
        self.window.title("Primeros pasos")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.window, padding=24)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        self.counter = ttk.Label(frame, style="Secondary.TLabel")
        self.counter.grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=len(TUTORIAL_STEPS))
        self.progress.grid(row=1, column=0, sticky="ew", pady=(8, 18))
        self.title = ttk.Label(frame, font=("Segoe UI", 17, "bold"))
        self.title.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.body = ttk.Label(frame, wraplength=500, justify="left")
        self.body.grid(row=3, column=0, sticky="w", pady=(0, 18))
        ttk.Separator(frame).grid(row=4, column=0, sticky="ew", pady=(0, 14))
        self.where = ttk.Label(frame, wraplength=500, style="Secondary.TLabel")
        self.where.grid(row=5, column=0, sticky="w", pady=(0, 18))
        ttk.Checkbutton(
            frame,
            text="Mostrar tutorial al iniciar",
            variable=self.show_on_startup,
        ).grid(row=6, column=0, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, sticky="ew", pady=(20, 0))
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Omitir", command=self.skip).grid(row=0, column=0)
        self.previous = ttk.Button(buttons, text="Anterior", command=self._previous)
        self.previous.grid(row=0, column=2, padx=(8, 0))
        self.next = ttk.Button(buttons, text="Siguiente", command=self._next, style="Accent.TButton")
        self.next.grid(row=0, column=3, padx=(8, 0))
        self._render()
        self.window.grab_set()
        self.window.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.window.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.window.winfo_height()) // 2)
        self.window.geometry(f"+{x}+{y}")

    def _render(self) -> None:
        step = TUTORIAL_STEPS[self.page]
        self.counter.configure(text=f"Paso {self.page + 1} de {len(TUTORIAL_STEPS)}")
        self.progress.configure(value=self.page + 1)
        self.title.configure(text=step["title"])
        self.body.configure(text=step["body"])
        self.where.configure(text=step["where"])
        self.previous.configure(state="normal" if self.page else "disabled")
        self.next.configure(text="Listo" if self.page == len(TUTORIAL_STEPS) - 1 else "Siguiente")

    def _previous(self) -> None:
        if self.page:
            self.page -= 1
            self._render()

    def _next(self) -> None:
        if self.page == len(TUTORIAL_STEPS) - 1:
            self.close()
            return
        self.page += 1
        self._render()

    def skip(self) -> None:
        self.show_on_startup.set(False)
        self.close()

    def close(self) -> None:
        save_tutorial_preference(SETTINGS_PATH, self.show_on_startup.get())
        self.window.destroy()


class EditorWindow:
    def __init__(self, parent: tk.Misc, project_path: str) -> None:
        if not project_path:
            raise ValueError("Seleccioná un proyecto antes de abrir el editor")
        self.project_path = project_path
        self.entries: list[dict] = []
        self.window = tk.Toplevel(parent)
        self.window.title("Editor de traducciones")
        self.window.minsize(960, 620)
        self.query = tk.StringVar()
        self.status = tk.StringVar(value="Todas")
        self.intentionally_empty = tk.BooleanVar()
        self._build()
        self.refresh()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        filters = ttk.Frame(frame)
        filters.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text="Buscar:").grid(row=0, column=0, padx=(0, 6))
        search = ttk.Entry(filters, textvariable=self.query)
        search.grid(row=0, column=1, sticky="ew")
        search.bind("<KeyRelease>", lambda _event: self._render())
        ttk.Label(filters, text="Estado:").grid(row=0, column=2, padx=(12, 6))
        status = ttk.Combobox(
            filters,
            textvariable=self.status,
            values=tuple(STATUS_FILTERS),
            state="readonly",
            width=20,
        )
        status.grid(row=0, column=3)
        status.bind("<<ComboboxSelected>>", lambda _event: self._render())
        ttk.Button(filters, text="Actualizar", command=self.refresh).grid(row=0, column=4, padx=(8, 0))

        self.tree = ttk.Treeview(
            frame,
            columns=("original", "translation", "status"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("original", text="Original")
        self.tree.heading("translation", text="Traducción")
        self.tree.heading("status", text="Estado")
        self.tree.column("original", width=360)
        self.tree.column("translation", width=360)
        self.tree.column("status", width=130, stretch=False)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._select_entry)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        editor = ttk.LabelFrame(frame, text="Traducción seleccionada", padding=10)
        editor.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        editor.columnconfigure(0, weight=1)
        text_options = {
            "height": 3,
            "wrap": "word",
            "background": DESIGN_COLORS["background"],
            "foreground": DESIGN_COLORS["text_secondary"],
            "insertbackground": DESIGN_COLORS["accent"],
            "selectbackground": "#164E63",
            "selectforeground": DESIGN_COLORS["text"],
            "relief": "flat",
            "highlightthickness": 1,
            "highlightbackground": DESIGN_COLORS["border"],
            "highlightcolor": DESIGN_COLORS["accent"],
        }
        self.original = tk.Text(editor, state="disabled", **text_options)
        self.original.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.translation = tk.Text(editor, **text_options)
        self.translation.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(
            editor,
            text="Vacío intencional",
            variable=self.intentionally_empty,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Button(editor, text="Guardar traducción", command=self.save).grid(
            row=2, column=2, sticky="e", pady=(8, 0)
        )

    def refresh(self) -> None:
        self.entries = list_entries(self.project_path)
        self._render()

    def _render(self) -> None:
        selected = self.tree.selection()
        selected_id = selected[0] if selected else None
        self.tree.delete(*self.tree.get_children())
        for entry in filter_entries(self.entries, self.query.get(), STATUS_FILTERS[self.status.get()]):
            self.tree.insert(
                "",
                "end",
                iid=entry["id"],
                values=(
                    entry["original_text"],
                    entry["translated_text"],
                    STATUS_LABELS.get(entry["status"], entry["status"]),
                ),
            )
        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)

    def _select_entry(self, _event: tk.Event | None = None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        entry = next(entry for entry in self.entries if entry["id"] == selected[0])
        self.original.configure(state="normal")
        self.original.delete("1.0", "end")
        self.original.insert("1.0", entry["original_text"])
        self.original.configure(state="disabled")
        self.translation.delete("1.0", "end")
        self.translation.insert("1.0", entry["translated_text"])
        self.intentionally_empty.set(entry["status"] == "intentionally_empty")

    def save(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Sin selección", "Seleccioná una fila de traducción")
            return
        entry_id = selected[0]
        try:
            update_translation(
                self.project_path,
                entry_id,
                self.translation.get("1.0", "end-1c"),
                intentionally_empty=self.intentionally_empty.get(),
            )
            self.refresh()
            if self.tree.exists(entry_id):
                self.tree.selection_set(entry_id)
                self.tree.see(entry_id)
        except Exception as error:
            messagebox.showerror("No se pudo guardar", str(error))


class DesktopApp:
    """Thin Tk UI. All translation behavior remains in the pipeline module."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Unity Translator")
        if APP_ICON.is_file():
            try:
                self.root.iconbitmap(default=str(APP_ICON))
            except tk.TclError:
                pass
        self.root.minsize(900, 680)
        self.root.geometry("980x760")
        self._configure_styles()
        self.game = tk.StringVar()
        self.project = tk.StringVar()
        self.profile = tk.StringVar()
        self._detected_profile: dict | None = None
        self.csv_path = tk.StringVar()
        self.build_path = tk.StringVar(value="Todavía no se generó una copia")
        self.stage_status = tk.StringVar(value="Listo")
        self._buttons: list[ttk.Button] = []
        self._build()
        self.root.bind("<F1>", lambda _event: self._show_tutorial())
        self.root.after(250, self._show_startup_tutorial)

    def _configure_styles(self) -> None:
        colors = DESIGN_COLORS
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=colors["background"], foreground=colors["text"], font=("Segoe UI", 10))
        style.configure("TFrame", background=colors["background"])
        style.configure("Panel.TFrame", background=colors["panel"])
        style.configure(
            "TLabelframe",
            background=colors["panel"],
            bordercolor=colors["border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=colors["panel"],
            foreground=colors["muted"],
            font=("Segoe UI", 9, "bold"),
        )
        style.configure("TLabel", background=colors["background"], foreground=colors["text"])
        style.configure("Panel.TLabel", background=colors["panel"], foreground=colors["text"])
        style.configure("Secondary.TLabel", background=colors["background"], foreground=colors["muted"])
        style.configure("PanelSecondary.TLabel", background=colors["panel"], foreground=colors["muted"])
        style.configure(
            "TButton",
            padding=(12, 8),
            background=colors["panel_alt"],
            foreground=colors["text_secondary"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            relief="solid",
            borderwidth=1,
        )
        style.map(
            "TButton",
            background=[("active", colors["border"]), ("pressed", colors["border_subtle"]), ("disabled", colors["panel"])],
            foreground=[("active", colors["text"]), ("disabled", colors["muted"])],
        )
        style.configure(
            "Accent.TButton",
            padding=(12, 8),
            background=colors["accent"],
            foreground="#061019",
            bordercolor=colors["accent"],
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", colors["accent_dim"]), ("pressed", colors["accent_dim"]), ("disabled", colors["panel_alt"])])
        style.configure(
            "TEntry",
            fieldbackground="#0D1014",
            foreground=colors["text_secondary"],
            insertcolor=colors["accent"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(8, 6),
        )
        style.configure("TCheckbutton", background=colors["panel"], foreground=colors["text_secondary"])
        style.map("TCheckbutton", foreground=[("active", colors["text"])])
        style.configure(
            "TCombobox",
            fieldbackground="#0D1014",
            background=colors["panel_alt"],
            foreground=colors["text_secondary"],
            arrowcolor=colors["accent"],
            bordercolor=colors["border"],
        )
        style.map("TCombobox", fieldbackground=[("readonly", "#0D1014")], foreground=[("readonly", colors["text_secondary"])])
        style.configure(
            "Treeview",
            background="#0D1014",
            fieldbackground="#0D1014",
            foreground=colors["text_secondary"],
            bordercolor=colors["border"],
            rowheight=28,
        )
        style.map("Treeview", background=[("selected", "#164E63")], foreground=[("selected", colors["text"])])
        style.configure("Treeview.Heading", background=colors["panel_alt"], foreground=colors["muted"], relief="flat", padding=(8, 7))
        style.configure("TScrollbar", background=colors["panel_alt"], troughcolor=colors["background"], arrowcolor=colors["muted"])
        style.configure("TProgressbar", troughcolor=colors["border"], background=colors["accent"], bordercolor=colors["border"], lightcolor=colors["accent"], darkcolor=colors["accent"])
        self.root.configure(background=colors["background"])

    def _build(self) -> None:
        viewport = ttk.Frame(self.root)
        viewport.pack(fill="both", expand=True)
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            viewport,
            background=DESIGN_COLORS["background"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._scroll_canvas = canvas

        frame = ttk.Frame(canvas, padding=24)
        canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw")

        def update_scroll_region(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event: tk.Event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        self.root.bind_all("<MouseWheel>", self._scroll_with_wheel, add="+")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(7, weight=1)

        header = ttk.Frame(frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Unity Translator", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Extraé, traducí y validá textos Unity completamente offline.",
            style="Secondary.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(
            header,
            text="Original protegido · Los cambios se aplican solamente a una copia.",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=(7, 0))
        ttk.Button(header, text="Ver tutorial", command=self._show_tutorial).grid(
            row=0, column=1, rowspan=3, sticky="e"
        )

        paths = ttk.LabelFrame(frame, text="Proyecto", padding=14)
        paths.grid(row=1, column=0, sticky="ew")
        paths.columnconfigure(1, weight=1)
        self._path_row(paths, 0, "Juego", self.game, self._select_game)
        self._path_row(paths, 1, "Proyecto", self.project, self._select_project)
        self._path_row(paths, 2, "Perfil", self.profile, self._select_profile)
        self._path_row(paths, 3, "CSV", self.csv_path, self._select_csv)

        actions = ttk.LabelFrame(frame, text="Flujo de trabajo", padding=14)
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure(0, weight=1)

        # Phase 1: Setup and Analysis
        phase1 = ttk.Frame(actions, style="Panel.TFrame")
        phase1.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        phase1.columnconfigure(0, weight=1)
        phase1.columnconfigure(1, weight=1)
        ttk.Label(phase1, text="1. Preparación", style="Panel.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        button_analyze = ttk.Button(phase1, text="Analizar", command=self._analyze)
        button_analyze.grid(row=1, column=0, padx=(0, 4), sticky="ew")
        self._buttons.append(button_analyze)
        button_create = ttk.Button(phase1, text="Crear proyecto", command=self._create_project)
        button_create.grid(row=1, column=1, padx=(4, 0), sticky="ew")
        self._buttons.append(button_create)

        # Phase 2: Extraction and Export
        phase2 = ttk.Frame(actions, style="Panel.TFrame")
        phase2.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        phase2.columnconfigure(0, weight=1)
        phase2.columnconfigure(1, weight=1)
        ttk.Label(phase2, text="2. Extracción", style="Panel.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        button_extract = ttk.Button(phase2, text="Extraer textos", command=self._extract)
        button_extract.grid(row=1, column=0, padx=(0, 4), sticky="ew")
        self._buttons.append(button_extract)
        button_export = ttk.Button(phase2, text="Exportar CSV", command=self._export)
        button_export.grid(row=1, column=1, padx=(4, 0), sticky="ew")
        self._buttons.append(button_export)

        # Phase 3: Translation and Validation
        phase3 = ttk.Frame(actions, style="Panel.TFrame")
        phase3.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        phase3.columnconfigure(0, weight=1)
        phase3.columnconfigure(1, weight=1)
        ttk.Label(phase3, text="3. Traducción", style="Panel.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        button_editor = ttk.Button(phase3, text="Abrir editor manual", command=self._open_editor)
        button_editor.grid(row=1, column=0, padx=(0, 4), sticky="ew")
        self._buttons.append(button_editor)
        button_import = ttk.Button(phase3, text="Importar CSV", command=self._import)
        button_import.grid(row=1, column=1, padx=(4, 0), sticky="ew")
        self._buttons.append(button_import)
        button_validate = ttk.Button(phase3, text="Validar traducciones", command=self._validate)
        button_validate.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._buttons.append(button_validate)

        # Phase 4: Generation
        phase4 = ttk.Frame(actions, style="Panel.TFrame")
        phase4.grid(row=3, column=0, sticky="ew")
        phase4.columnconfigure(0, weight=1)
        ttk.Label(phase4, text="4. Generación y prueba", style="Panel.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        button_inject = ttk.Button(phase4, text="Generar copia traducida", command=self._inject, style="Accent.TButton")
        button_inject.grid(row=1, column=0, sticky="ew")
        self._buttons.append(button_inject)

        result = ttk.LabelFrame(frame, text="Resultado: Copia traducida", padding=14)
        result.grid(row=4, column=0, sticky="ew", pady=(12, 12))
        result.columnconfigure(0, weight=1)
        ttk.Label(result, text="Ruta:", style="Panel.TLabel", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Label(result, textvariable=self.build_path, style="PanelSecondary.TLabel").grid(
            row=0, column=1, sticky="ew", padx=(0, 12)
        )
        ttk.Separator(result, orient="horizontal").grid(row=1, column=0, columnspan=4, sticky="ew", pady=8)
        ttk.Label(result, text="Acciones:", style="Panel.TLabel", font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )
        result_buttons = (
            ("📁 Abrir carpeta", self._open_build_folder),
            ("▶ Ejecutar copia", self._launch_build),
            ("🔄 Restaurar", self._restore_build),
        )
        for column, (label, callback) in enumerate(result_buttons):
            button = ttk.Button(result, text=label, command=callback)
            button.grid(row=3, column=column, padx=(0 if column == 0 else 4), sticky="ew")
            result.columnconfigure(column, weight=1)
            self._buttons.append(button)

        status_header = ttk.Frame(frame)
        status_header.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        status_header.columnconfigure(0, weight=1)
        ttk.Label(status_header, text="Registro de actividad", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(status_header, textvariable=self.stage_status, style="Secondary.TLabel", font=("Segoe UI", 9)).grid(
            row=0, column=1, sticky="e"
        )
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=6, column=0, sticky="ew", pady=(8, 6))
        self.progress.grid_remove()
        self.output = tk.Text(
            frame,
            height=12,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            background="#080A0D",
            foreground=DESIGN_COLORS["text_secondary"],
            insertbackground=DESIGN_COLORS["accent"],
            selectbackground="#164E63",
            selectforeground=DESIGN_COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=DESIGN_COLORS["border"],
            highlightcolor=DESIGN_COLORS["accent"],
        )
        self.output.grid(row=7, column=0, sticky="nsew")
        self._append("Listo. Seleccioná un juego, una carpeta de proyecto y un perfil compatible.")

    def _scroll_with_wheel(self, event: tk.Event) -> None:
        if getattr(self, "_scroll_canvas", None) is not None:
            self._scroll_canvas.yview_scroll(-int(event.delta / 120), "units")

    def _path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse: Callable[[], None],
    ) -> None:
        ttk.Label(parent, text=f"{label}:", style="Panel.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Elegir…", command=browse).grid(row=row, column=2, padx=(8, 0), pady=4)

    def _select_game(self) -> None:
        if selected := filedialog.askdirectory(title="Seleccionar carpeta del juego Unity"):
            self.game.set(selected)

    def _select_project(self) -> None:
        if selected := filedialog.askdirectory(title="Seleccionar carpeta del proyecto"):
            self.project.set(selected)
            try:
                self.build_path.set(str(latest_build(selected)))
            except (OSError, ValueError):
                self.build_path.set("Todavía no se generó una copia")

    def _select_profile(self) -> None:
        if selected := filedialog.askopenfilename(title="Seleccionar perfil de extracción", filetypes=[("JSON", "*.json")]):
            self._detected_profile = None
            self.profile.set(selected)

    def _select_csv(self) -> None:
        if selected := filedialog.askopenfilename(title="Seleccionar CSV de traducción", filetypes=[("CSV", "*.csv")]):
            self.csv_path.set(selected)

    def _show_startup_tutorial(self) -> None:
        if load_tutorial_preference():
            self._show_tutorial()

    def _show_tutorial(self) -> None:
        TutorialDialog(self.root)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in self._buttons:
            button.configure(state=state)
        if busy:
            self.progress.grid()
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def _append(self, message: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", message.rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _run(self, stage: str, operation: Callable[[], str]) -> None:
        self._set_busy(True)
        self.stage_status.set(f"Ejecutando: {stage}")
        self._append(f"[{stage}] Iniciando…")

        def worker() -> None:
            try:
                result = operation()
            except Exception as error:
                self.root.after(0, lambda error=error: self._finish(stage, f"Error: {error}", True))
            else:
                self.root.after(0, lambda: self._finish(stage, result, False))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, stage: str, message: str, failed: bool) -> None:
        self._append(f"[{stage}] {message}")
        self._set_busy(False)
        self.stage_status.set("Error" if failed else "Completado")
        if failed:
            messagebox.showerror(f"Falló {stage}", message)

    def _analyze(self) -> None:
        def operation() -> str:
            game = _required_path(self.game.get(), "Juego")
            result = analyze(game)
            detected = detect_profile(Path(game))
            if detected:
                self.root.after(0, lambda: self._set_detected_profile(detected))
            message = format_analysis(result)
            if detected:
                message += f"\nPerfil automático: {detected['extractor']}"
            else:
                message += "\nPerfil automático: no disponible"
            return message

        self._run("Análisis", operation)

    def _set_detected_profile(self, profile: dict) -> None:
        self._detected_profile = profile
        self.profile.set(f"[Automático] {profile['extractor']}")

    def _create_project(self) -> None:
        def operation() -> str:
            game = _required_path(self.game.get(), "Juego")
            project = _required_path(self.project.get(), "Proyecto")
            profile_value = self.profile.get().strip()
            if profile_value.startswith("[Automático]") and self._detected_profile:
                profile = self._detected_profile
            elif profile_value:
                profile_path = _required_path(profile_value, "Perfil")
                profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
            else:
                profile = detect_profile(Path(game))
                if profile is None:
                    raise ValueError("No se pudo detectar un perfil compatible; seleccioná uno manualmente")
            created = create_project(game, project, profile)
            return f"Proyecto creado en {created}"

        self._run("Proyecto", operation)

    def _extract(self) -> None:
        self._run("Extracción", lambda: f"Se extrajeron {len(extract(_required_path(self.project.get(), 'Proyecto')))} cadenas")

    def _export(self) -> None:
        def operation() -> str:
            project = _required_path(self.project.get(), "Proyecto")
            target = export_csv(project, _required_path(self.csv_path.get(), "CSV"))
            return f"CSV exportado en {target}"

        self._run("CSV", operation)

    def _import(self) -> None:
        def operation() -> str:
            project = _required_path(self.project.get(), "Proyecto")
            result = import_csv(project, _required_path(self.csv_path.get(), "CSV"))
            return (
                f"Importadas: {result['imported']} | Pendientes: {result['pending']} | "
                f"Vacías intencionales: {result['intentionally_empty']}"
            )

        self._run("CSV", operation)

    def _validate(self) -> None:
        self._run("Validación", lambda: format_validation(validate(_required_path(self.project.get(), "Proyecto"))))

    def _inject(self) -> None:
        def operation() -> str:
            build = inject(_required_path(self.project.get(), "Proyecto"))
            self.root.after(0, lambda build=build: self.build_path.set(str(build)))
            return f"Copia generada y verificada en {build}"

        self._run("Copia", operation)

    def _open_build_folder(self) -> None:
        try:
            build = open_folder(latest_build(_required_path(self.project.get(), "Proyecto")))
            self.build_path.set(str(build))
            self._append(f"[Resultado] Carpeta abierta: {build}")
        except Exception as error:
            messagebox.showerror("No se pudo abrir la copia", str(error))

    def _launch_build(self) -> None:
        try:
            executable = start_executable(launchable_executable(_required_path(self.project.get(), "Proyecto")))
            self.build_path.set(str(executable.parent))
            self._append(f"[Resultado] Juego iniciado: {executable.name}")
        except Exception as error:
            messagebox.showerror("No se pudo ejecutar la copia", str(error))

    def _restore_build(self) -> None:
        try:
            project = _required_path(self.project.get(), "Proyecto")
            build = latest_build(project)
        except Exception as error:
            messagebox.showerror("No se pudo restaurar", str(error))
            return
        if not messagebox.askyesno(
            "Restaurar último build",
            "Se restaurarán dentro de la copia los archivos respaldados antes de la inyección. "
            "El juego original no se modificará. ¿Continuar?",
        ):
            return

        def operation() -> str:
            restored, destination = restore_latest_build(project)
            return f"Se restauraron {restored} archivos en {destination}"

        self._run("Restauración", operation)

    def _open_editor(self) -> None:
        try:
            EditorWindow(self.root, _required_path(self.project.get(), "Proyecto"))
        except Exception as error:
            messagebox.showerror("No se pudo abrir el editor", str(error))


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
