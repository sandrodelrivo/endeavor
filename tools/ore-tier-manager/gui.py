"""Tkinter GUI for editing biome_overrides.yaml + endeavour tag JSONs.

Three panes:
    Left   - tags (from data/endeavour/tags/worldgen/biome/*.json)
    Middle - ores assigned to the selected tag at the chosen step
             (filtered to the catalog - non-ore features stay in biome JSONs)
    Right  - biomes that belong to the selected tag

The "+ Add ore" picker shows ores from config/ore_catalog.yaml organized
by namespace (vanilla / create / immersiveengineering / etc.) with
multi-select. Custom IDs not in the catalog can also be typed (and a
warning appears, since apply.py won't propagate non-catalog features).

The xlsx is documentation only; never read or written.

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
    BIOME_OVERRIDES_PATH,
    ENDEAVOUR_TAG_DIR,
    GENERATION_STEPS,
    OP_ADD,
    OP_REMOVE,
    OP_SET,
    TOOL_ROOT,
    all_biome_files,
    biome_id_from_path,
    load_ore_catalog,
    load_ore_catalog_categorized,
    normalize_biome_id,
    yaml_dump,
    yaml_load,
)


DEFAULT_STEP = "underground_ores"


# --- Data model -----------------------------------------------------------

class DataModel:
    def __init__(self) -> None:
        self.load()

    def load(self) -> None:
        self.biome_files = {biome_id_from_path(f): f for f in all_biome_files()}
        self.all_biome_ids = sorted(self.biome_files)

        self._bo_header = _read_header(BIOME_OVERRIDES_PATH)
        self.biome_overrides = (yaml_load(BIOME_OVERRIDES_PATH) or {})

        self.tags = self._load_tags()
        self.catalog = load_ore_catalog()
        self.catalog_categorized = load_ore_catalog_categorized()

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

    def is_in_catalog(self, feature: str) -> bool:
        return feature in self.catalog

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

    def add_features_to_tag(self, tag: str, features: list[str],
                            step: str = DEFAULT_STEP) -> None:
        key = f"#endeavour:{tag}"
        ov = self.biome_overrides.setdefault(key, {})
        block = ov.setdefault(step, {})
        if isinstance(block, list):
            for f in features:
                if f not in block:
                    block.append(f)
            return
        if OP_SET in block:
            for f in features:
                if f not in block[OP_SET]:
                    block[OP_SET].append(f)
            return
        adds = block.setdefault(OP_ADD, [])
        for f in features:
            if f not in adds:
                adds.append(f)

    def remove_features_from_tag(self, tag: str, features: list[str],
                                 step: str = DEFAULT_STEP) -> None:
        key = f"#endeavour:{tag}"
        ov = self.biome_overrides.get(key) or {}
        block = ov.get(step)
        if block is None:
            return
        if isinstance(block, list):
            for f in features:
                if f in block:
                    block.remove(f)
            if not block:
                del ov[step]
            if not ov:
                del self.biome_overrides[key]
            return
        if OP_ADD in block:
            for f in features:
                if f in block[OP_ADD]:
                    block[OP_ADD].remove(f)
            if not block[OP_ADD]:
                del block[OP_ADD]
        if OP_SET in block:
            for f in features:
                if f in block[OP_SET]:
                    block[OP_SET].remove(f)
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
        yaml_dump(BIOME_OVERRIDES_PATH, bo_clean, header=self._bo_header)

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
        self.root.geometry("1280x760")

        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Save (YAML + tag JSONs)",
                          command=self._save, accelerator="Ctrl+S")
        filem.add_command(label="Reload from disk (discard edits)",
                          command=self._reload)
        filem.add_separator()
        filem.add_command(label="Apply (strip biome JSONs + write biome_modifiers)",
                          command=self._apply)
        filem.add_command(label="Run validate.py", command=self._validate)
        filem.add_separator()
        filem.add_command(label="Quit", command=self._on_close)
        menubar.add_cascade(label="File", menu=filem)
        self.root.config(menu=menubar)
        self.root.bind("<Control-s>", lambda _e: self._save())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        bar = ttk.Frame(self.root, padding=(8, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Reload", command=self._reload).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Apply", command=self._apply).pack(side="left", padx=(18, 0))
        ttk.Button(bar, text="Validate", command=self._validate).pack(side="left", padx=(6, 0))
        self.status = ttk.Label(bar, text="Loaded.", anchor="e")
        self.status.pack(side="right", fill="x", expand=True)

        step_bar = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        step_bar.pack(fill="x")
        ttk.Label(step_bar, text="Generation step:").pack(side="left")
        self.step_var = tk.StringVar(value=DEFAULT_STEP)
        cb = ttk.Combobox(step_bar, textvariable=self.step_var,
                          values=list(GENERATION_STEPS), state="readonly",
                          width=24)
        cb.pack(side="left", padx=(6, 0))
        cb.bind("<<ComboboxSelected>>",
                lambda _e: (self._refresh_features(), None))
        ttk.Label(step_bar,
                  text=f"   ({len(self.model.catalog)} ores in catalog)",
                  foreground="#777").pack(side="left", padx=(20, 0))

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

        # Middle: features (ores)
        middle = ttk.Frame(body)
        body.add(middle, weight=2)
        self.feat_label = ttk.Label(middle, text="Ores (select a tag)",
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
        ttk.Button(mb, text="+ Add ore(s)",
                   command=self._add_features).pack(side="left")
        ttk.Button(mb, text="- Remove",
                   command=self._remove_features).pack(side="left", padx=(6, 0))

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
        ttk.Button(rb, text="+ Add biome(s)",
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
            self.feat_label.config(text="Ores (select a tag)")
            return
        feats = self.model.features_for_tag(tag, step)
        # Annotate non-catalog features so the user can see what won't propagate
        labels = []
        n_non_catalog = 0
        for f in feats:
            if self.model.is_in_catalog(f):
                labels.append(f)
            else:
                labels.append(f"{f}    [NOT IN CATALOG]")
                n_non_catalog += 1
        suffix = f" ({n_non_catalog} non-catalog)" if n_non_catalog else ""
        self.feat_label.config(
            text=f"Ores in #endeavour:{tag} @ {step}{suffix}")
        flt = self.feat_filter.get().lower()
        for label in labels:
            if flt and flt not in label.lower():
                continue
            self.feat_list.insert("end", label)

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
                f"This deletes the tag JSON and removes its entry from "
                f"biome_overrides.yaml. Biomes lose membership but are "
                f"otherwise unchanged.",
                parent=self.root):
            return
        self.model.delete_tag(tag)
        self._mark_dirty()
        self._refresh_left()
        self._refresh_features()
        self._refresh_biomes()

    def _add_features(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            messagebox.showinfo("Pick a tag",
                                "Select a tag in the left pane first.",
                                parent=self.root)
            return
        step = self.step_var.get()
        already = set(self.model.features_for_tag(tag, step))
        picked = _ore_picker(
            self.root, self.model.catalog_categorized,
            already=already,
            title="Add ores",
            prompt=f"Pick ore(s) to add to #endeavour:{tag} @ {step}.\n"
                   f"Multi-select with Ctrl/Shift. Or type a custom ID at "
                   f"the bottom (must be in the catalog to take effect).")
        if not picked:
            return
        self.model.add_features_to_tag(tag, picked, step)
        self._mark_dirty()
        self._refresh_features()

    def _remove_features(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            return
        step = self.step_var.get()
        picked_labels = [self.feat_list.get(i) for i in self.feat_list.curselection()]
        if not picked_labels:
            messagebox.showinfo("Pick ores",
                                "Select ore(s) in the middle list to remove.",
                                parent=self.root)
            return
        # Strip "[NOT IN CATALOG]" suffix
        picked = [lab.split("    [")[0] for lab in picked_labels]
        self.model.remove_features_from_tag(tag, picked, step)
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
            self.root, "Add biomes",
            f"Pick biome(s) to add to #endeavour:{tag}.\n"
            f"Multi-select with Ctrl/Shift.",
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


# --- pickers --------------------------------------------------------------

def _ore_picker(parent: tk.Misc,
                catalog_by_category: dict[str, list[str]],
                already: set[str],
                title: str,
                prompt: str) -> list[str] | None:
    """Modal multi-select picker for ores, organized by mod namespace.

    Renders the catalog as a treeview grouped by category. Multi-select
    via Ctrl/Shift. Custom IDs can be typed in the bottom field. Returns
    the union of selected and custom-typed IDs.
    """
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    win.geometry("620x640")

    ttk.Label(win, text=prompt, wraplength=580, justify="left").pack(
        anchor="w", padx=10, pady=(10, 4))
    ttk.Label(win, text="Filter:").pack(anchor="w", padx=10)
    filter_var = tk.StringVar()
    ttk.Entry(win, textvariable=filter_var).pack(fill="x", padx=10)

    tree_frame = ttk.Frame(win)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=(4, 4))
    tree = ttk.Treeview(tree_frame, show="tree", selectmode="extended")
    sb = ttk.Scrollbar(tree_frame, command=tree.yview)
    tree.config(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    iid_to_ore: dict[str, str] = {}
    cat_iids: list[str] = []

    def populate():
        tree.delete(*tree.get_children())
        iid_to_ore.clear()
        cat_iids.clear()
        f = filter_var.get().lower()
        for category, ores in catalog_by_category.items():
            visible = [o for o in ores
                       if (not f or f in o.lower() or f in category.lower())
                       and o not in already]
            if not visible:
                continue
            cat_iid = tree.insert("", "end", text=f"{category}  ({len(visible)})",
                                  open=True)
            cat_iids.append(cat_iid)
            for ore in visible:
                child_iid = tree.insert(cat_iid, "end", text=ore)
                iid_to_ore[child_iid] = ore

    filter_var.trace_add("write", lambda *_: populate())
    populate()

    # Quick "select all visible" / "clear selection" buttons
    qb = ttk.Frame(win)
    qb.pack(fill="x", padx=10)
    ttk.Button(qb, text="Select all visible",
               command=lambda: tree.selection_set(*iid_to_ore.keys())).pack(side="left")
    ttk.Button(qb, text="Clear selection",
               command=lambda: tree.selection_remove(*tree.selection())).pack(side="left", padx=(6, 0))

    ttk.Label(win, text="Or type a custom ID (one per line):").pack(
        anchor="w", padx=10, pady=(8, 0))
    custom_text = tk.Text(win, height=3)
    custom_text.pack(fill="x", padx=10)

    result: dict = {"value": None}

    def on_ok():
        out: list[str] = []
        # From tree selection
        for iid in tree.selection():
            if iid in iid_to_ore:
                out.append(iid_to_ore[iid])
        # From custom text
        for line in custom_text.get("1.0", "end").splitlines():
            v = line.strip()
            if v and v not in out:
                out.append(v)
        if not out:
            return
        result["value"] = out
        win.destroy()

    def on_cancel():
        win.destroy()

    btn_row = ttk.Frame(win)
    btn_row.pack(fill="x", padx=10, pady=(8, 10))
    ttk.Button(btn_row, text="OK", command=on_ok).pack(side="right")
    ttk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="right", padx=(0, 6))
    win.bind("<Escape>", lambda _e: on_cancel())

    win.wait_window()
    return result["value"]


def _pick_from_list(parent: tk.Misc, title: str, prompt: str,
                    options: list[str], multi: bool = False
                    ) -> str | list[str] | None:
    """Single/multi-select picker with filter (used for biome lists)."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    win.geometry("520x560")

    ttk.Label(win, text=prompt, wraplength=480, justify="left").pack(
        anchor="w", padx=10, pady=(10, 4))
    ttk.Label(win, text="Filter:").pack(anchor="w", padx=10)
    filter_var = tk.StringVar()
    ttk.Entry(win, textvariable=filter_var).pack(fill="x", padx=10)
    lb = tk.Listbox(win, selectmode="extended" if multi else "browse",
                    exportselection=False, activestyle="dotbox")
    lb.pack(fill="both", expand=True, padx=10, pady=(4, 4))

    def refresh():
        lb.delete(0, "end")
        f = filter_var.get().lower()
        for o in options:
            if f and f not in o.lower():
                continue
            lb.insert("end", o)

    filter_var.trace_add("write", lambda *_: refresh())
    refresh()

    if multi:
        qb = ttk.Frame(win)
        qb.pack(fill="x", padx=10)
        ttk.Button(qb, text="Select all visible",
                   command=lambda: lb.select_set(0, "end")).pack(side="left")
        ttk.Button(qb, text="Clear selection",
                   command=lambda: lb.select_clear(0, "end")).pack(side="left", padx=(6, 0))

    result: dict = {"value": None}

    def on_ok():
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
