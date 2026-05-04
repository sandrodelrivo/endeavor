"""Tkinter GUI for editing biome_overrides.yaml + endeavour tag JSONs.

Three panes:
    Left   - tags (from data/endeavour/tags/worldgen/biome/*.json)
    Middle - features (typically ores) the selected tag adds at the
             chosen generation step
    Right  - biomes that belong to the selected tag

Buttons let you create/delete tags, add/remove ores from a tag, and
add/remove biomes to a tag. The menu bar saves the YAML + tag JSONs
and runs apply.py to regenerate the biome JSONs.

The xlsx (design/tier-map.xlsx) is documentation only; this GUI
neither reads nor writes it.

Run from this directory:
    python gui.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from collections import OrderedDict
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import yaml

from common import (
    CONFIG_DIR,
    DATAPACK_ROOT,
    ENDEAVOUR_TAG_DIR,
    GENERATION_STEPS,
    OP_ADD,
    OP_REMOVE,
    OP_SET,
    TOOL_ROOT,
    all_biome_files,
    biome_id_from_path,
    normalize_biome_id,
    yaml_dump,
    yaml_load,
)


BO_PATH = CONFIG_DIR / "biome_overrides.yaml"
DEFAULT_STEP = "underground_ores"


# --- Data model -----------------------------------------------------------

class DataModel:
    """Loads + mutates biome_overrides.yaml and the tag JSONs.

    Edits stay in memory until save_all() runs. apply.py is invoked
    separately so the user can review the YAML diff first.
    """

    def __init__(self) -> None:
        self.load()

    def load(self) -> None:
        self.biome_files = {biome_id_from_path(f): f for f in all_biome_files()}
        self.all_biome_ids = sorted(self.biome_files)

        self._bo_header = _read_header(BO_PATH)
        self.biome_overrides = (yaml_load(BO_PATH) or {})

        self.tags = self._load_tags()
        self.known_features = self._collect_known_features()

    def _load_tags(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for f in sorted(ENDEAVOUR_TAG_DIR.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            values: list[str] = []
            for v in data.get("values", []):
                if isinstance(v, str):
                    bid = v
                elif isinstance(v, dict) and "id" in v:
                    bid = v["id"]
                else:
                    continue
                values.append(normalize_biome_id(bid, set(self.biome_files)))
            out[f.stem] = {
                "replace": bool(data.get("replace", False)),
                "values": values,
                "_path": f,
            }
        return out

    def _collect_known_features(self) -> list[str]:
        feats: set[str] = set()
        for f in self.biome_files.values():
            data = json.loads(f.read_text(encoding="utf-8"))
            for step in data.get("features", []):
                for x in step:
                    feats.add(x)
        _gather_features(self.biome_overrides, feats)
        return sorted(feats)

    # --- queries ---

    def list_tags(self) -> list[str]:
        return sorted(self.tags)

    def features_for_tag(self, tag: str, step: str = DEFAULT_STEP) -> list[str]:
        block = (self.biome_overrides.get(f"#endeavour:{tag}") or {}).get(step)
        if block is None:
            return []
        if isinstance(block, list):
            return list(block)
        out: list[str] = []
        if OP_SET in block:
            out = list(block[OP_SET])
        for f in block.get(OP_ADD, []):
            if f not in out:
                out.append(f)
        for f in block.get(OP_REMOVE, []):
            if f in out:
                out.remove(f)
        return out

    def biomes_for_tag(self, tag: str) -> list[str]:
        return sorted(self.tags.get(tag, {}).get("values", []))

    def tags_of_biome(self, biome: str) -> list[str]:
        return sorted(t for t, info in self.tags.items()
                      if biome in info.get("values", []))

    # --- mutations ---

    def add_tag(self, tag: str) -> None:
        tag = tag.strip().lstrip("#").removeprefix("endeavour:")
        if not tag:
            raise ValueError("tag name required")
        if tag in self.tags:
            raise ValueError(f"tag {tag!r} already exists")
        self.tags[tag] = {"replace": False, "values": [], "_path": None}

    def delete_tag(self, tag: str) -> None:
        if tag in self.tags:
            self.tags[tag]["_delete"] = True
            self.tags[tag]["values"] = []
        key = f"#endeavour:{tag}"
        if key in self.biome_overrides:
            del self.biome_overrides[key]

    def add_feature_to_tag(self, tag: str, feature: str,
                           step: str = DEFAULT_STEP) -> None:
        key = f"#endeavour:{tag}"
        ov = self.biome_overrides.setdefault(key, {})
        block = ov.setdefault(step, {})
        if isinstance(block, list):
            if feature not in block:
                block.append(feature)
            return
        if OP_SET in block:
            if feature not in block[OP_SET]:
                block[OP_SET].append(feature)
            return
        adds = block.setdefault(OP_ADD, [])
        if feature not in adds:
            adds.append(feature)

    def remove_feature_from_tag(self, tag: str, feature: str,
                                step: str = DEFAULT_STEP) -> None:
        key = f"#endeavour:{tag}"
        ov = self.biome_overrides.get(key) or {}
        block = ov.get(step)
        if block is None:
            return
        if isinstance(block, list):
            if feature in block:
                block.remove(feature)
            if not block:
                del ov[step]
            if not ov:
                del self.biome_overrides[key]
            return
        if OP_ADD in block and feature in block[OP_ADD]:
            block[OP_ADD].remove(feature)
            if not block[OP_ADD]:
                del block[OP_ADD]
        if OP_SET in block and feature in block[OP_SET]:
            block[OP_SET].remove(feature)
            if not block[OP_SET]:
                del block[OP_SET]
        if not block:
            del ov[step]
        if not ov:
            del self.biome_overrides[key]

    def add_biome_to_tag(self, biome: str, tag: str) -> None:
        if biome not in self.biome_files:
            raise ValueError(f"unknown biome {biome!r}")
        if tag not in self.tags:
            raise ValueError(f"unknown tag {tag!r}")
        vals = self.tags[tag]["values"]
        if biome not in vals:
            vals.append(biome)

    def remove_biome_from_tag(self, biome: str, tag: str) -> None:
        if tag not in self.tags:
            return
        vals = self.tags[tag]["values"]
        if biome in vals:
            vals.remove(biome)

    # --- save ---

    def save_all(self) -> None:
        self._save_biome_overrides()
        self._save_tags()

    def _save_biome_overrides(self) -> None:
        bo_clean: dict[str, dict] = {}
        for key, steps in self.biome_overrides.items():
            if not steps:
                continue
            clean_steps = {s: v for s, v in steps.items() if not _is_empty_step(v)}
            if clean_steps:
                bo_clean[key] = clean_steps
        yaml_dump(BO_PATH, bo_clean, header=self._bo_header)

    def _save_tags(self) -> None:
        ENDEAVOUR_TAG_DIR.mkdir(parents=True, exist_ok=True)
        for tag, info in list(self.tags.items()):
            path: Path = info.get("_path") or (ENDEAVOUR_TAG_DIR / f"{tag}.json")
            if info.get("_delete"):
                if path.exists():
                    path.unlink()
                del self.tags[tag]
                continue
            data = {
                "replace": info.get("replace", False),
                "values": sorted(set(info["values"])),
            }
            text = json.dumps(data, indent=4) + "\n"
            path.write_text(text, encoding="utf-8")
            info["_path"] = path
            info.pop("_delete", None)


# --- helpers --------------------------------------------------------------

def _is_empty_step(v) -> bool:
    if v is None:
        return True
    if isinstance(v, list):
        return len(v) == 0
    if isinstance(v, dict):
        if not v:
            return True
        for k, val in v.items():
            if k in (OP_SET, OP_ADD, OP_REMOVE) and val:
                return False
        return True
    return False


def _gather_features(node, sink: set[str]) -> None:
    if isinstance(node, list):
        for x in node:
            if isinstance(x, str):
                sink.add(x)
    elif isinstance(node, dict):
        for v in node.values():
            _gather_features(v, sink)


def _read_header(path: Path) -> str:
    if not path.exists():
        return ""
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.strip() == "":
            lines.append(line)
        else:
            break
    return "\n".join(lines).rstrip()


# --- GUI ------------------------------------------------------------------

class GuiApp:
    def __init__(self, root: tk.Tk, model: DataModel) -> None:
        self.root = root
        self.model = model
        self._dirty = False
        self._build()
        self._refresh_left()

    def _build(self) -> None:
        self.root.title("Endeavour Ore Tag Manager")
        self.root.geometry("1200x720")

        # Menu bar
        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Save (YAML + tag JSONs)",
                          command=self._save, accelerator="Ctrl+S")
        filem.add_command(label="Reload from disk (discard edits)",
                          command=self._reload)
        filem.add_separator()
        filem.add_command(label="Apply (regenerate biome JSONs)",
                          command=self._apply)
        filem.add_command(label="Run validate.py", command=self._validate)
        filem.add_separator()
        filem.add_command(label="Quit", command=self._on_close)
        menubar.add_cascade(label="File", menu=filem)
        self.root.config(menu=menubar)
        self.root.bind("<Control-s>", lambda _e: self._save())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Toolbar
        bar = ttk.Frame(self.root, padding=(8, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Reload", command=self._reload).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Apply -> biome JSONs",
                   command=self._apply).pack(side="left", padx=(18, 0))
        ttk.Button(bar, text="Validate", command=self._validate).pack(side="left", padx=(6, 0))
        self.status = ttk.Label(bar, text="Loaded.", anchor="e")
        self.status.pack(side="right", fill="x", expand=True)

        step_bar = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        step_bar.pack(fill="x")
        ttk.Label(step_bar, text="Generation step for ore ops:").pack(side="left")
        self.step_var = tk.StringVar(value=DEFAULT_STEP)
        cb = ttk.Combobox(step_bar, textvariable=self.step_var,
                          values=list(GENERATION_STEPS), state="readonly",
                          width=24)
        cb.pack(side="left", padx=(6, 0))
        cb.bind("<<ComboboxSelected>>",
                lambda _e: (self._refresh_features(), None))

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left: tags
        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text="Tags", font=("", 10, "bold")).pack(anchor="w")
        self.tag_list = tk.Listbox(left, exportselection=False, activestyle="dotbox")
        self.tag_list.pack(fill="both", expand=True, pady=(4, 4))
        self.tag_list.bind("<<ListboxSelect>>", self._on_tag_select)
        lb = ttk.Frame(left)
        lb.pack(fill="x")
        ttk.Button(lb, text="+ New tag", command=self._add_tag).pack(side="left")
        ttk.Button(lb, text="- Delete tag",
                   command=self._delete_tag).pack(side="left", padx=(6, 0))

        # Middle: features
        middle = ttk.Frame(body)
        body.add(middle, weight=2)
        self.feat_label = ttk.Label(middle, text="Features (select a tag)",
                                    font=("", 10, "bold"))
        self.feat_label.pack(anchor="w")
        ttk.Label(middle, text="Filter:").pack(anchor="w", pady=(4, 0))
        self.feat_filter = tk.StringVar()
        self.feat_filter.trace_add("write", lambda *_: self._refresh_features())
        ttk.Entry(middle, textvariable=self.feat_filter).pack(fill="x")
        self.feat_list = tk.Listbox(middle, selectmode="extended",
                                    exportselection=False, activestyle="dotbox")
        self.feat_list.pack(fill="both", expand=True, pady=(4, 4))
        mb = ttk.Frame(middle)
        mb.pack(fill="x")
        ttk.Button(mb, text="+ Add ore",
                   command=self._add_feature).pack(side="left")
        ttk.Button(mb, text="- Remove",
                   command=self._remove_feature).pack(side="left", padx=(6, 0))

        # Right: biomes
        right = ttk.Frame(body)
        body.add(right, weight=2)
        self.biome_label = ttk.Label(right, text="Biomes (select a tag)",
                                     font=("", 10, "bold"))
        self.biome_label.pack(anchor="w")
        ttk.Label(right, text="Filter:").pack(anchor="w", pady=(4, 0))
        self.biome_filter = tk.StringVar()
        self.biome_filter.trace_add("write", lambda *_: self._refresh_biomes())
        ttk.Entry(right, textvariable=self.biome_filter).pack(fill="x")
        self.biome_list = tk.Listbox(right, selectmode="extended",
                                     exportselection=False, activestyle="dotbox")
        self.biome_list.pack(fill="both", expand=True, pady=(4, 4))
        rb = ttk.Frame(right)
        rb.pack(fill="x")
        ttk.Button(rb, text="+ Add biome",
                   command=self._add_biome).pack(side="left")
        ttk.Button(rb, text="- Remove",
                   command=self._remove_biome).pack(side="left", padx=(6, 0))

    # --- left list ---

    def _refresh_left(self) -> None:
        prev = self._selected_tag()
        self.tag_list.delete(0, "end")
        for tag in self.model.list_tags():
            n = len(self.model.biomes_for_tag(tag))
            self.tag_list.insert("end", f"#endeavour:{tag}  ({n} biomes)")
        if prev:
            for i, name in enumerate(self.model.list_tags()):
                if name == prev:
                    self.tag_list.selection_set(i)
                    break

    def _selected_tag(self) -> str | None:
        sel = self.tag_list.curselection()
        if not sel:
            return None
        tags = self.model.list_tags()
        idx = sel[0]
        if 0 <= idx < len(tags):
            return tags[idx]
        return None

    def _on_tag_select(self, _evt=None) -> None:
        self._refresh_features()
        self._refresh_biomes()

    def _refresh_features(self) -> None:
        self.feat_list.delete(0, "end")
        tag = self._selected_tag()
        step = self.step_var.get()
        if tag is None:
            self.feat_label.config(text="Features (select a tag)")
            return
        feats = self.model.features_for_tag(tag, step)
        self.feat_label.config(
            text=f"Features added by #endeavour:{tag} @ {step}")
        flt = self.feat_filter.get().lower()
        for f in feats:
            if flt and flt not in f.lower():
                continue
            self.feat_list.insert("end", f)

    def _refresh_biomes(self) -> None:
        self.biome_list.delete(0, "end")
        tag = self._selected_tag()
        if tag is None:
            self.biome_label.config(text="Biomes (select a tag)")
            return
        biomes = self.model.biomes_for_tag(tag)
        self.biome_label.config(text=f"Biomes in #endeavour:{tag}")
        flt = self.biome_filter.get().lower()
        for b in biomes:
            if flt and flt not in b.lower():
                continue
            self.biome_list.insert("end", b)

    # --- mutations ---

    def _add_tag(self) -> None:
        name = simpledialog.askstring(
            "New tag", "Tag name (without '#endeavour:' prefix):",
            parent=self.root)
        if not name:
            return
        try:
            self.model.add_tag(name)
        except ValueError as e:
            messagebox.showerror("Cannot add tag", str(e), parent=self.root)
            return
        self._mark_dirty()
        self._refresh_left()

    def _delete_tag(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            return
        if not messagebox.askyesno(
                "Delete tag?",
                f"Delete tag '#endeavour:{tag}'?\n\n"
                f"This deletes the tag JSON file and removes its entry "
                f"from biome_overrides.yaml. Biomes are not affected; "
                f"they just stop being members of this tag.",
                parent=self.root):
            return
        self.model.delete_tag(tag)
        self._mark_dirty()
        self._refresh_left()
        self._refresh_features()
        self._refresh_biomes()

    def _add_feature(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            messagebox.showinfo("Pick a tag",
                                "Select a tag in the left pane first.",
                                parent=self.root)
            return
        step = self.step_var.get()
        feature = _pick_from_list(
            self.root, "Add feature",
            f"Pick a feature ID to add to #endeavour:{tag} @ {step}.\n"
            f"Or type a new ID at the bottom.",
            self.model.known_features, allow_custom=True)
        if not feature:
            return
        self.model.add_feature_to_tag(tag, feature, step)
        self._mark_dirty()
        self._refresh_features()

    def _remove_feature(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            return
        step = self.step_var.get()
        picked = [self.feat_list.get(i) for i in self.feat_list.curselection()]
        if not picked:
            messagebox.showinfo("Pick features",
                                "Select feature(s) in the middle list to remove.",
                                parent=self.root)
            return
        for f in picked:
            self.model.remove_feature_from_tag(tag, f, step)
        self._mark_dirty()
        self._refresh_features()

    def _add_biome(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            messagebox.showinfo("Pick a tag",
                                "Select a tag in the left pane first.",
                                parent=self.root)
            return
        already = set(self.model.biomes_for_tag(tag))
        # Annotate each option with its other tag memberships so the user
        # knows what they're combining.
        options: list[str] = []
        labels_to_id: dict[str, str] = {}
        for b in self.model.all_biome_ids:
            if b in already:
                continue
            other = [t for t in self.model.tags_of_biome(b) if t != tag]
            label = b if not other else f"{b}    [also: {', '.join(other)}]"
            options.append(label)
            labels_to_id[label] = b
        picked = _pick_from_list(
            self.root, "Add biome",
            f"Pick biome(s) to add to #endeavour:{tag}.",
            options, multi=True)
        if not picked:
            return
        for label in picked:
            self.model.add_biome_to_tag(labels_to_id[label], tag)
        self._mark_dirty()
        self._refresh_left()
        self._refresh_biomes()

    def _remove_biome(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            return
        picked = [self.biome_list.get(i) for i in self.biome_list.curselection()]
        if not picked:
            messagebox.showinfo("Pick biomes",
                                "Select biome(s) in the right list to remove.",
                                parent=self.root)
            return
        for b in picked:
            self.model.remove_biome_from_tag(b, tag)
        self._mark_dirty()
        self._refresh_left()
        self._refresh_biomes()

    # --- save / reload / apply ---

    def _save(self) -> None:
        try:
            self.model.save_all()
        except Exception as e:
            messagebox.showerror("Save failed", str(e), parent=self.root)
            return
        self._dirty = False
        self.status.config(text="Saved.")
        self._refresh_left()

    def _reload(self) -> None:
        if self._dirty and not messagebox.askyesno(
                "Reload?",
                "You have unsaved changes. Discard and reload from disk?",
                parent=self.root):
            return
        self.model.load()
        self._dirty = False
        self.status.config(text="Reloaded.")
        self._refresh_left()
        self._refresh_features()
        self._refresh_biomes()

    def _apply(self) -> None:
        if self._dirty:
            if not messagebox.askyesno(
                    "Save first?",
                    "You have unsaved changes. Save before running apply.py?",
                    parent=self.root):
                return
            self._save()
        self._run_subprocess(["python", "apply.py", "--diff"])

    def _validate(self) -> None:
        self._run_subprocess(["python", "validate.py"])

    def _run_subprocess(self, cmd: list[str]) -> None:
        self.status.config(text=f"Running: {' '.join(cmd)} ...")
        self.root.update_idletasks()
        try:
            r = subprocess.run(cmd, cwd=TOOL_ROOT, capture_output=True,
                               text=True, encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Run failed", str(e), parent=self.root)
            self.status.config(text="Error.")
            return
        out = (r.stdout or "") + (("\n--- stderr ---\n" + r.stderr) if r.stderr else "")
        ok = (r.returncode == 0)
        self.status.config(text=f"Exit {r.returncode}.")
        _show_text_dialog(self.root,
                          f"{cmd[1]}  (exit {r.returncode})",
                          out or "(no output)",
                          ok=ok)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.status.config(text="Modified (unsaved).")

    def _on_close(self) -> None:
        if self._dirty and not messagebox.askyesno(
                "Quit?", "You have unsaved changes. Quit anyway?",
                parent=self.root):
            return
        self.root.destroy()


# --- small reusable dialogs ----------------------------------------------

def _pick_from_list(parent: tk.Misc, title: str, prompt: str,
                    options: list[str], multi: bool = False,
                    allow_custom: bool = False) -> str | list[str] | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    win.geometry("520x520")

    ttk.Label(win, text=prompt, wraplength=480, justify="left").pack(
        anchor="w", padx=10, pady=(10, 4))
    ttk.Label(win, text="Filter:").pack(anchor="w", padx=10)
    filter_var = tk.StringVar()
    ttk.Entry(win, textvariable=filter_var).pack(fill="x", padx=10)
    lb = tk.Listbox(win, selectmode="extended" if multi else "browse",
                    exportselection=False, activestyle="dotbox")
    lb.pack(fill="both", expand=True, padx=10, pady=(4, 4))
    custom_var = tk.StringVar()
    if allow_custom:
        ttk.Label(win, text="Or type a custom value:").pack(anchor="w", padx=10)
        ttk.Entry(win, textvariable=custom_var).pack(fill="x", padx=10)

    def refresh():
        lb.delete(0, "end")
        f = filter_var.get().lower()
        for o in options:
            if f and f not in o.lower():
                continue
            lb.insert("end", o)

    filter_var.trace_add("write", lambda *_: refresh())
    refresh()

    result: dict = {"value": None}

    def on_ok():
        if allow_custom and custom_var.get().strip():
            result["value"] = custom_var.get().strip()
        else:
            sel = [lb.get(i) for i in lb.curselection()]
            if not sel:
                return
            result["value"] = sel if multi else sel[0]
        win.destroy()

    def on_cancel():
        win.destroy()

    btn_row = ttk.Frame(win)
    btn_row.pack(fill="x", padx=10, pady=(0, 10))
    ttk.Button(btn_row, text="OK", command=on_ok).pack(side="right")
    ttk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="right", padx=(0, 6))
    lb.bind("<Double-Button-1>", lambda _e: on_ok())
    win.bind("<Return>", lambda _e: on_ok())
    win.bind("<Escape>", lambda _e: on_cancel())

    win.wait_window()
    return result["value"]


def _show_text_dialog(parent: tk.Misc, title: str, body: str, ok: bool) -> None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.geometry("780x520")
    txt = tk.Text(win, wrap="word")
    txt.insert("1.0", body)
    txt.config(state="disabled")
    sb = ttk.Scrollbar(win, command=txt.yview)
    txt.config(yscrollcommand=sb.set)
    txt.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")
    if not ok:
        win.configure(bg="#fee")


def main() -> int:
    root = tk.Tk()
    try:
        model = DataModel()
    except Exception as e:
        messagebox.showerror("Failed to load", str(e))
        return 1
    GuiApp(root, model)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
