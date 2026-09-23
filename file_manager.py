"""
File Manager - Browse files/folders with size and last-accessed info,
sort by any column, and rename/delete entries safely (Recycle Bin when available).
Cross-platform: Windows, macOS, and Linux.
"""

import os
import platform
import shutil
import string
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

try:
    from send2trash import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False

# Known OS/system files that must never be moved even if found loose in a drive root
SYSTEM_FILE_SKIP_LIST = {
    "pagefile.sys", "hiberfil.sys", "swapfile.sys", "bootmgr", "bootnxt",
    "desktop.ini", "ntuser.dat", "autoexec.bat", "config.sys", "io.sys", "msdos.sys",
    "dumpstack.log.tmp",
}

FILE_CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".tif", ".ico", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt", ".csv", ".md"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Installers": {".exe", ".msi", ".bat", ".sh", ".apk", ".appimage"},
}


def category_for_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return "Other"


def preview_organize_folder(path):
    """Read-only preview: how many loose files (directly in path, not in subfolders)
    would be moved into each category folder"""
    counts = {}
    skipped_system = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if entry.name.lower() in SYSTEM_FILE_SKIP_LIST:
                    skipped_system += 1
                    continue
                category = category_for_file(entry.name)
                counts[category] = counts.get(category, 0) + 1
    except OSError as e:
        return None, str(e)
    return {"counts": counts, "total": sum(counts.values()), "skipped_system": skipped_system}, None


def organize_folder_by_type(path):
    """Move loose files directly inside `path` into category subfolders (Images, Documents, etc.).
    Subfolders and known system files are never touched."""
    moved = 0
    created_folders = set()
    conflicts = []

    try:
        with os.scandir(path) as it:
            file_entries = [e for e in it if e.is_file(follow_symlinks=False)]
    except OSError as e:
        return None, str(e)

    for entry in file_entries:
        if entry.name.lower() in SYSTEM_FILE_SKIP_LIST:
            continue
        category = category_for_file(entry.name)
        dest_dir = os.path.join(path, category)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            created_folders.add(category)
            dest_path = os.path.join(dest_dir, entry.name)
            if os.path.exists(dest_path):
                conflicts.append(entry.name)
                continue
            shutil.move(entry.path, dest_path)
            moved += 1
        except OSError as e:
            conflicts.append(f"{entry.name} ({str(e)})")

    return {"moved": moved, "categories": sorted(created_folders), "conflicts": conflicts}, None


def format_size(num_bytes):
    """Human-readable file size"""
    if num_bytes is None:
        return ""
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def format_time(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def list_windows_drives():
    drives = []
    for letter in string.ascii_uppercase:
        path = f"{letter}:\\"
        if os.path.exists(path):
            drives.append(path)
    return drives


def open_path_with_default_app(path):
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True, None
    except Exception as e:
        return False, str(e)


class FileManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🗂️ File Manager - Browse, Arrange, Edit & Delete")
        self.root.geometry("980x620")

        self.current_path = os.path.expanduser("~")
        self.entries = []  # list of dicts for the currently listed folder
        self.sort_column = "name"
        self.sort_reverse = False
        self.size_calc_queue = queue.Queue()

        self._setup_ui()
        self.navigate_to(self.current_path)

    # ---------------------------------------------------------------- UI

    def _setup_ui(self):
        nav_frame = ttk.Frame(self.root, padding=(10, 10, 10, 5))
        nav_frame.pack(fill="x")

        ttk.Button(nav_frame, text="⬅ Up", command=self.go_up).pack(side="left")
        ttk.Button(nav_frame, text="🏠 Home", command=lambda: self.navigate_to(os.path.expanduser("~"))).pack(side="left", padx=(5, 0))
        ttk.Button(nav_frame, text="🔄 Refresh", command=lambda: self.navigate_to(self.current_path)).pack(side="left", padx=(5, 0))

        if platform.system() == "Windows":
            self.drive_var = tk.StringVar()
            drive_combo = ttk.Combobox(nav_frame, textvariable=self.drive_var, values=list_windows_drives(),
                                        state="readonly", width=6)
            drive_combo.pack(side="left", padx=(10, 0))
            drive_combo.bind("<<ComboboxSelected>>", lambda e: self.navigate_to(self.drive_var.get()))

        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(nav_frame, textvariable=self.path_var)
        path_entry.pack(side="left", fill="x", expand=True, padx=10)
        path_entry.bind("<Return>", lambda e: self.navigate_to(self.path_var.get()))

        ttk.Button(nav_frame, text="Go", command=lambda: self.navigate_to(self.path_var.get())).pack(side="left")

        filter_frame = ttk.Frame(self.root, padding=(10, 0, 10, 5))
        filter_frame.pack(fill="x")
        ttk.Label(filter_frame, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=30)
        filter_entry.pack(side="left", padx=(5, 10))
        filter_entry.bind("<KeyRelease>", lambda e: self.render_entries())
        ttk.Button(filter_frame, text="📏 Calculate Folder Sizes", command=self.calculate_folder_sizes).pack(side="left")

        organize_frame = ttk.LabelFrame(self.root, text="🗂️ Organize Loose Files Into Folders (by type)", padding=10)
        organize_frame.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Button(organize_frame, text="Organize Desktop",
                   command=lambda: self.organize_folder_prompt(os.path.join(os.path.expanduser("~"), "Desktop"))).pack(side="left")
        ttk.Button(organize_frame, text="Organize Documents",
                   command=lambda: self.organize_folder_prompt(os.path.join(os.path.expanduser("~"), "Documents"))).pack(side="left", padx=(8, 0))
        ttk.Button(organize_frame, text="Organize Downloads",
                   command=lambda: self.organize_folder_prompt(os.path.join(os.path.expanduser("~"), "Downloads"))).pack(side="left", padx=(8, 0))
        if platform.system() == "Windows":
            ttk.Button(organize_frame, text="Organize C:\\ (root files only)",
                       command=lambda: self.organize_folder_prompt("C:\\")).pack(side="left", padx=(8, 0))
        ttk.Button(organize_frame, text="Organize Current Folder",
                   command=lambda: self.organize_folder_prompt(self.current_path)).pack(side="left", padx=(8, 0))

        tree_frame = ttk.Frame(self.root, padding=(10, 0, 10, 5))
        tree_frame.pack(fill="both", expand=True)

        columns = ("name", "type", "size", "modified", "accessed")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")
        headings = {"name": "Name", "type": "Type", "size": "Size", "modified": "Last Modified", "accessed": "Last Accessed"}
        widths = {"name": 320, "type": 70, "size": 100, "modified": 150, "accessed": 150}
        for col in columns:
            self.tree.heading(col, text=headings[col], command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<Double-1>", self.on_double_click)

        actions_frame = ttk.Frame(self.root, padding=10)
        actions_frame.pack(fill="x")
        ttk.Button(actions_frame, text="📂 Open Selected", command=self.open_selected).pack(side="left")
        ttk.Button(actions_frame, text="✏️ Rename Selected", command=self.rename_selected).pack(side="left", padx=(10, 0))
        ttk.Button(actions_frame, text="🗑️ Delete Selected", command=self.delete_selected).pack(side="left", padx=(10, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    # ---------------------------------------------------------------- Navigation / listing

    def navigate_to(self, path):
        path = os.path.abspath(os.path.expanduser(path.strip())) if path else self.current_path
        if not os.path.isdir(path):
            messagebox.showerror("❌ Error", f"Not a valid folder:\n{path}")
            return

        try:
            entries = []
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        is_dir = entry.is_dir(follow_symlinks=False)
                        entries.append({
                            "name": entry.name,
                            "path": entry.path,
                            "is_dir": is_dir,
                            "size": None if is_dir else stat.st_size,
                            "modified": stat.st_mtime,
                            "accessed": stat.st_atime,
                        })
                    except OSError:
                        continue
        except PermissionError:
            messagebox.showerror("❌ Access Denied", f"You don't have permission to open:\n{path}")
            return
        except OSError as e:
            messagebox.showerror("❌ Error", str(e))
            return

        self.current_path = path
        self.path_var.set(path)
        self.entries = entries
        self.render_entries()
        self.status_var.set(f"{len(entries)} item(s) in {path}")

    def go_up(self):
        parent = os.path.dirname(self.current_path.rstrip("\\/"))
        if parent and parent != self.current_path:
            self.navigate_to(parent)

    def render_entries(self):
        query = self.filter_var.get().strip().lower()
        rows = [e for e in self.entries if query in e["name"].lower()] if query else list(self.entries)

        key_map = {
            "name": lambda e: e["name"].lower(),
            "type": lambda e: (0 if e["is_dir"] else 1, e["name"].lower()),
            "size": lambda e: e["size"] if e["size"] is not None else -1,
            "modified": lambda e: e["modified"],
            "accessed": lambda e: e["accessed"],
        }
        rows.sort(key=key_map[self.sort_column], reverse=self.sort_reverse)

        self.tree.delete(*self.tree.get_children())
        for e in rows:
            size_display = "<DIR>" if e["is_dir"] and e["size"] is None else format_size(e["size"])
            self.tree.insert("", "end", iid=e["path"], values=(
                e["name"],
                "Folder" if e["is_dir"] else "File",
                size_display,
                format_time(e["modified"]),
                format_time(e["accessed"]),
            ))

    def sort_by(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column, self.sort_reverse = column, False
        self.render_entries()

    # ---------------------------------------------------------------- Actions

    def _get_selected_entries(self):
        selection = self.tree.selection()
        return [e for e in self.entries if e["path"] in selection]

    def on_double_click(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        path = selection[0]
        entry = next((e for e in self.entries if e["path"] == path), None)
        if entry and entry["is_dir"]:
            self.navigate_to(path)
        elif entry:
            success, error = open_path_with_default_app(path)
            if not success:
                messagebox.showerror("❌ Error", f"Could not open file: {error}")

    def open_selected(self):
        selected = self._get_selected_entries()
        if not selected:
            messagebox.showwarning("⚠️ Nothing Selected", "Select a file or folder first.")
            return
        for entry in selected:
            if entry["is_dir"]:
                self.navigate_to(entry["path"])
                break
            success, error = open_path_with_default_app(entry["path"])
            if not success:
                messagebox.showerror("❌ Error", f"Could not open '{entry['name']}': {error}")

    def rename_selected(self):
        selected = self._get_selected_entries()
        if len(selected) != 1:
            messagebox.showwarning("⚠️ Select One", "Select exactly one file or folder to rename.")
            return
        entry = selected[0]
        new_name = simpledialog.askstring("✏️ Rename", "New name:", initialvalue=entry["name"], parent=self.root)
        if not new_name or new_name == entry["name"]:
            return
        new_path = os.path.join(os.path.dirname(entry["path"]), new_name)
        if os.path.exists(new_path):
            messagebox.showerror("❌ Error", f"'{new_name}' already exists in this folder.")
            return
        try:
            os.rename(entry["path"], new_path)
        except OSError as e:
            messagebox.showerror("❌ Error", f"Could not rename: {str(e)}")
            return
        self.status_var.set(f"✅ Renamed '{entry['name']}' to '{new_name}'")
        self.navigate_to(self.current_path)

    def delete_selected(self):
        selected = self._get_selected_entries()
        if not selected:
            messagebox.showwarning("⚠️ Nothing Selected", "Select one or more files/folders first.")
            return

        method = "moved to the Recycle Bin" if HAS_SEND2TRASH else "PERMANENTLY DELETED (no Recycle Bin support installed)"
        names = "\n".join(f"  • {e['name']}" for e in selected[:10])
        more = f"\n  ...and {len(selected) - 10} more" if len(selected) > 10 else ""
        confirm = messagebox.askyesno(
            "⚠️ Confirm Delete",
            f"The following {len(selected)} item(s) will be {method}:\n\n{names}{more}\n\nProceed?"
        )
        if not confirm:
            return

        failed = []
        for entry in selected:
            try:
                if HAS_SEND2TRASH:
                    send2trash(entry["path"])
                elif entry["is_dir"]:
                    shutil.rmtree(entry["path"])
                else:
                    os.remove(entry["path"])
            except Exception as e:
                failed.append(f"{entry['name']}: {str(e)}")

        self.navigate_to(self.current_path)
        if failed:
            messagebox.showerror("❌ Some Deletions Failed", "\n".join(failed))
        else:
            self.status_var.set(f"✅ Deleted {len(selected)} item(s) ({method})")

    def calculate_folder_sizes(self):
        """Compute folder sizes in the background (can be slow for large folders)"""
        folders = [e for e in self.entries if e["is_dir"]]
        if not folders:
            return

        self.status_var.set("Calculating folder sizes...")

        def worker():
            for entry in folders:
                total = 0
                try:
                    for dirpath, _, filenames in os.walk(entry["path"]):
                        for fname in filenames:
                            try:
                                total += os.path.getsize(os.path.join(dirpath, fname))
                            except OSError:
                                continue
                except OSError:
                    pass
                self.size_calc_queue.put((entry["path"], total))
            self.size_calc_queue.put(("__done__", None))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(150, self._poll_size_queue)

    def _poll_size_queue(self):
        try:
            while True:
                path, total = self.size_calc_queue.get_nowait()
                if path == "__done__":
                    self.status_var.set(f"✅ Folder sizes calculated for {self.current_path}")
                    return
                for e in self.entries:
                    if e["path"] == path:
                        e["size"] = total
                        break
                self.render_entries()
        except queue.Empty:
            pass
        self.root.after(150, self._poll_size_queue)

    def organize_folder_prompt(self, target_path):
        """Preview loose files in target_path and, if confirmed, sort them into type-based subfolders
        (Images/Documents/Videos/etc). Only files directly in target_path are touched - subfolders
        and known system files are never moved."""
        if not os.path.isdir(target_path):
            messagebox.showerror("❌ Error", f"Folder not found:\n{target_path}")
            return

        preview, error = preview_organize_folder(target_path)
        if error:
            messagebox.showerror("❌ Error", error)
            return
        if preview["total"] == 0:
            messagebox.showinfo("✅ Nothing To Do", f"No loose files found directly in:\n{target_path}")
            return

        breakdown = "\n".join(f"  • {cat}: {count}" for cat, count in sorted(preview["counts"].items()))
        system_note = f"\n\n({preview['skipped_system']} system file(s) will be skipped)" if preview["skipped_system"] else ""
        confirm = messagebox.askyesno(
            "⚠️ Confirm Organize",
            f"Found {preview['total']} loose file(s) directly in:\n{target_path}\n\n{breakdown}"
            f"{system_note}\n\n"
            f"Each file will be moved into a subfolder named after its type (created if needed). "
            f"Existing folders and their contents are never touched.\n\nProceed?"
        )
        if not confirm:
            return

        result, error = organize_folder_by_type(target_path)
        if error:
            messagebox.showerror("❌ Error", error)
            return

        conflict_note = f"\n\n⚠️ {len(result['conflicts'])} file(s) skipped due to name conflicts or errors." if result["conflicts"] else ""
        messagebox.showinfo(
            "✅ Organized",
            f"Moved {result['moved']} file(s) into: {', '.join(result['categories'])}{conflict_note}"
        )
        if target_path == self.current_path:
            self.navigate_to(self.current_path)


def main():
    root = tk.Tk()
    app = FileManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
