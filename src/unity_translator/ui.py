from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .pipeline import (
    analyze,
    create_project,
    export_csv,
    extract,
    import_csv,
    inject,
    list_entries,
    update_translation,
    validate,
)

SETTINGS_PATH = Path(os.getenv("LOCALAPPDATA", Path.home() / ".config")) / "unity-translator" / "settings.json"

TUTORIAL_STEPS = (
    {
        "title": "1. Seleccioná el juego",
        "body": "Elegí la carpeta que contiene el ejecutable y su carpeta *_Data. Analizar solo inspecciona: no modifica archivos.",
    },
    {
        "title": "2. Creá el proyecto y extraé",
        "body": "Elegí un perfil compatible, creá una carpeta de proyecto y extraé los textos al Translation IR.",
    },
    {
        "title": "3. Traducí y validá",
        "body": "Usá el Editor o exportá el CSV. Después importá y validá IDs, placeholders, tags y hashes.",
    },
    {
        "title": "4. Inyectá sobre una copia",
        "body": "Inyectar crea backup y un build separado. Probá esa copia; el juego original nunca se sobrescribe.",
    },
)


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
        return f"Unity game not detected: {result.get('reason', 'unknown reason')}"
    return "\n".join(
        [
            f"Unity {result.get('unity_version', 'unknown')} detected",
            f"Runtime: {result.get('runtime', 'unknown')}",
            f"StreamingAssets: {'yes' if result.get('streaming_assets') else 'no'}",
            f"Assets: {len(result.get('asset_files', []))}",
            f"Compatibility: {result.get('compatibility', 'unknown')}",
        ]
    )


def format_validation(result: dict) -> str:
    return (
        f"Checked: {result['checked']} | Errors: {result['errors']} | "
        f"Warnings: {result['warnings']} | Pending: {result['pending']}"
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
        self.dont_show_again = tk.BooleanVar(value=not load_tutorial_preference())
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
        self.title = ttk.Label(frame, font=("Segoe UI", 17, "bold"))
        self.title.grid(row=1, column=0, sticky="w", pady=(8, 8))
        self.body = ttk.Label(frame, wraplength=500, justify="left")
        self.body.grid(row=2, column=0, sticky="w", pady=(0, 22))
        ttk.Checkbutton(
            frame,
            text="No volver a mostrar al iniciar",
            variable=self.dont_show_again,
        ).grid(row=3, column=0, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew", pady=(20, 0))
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Omitir", command=self.close).grid(row=0, column=0)
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
        self.title.configure(text=step["title"])
        self.body.configure(text=step["body"])
        self.previous.configure(state="normal" if self.page else "disabled")
        self.next.configure(text="Empezar" if self.page == len(TUTORIAL_STEPS) - 1 else "Siguiente")

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

    def close(self) -> None:
        save_tutorial_preference(SETTINGS_PATH, not self.dont_show_again.get())
        self.window.destroy()


class EditorWindow:
    def __init__(self, parent: tk.Misc, project_path: str) -> None:
        if not project_path:
            raise ValueError("Select a project before opening the editor")
        self.project_path = project_path
        self.entries: list[dict] = []
        self.window = tk.Toplevel(parent)
        self.window.title("Editor de traducciones")
        self.window.minsize(960, 620)
        self.query = tk.StringVar()
        self.status = tk.StringVar(value="all")
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
            values=("all", "untranslated", "translated", "intentionally_empty"),
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
        self.original = tk.Text(editor, height=3, wrap="word", state="disabled")
        self.original.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.translation = tk.Text(editor, height=3, wrap="word")
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
        for entry in filter_entries(self.entries, self.query.get(), self.status.get()):
            self.tree.insert(
                "",
                "end",
                iid=entry["id"],
                values=(entry["original_text"], entry["translated_text"], entry["status"]),
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
        self.root.minsize(860, 620)
        self.root.geometry("940x680")
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TButton", padding=(10, 7))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Secondary.TLabel", foreground="#5f6368")
        self.game = tk.StringVar()
        self.project = tk.StringVar()
        self.profile = tk.StringVar()
        self.csv_path = tk.StringVar()
        self.stage_status = tk.StringVar(value="Listo")
        self._buttons: list[ttk.Button] = []
        self._build()
        self.root.after(250, self._show_startup_tutorial)

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)

        header = ttk.Frame(frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Unity Translator", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Pipeline offline para extraer, traducir y generar una copia segura del juego.",
            style="Secondary.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Button(header, text="Ver tutorial", command=self._show_tutorial).grid(
            row=0, column=1, rowspan=2, sticky="e"
        )

        paths = ttk.LabelFrame(frame, text="Proyecto", padding=14)
        paths.grid(row=1, column=0, sticky="ew")
        paths.columnconfigure(1, weight=1)
        self._path_row(paths, 0, "Juego", self.game, self._select_game)
        self._path_row(paths, 1, "Proyecto", self.project, self._select_project)
        self._path_row(paths, 2, "Perfil", self.profile, self._select_profile)
        self._path_row(paths, 3, "CSV", self.csv_path, self._select_csv)

        actions = ttk.LabelFrame(frame, text="Flujo de trabajo", padding=12)
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 12))
        for column in range(4):
            actions.columnconfigure(column, weight=1)
        specs = [
            ("1  Analizar", self._analyze),
            ("2  Crear proyecto", self._create_project),
            ("3  Extraer", self._extract),
            ("4  Abrir editor", self._open_editor),
            ("5  Exportar CSV", self._export),
            ("6  Importar CSV", self._import),
            ("7  Validar", self._validate),
            ("8  Generar copia", self._inject),
        ]
        for index, (label, callback) in enumerate(specs):
            button = ttk.Button(
                actions,
                text=label,
                command=callback,
                style="Accent.TButton" if index in {0, 7} else "TButton",
            )
            button.grid(row=index // 4, column=index % 4, padx=4, pady=4, sticky="ew")
            self._buttons.append(button)

        status_header = ttk.Frame(frame)
        status_header.grid(row=3, column=0, sticky="ew")
        status_header.columnconfigure(0, weight=1)
        ttk.Label(status_header, text="Estado y actividad", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(status_header, textvariable=self.stage_status, style="Secondary.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=4, column=0, sticky="ew", pady=(6, 8))
        self.output = tk.Text(frame, height=12, wrap="word", state="disabled", font=("Consolas", 9))
        self.output.grid(row=5, column=0, sticky="nsew")
        self._append("Listo. Seleccioná un juego, una carpeta de proyecto y un perfil compatible.")

    def _path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse: Callable[[], None],
    ) -> None:
        ttk.Label(parent, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Elegir…", command=browse).grid(row=row, column=2, padx=(8, 0), pady=4)

    def _select_game(self) -> None:
        if selected := filedialog.askdirectory(title="Seleccionar carpeta del juego Unity"):
            self.game.set(selected)

    def _select_project(self) -> None:
        if selected := filedialog.askdirectory(title="Seleccionar carpeta del proyecto"):
            self.project.set(selected)

    def _select_profile(self) -> None:
        if selected := filedialog.askopenfilename(title="Seleccionar perfil de extracción", filetypes=[("JSON", "*.json")]):
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
            self.progress.start(12)
        else:
            self.progress.stop()

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
                self.root.after(0, lambda error=error: self._finish(stage, f"ERROR: {error}", True))
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
        self._run("ANALYZE", lambda: format_analysis(analyze(self.game.get())))

    def _create_project(self) -> None:
        def operation() -> str:
            profile = json.loads(Path(self.profile.get()).read_text(encoding="utf-8"))
            created = create_project(self.game.get(), self.project.get(), profile)
            return f"Created {created}"

        self._run("PROJECT", operation)

    def _extract(self) -> None:
        self._run("EXTRACT", lambda: f"Extracted {len(extract(self.project.get()))} strings")

    def _export(self) -> None:
        def operation() -> str:
            target = export_csv(self.project.get(), self.csv_path.get())
            return f"Exported {target}"

        self._run("CSV", operation)

    def _import(self) -> None:
        def operation() -> str:
            result = import_csv(self.project.get(), self.csv_path.get())
            return (
                f"Imported {result['imported']} | Pending {result['pending']} | "
                f"Intentionally empty {result['intentionally_empty']}"
            )

        self._run("CSV", operation)

    def _validate(self) -> None:
        self._run("VALIDATE", lambda: format_validation(validate(self.project.get())))

    def _inject(self) -> None:
        self._run("INJECT", lambda: f"Build generated at {inject(self.project.get())}")

    def _open_editor(self) -> None:
        try:
            EditorWindow(self.root, self.project.get())
        except Exception as error:
            messagebox.showerror("Editor failed", str(error))


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
