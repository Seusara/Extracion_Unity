from __future__ import annotations

import json
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


class EditorWindow:
    def __init__(self, parent: tk.Misc, project_path: str) -> None:
        if not project_path:
            raise ValueError("Select a project before opening the editor")
        self.project_path = project_path
        self.entries: list[dict] = []
        self.window = tk.Toplevel(parent)
        self.window.title("Translation editor")
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
        ttk.Label(filters, text="Search:").grid(row=0, column=0, padx=(0, 6))
        search = ttk.Entry(filters, textvariable=self.query)
        search.grid(row=0, column=1, sticky="ew")
        search.bind("<KeyRelease>", lambda _event: self._render())
        ttk.Label(filters, text="Status:").grid(row=0, column=2, padx=(12, 6))
        status = ttk.Combobox(
            filters,
            textvariable=self.status,
            values=("all", "untranslated", "translated", "intentionally_empty"),
            state="readonly",
            width=20,
        )
        status.grid(row=0, column=3)
        status.bind("<<ComboboxSelected>>", lambda _event: self._render())
        ttk.Button(filters, text="Refresh", command=self.refresh).grid(row=0, column=4, padx=(8, 0))

        self.tree = ttk.Treeview(
            frame,
            columns=("original", "translation", "status"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("original", text="Original")
        self.tree.heading("translation", text="Translation")
        self.tree.heading("status", text="Status")
        self.tree.column("original", width=360)
        self.tree.column("translation", width=360)
        self.tree.column("status", width=130, stretch=False)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._select_entry)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        editor = ttk.LabelFrame(frame, text="Selected translation", padding=10)
        editor.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        editor.columnconfigure(0, weight=1)
        self.original = tk.Text(editor, height=3, wrap="word", state="disabled")
        self.original.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.translation = tk.Text(editor, height=3, wrap="word")
        self.translation.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(
            editor,
            text="Intentionally empty",
            variable=self.intentionally_empty,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Button(editor, text="Save translation", command=self.save).grid(
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
            messagebox.showwarning("No selection", "Select a translation row first")
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
            messagebox.showerror("Save failed", str(error))


class DesktopApp:
    """Thin Tk UI. All translation behavior remains in the pipeline module."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Unity Translator MVP")
        self.root.minsize(760, 520)
        self.game = tk.StringVar()
        self.project = tk.StringVar()
        self.profile = tk.StringVar()
        self.csv_path = tk.StringVar()
        self._buttons: list[ttk.Button] = []
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="UNITY TRANSLATOR", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16)
        )
        frame.columnconfigure(1, weight=1)

        self._path_row(frame, 1, "Game", self.game, self._select_game)
        self._path_row(frame, 2, "Project", self.project, self._select_project)
        self._path_row(frame, 3, "Profile", self.profile, self._select_profile)
        self._path_row(frame, 4, "CSV", self.csv_path, self._select_csv)

        actions = ttk.Frame(frame)
        actions.grid(row=5, column=0, columnspan=3, sticky="ew", pady=12)
        specs = [
            ("Analyze", self._analyze),
            ("Create Project", self._create_project),
            ("Extract", self._extract),
            ("Export CSV", self._export),
            ("Import CSV", self._import),
            ("Validate", self._validate),
            ("Inject", self._inject),
            ("Editor", self._open_editor),
        ]
        for column, (label, callback) in enumerate(specs):
            button = ttk.Button(actions, text=label, command=callback)
            button.grid(row=0, column=column, padx=(0, 6), pady=3)
            self._buttons.append(button)

        ttk.Label(frame, text="Status / logs").grid(row=6, column=0, columnspan=3, sticky="w")
        self.output = tk.Text(frame, height=17, wrap="word", state="disabled")
        self.output.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        frame.rowconfigure(7, weight=1)
        self._append("Ready. Select a game, project path and extractor profile.")

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
        ttk.Button(parent, text="Browse", command=browse).grid(row=row, column=2, padx=(8, 0), pady=4)

    def _select_game(self) -> None:
        if selected := filedialog.askdirectory(title="Select Unity game folder"):
            self.game.set(selected)

    def _select_project(self) -> None:
        if selected := filedialog.askdirectory(title="Select existing project folder"):
            self.project.set(selected)

    def _select_profile(self) -> None:
        if selected := filedialog.askopenfilename(title="Select extractor profile", filetypes=[("JSON", "*.json")]):
            self.profile.set(selected)

    def _select_csv(self) -> None:
        if selected := filedialog.askopenfilename(title="Select translation CSV", filetypes=[("CSV", "*.csv")]):
            self.csv_path.set(selected)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in self._buttons:
            button.configure(state=state)

    def _append(self, message: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", message.rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _run(self, stage: str, operation: Callable[[], str]) -> None:
        self._set_busy(True)
        self._append(f"[{stage}] Starting...")

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
        if failed:
            messagebox.showerror(f"{stage} failed", message)

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
