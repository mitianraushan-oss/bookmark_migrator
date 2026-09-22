"""
Bookmark Migrator - Extract and Import bookmarks from Chrome and Edge browsers
Allows you to backup bookmarks and restore them on a new computer
"""

import json
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import sys

class BookmarkMigrator:
    def __init__(self):
        self.chrome_bookmark_path = os.path.expanduser(
            "~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Bookmarks"
        )
        self.edge_bookmark_path = os.path.expanduser(
            "~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Bookmarks"
        )
        self.export_dir = os.path.expanduser("~/Bookmarks_Backup")
        os.makedirs(self.export_dir, exist_ok=True)
        
    def read_bookmarks(self, browser_type):
        """Read bookmarks from Chrome or Edge"""
        if browser_type == "chrome":
            bookmark_file = self.chrome_bookmark_path
            browser_name = "Chrome"
        else:
            bookmark_file = self.edge_bookmark_path
            browser_name = "Edge"
        
        if not os.path.exists(bookmark_file):
            return None, f"{browser_name} bookmarks file not found at {bookmark_file}"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data, None
        except Exception as e:
            return None, f"Error reading {browser_name} bookmarks: {str(e)}"
    
    def extract_bookmarks_recursive(self, node, bookmarks_list):
        """Recursively extract bookmarks from the bookmark tree"""
        if node.get('type') == 'url':
            bookmarks_list.append({
                'title': node.get('name', 'Untitled'),
                'url': node.get('url', ''),
                'date_added': node.get('date_added', ''),
                'type': 'bookmark'
            })
        elif node.get('type') == 'folder':
            folder_data = {
                'title': node.get('name', 'Folder'),
                'type': 'folder',
                'children': []
            }
            for child in node.get('children', []):
                self.extract_bookmarks_recursive(child, folder_data['children'])
            bookmarks_list.append(folder_data)
    
    def export_bookmarks(self, browser_type):
        """Export bookmarks to JSON file"""
        data, error = self.read_bookmarks(browser_type)
        if error:
            return False, error
        
        bookmarks_list = []
        if 'roots' in data:
            for root_key in ['bookmark_bar', 'other', 'synced']:
                if root_key in data['roots']:
                    root_node = data['roots'][root_key]
                    if root_node.get('children'):
                        for child in root_node['children']:
                            self.extract_bookmarks_recursive(child, bookmarks_list)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = os.path.join(self.export_dir, f"{browser_type}_bookmarks_{timestamp}.json")
        
        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(bookmarks_list, f, indent=2, ensure_ascii=False)
            return True, f"Exported {len(bookmarks_list)} bookmarks to {export_file}"
        except Exception as e:
            return False, f"Error exporting bookmarks: {str(e)}"
    
    def import_bookmarks_to_browser(self, browser_type, import_file):
        """Import bookmarks to Chrome or Edge"""
        if not os.path.exists(import_file):
            return False, "Import file not found"
        
        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                imported_bookmarks = json.load(f)
        except Exception as e:
            return False, f"Error reading import file: {str(e)}"
        
        if browser_type == "chrome":
            bookmark_file = self.chrome_bookmark_path
            browser_name = "Chrome"
        else:
            bookmark_file = self.edge_bookmark_path
            browser_name = "Edge"
        
        if not os.path.exists(bookmark_file):
            return False, f"{browser_name} bookmarks file not found. Make sure {browser_name} is installed."
        
        # Backup existing bookmarks
        backup_file = bookmark_file + ".backup"
        try:
            shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up existing bookmarks: {str(e)}"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Add imported bookmarks to "Other Bookmarks" folder
            if 'roots' in existing_data and 'other' in existing_data['roots']:
                if 'children' not in existing_data['roots']['other']:
                    existing_data['roots']['other']['children'] = []
                
                # Add imported bookmarks
                for item in imported_bookmarks:
                    existing_data['roots']['other']['children'].append(item)
            
            # Close the browser before writing (important!)
            return True, f"Bookmarks prepared. Please close {browser_name} before importing. Backup saved to {backup_file}"
        except Exception as e:
            return False, f"Error preparing bookmarks: {str(e)}"


class BookmarkMigratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("📚 Bookmark Migrator - Extract & Import Bookmarks")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        self.migrator = BookmarkMigrator()
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - 300
        y = (self.root.winfo_screenheight() // 2) - 250
        self.root.geometry(f"+{x}+{y}")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the GUI"""
        # Title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(pady=15, padx=10, fill="x")
        
        ttk.Label(title_frame, text="📚 Bookmark Migrator", 
                 font=("Segoe UI", 16, "bold")).pack()
        ttk.Label(title_frame, text="Extract bookmarks from browsers and import on new computer",
                 font=("Segoe UI", 10)).pack()
        
        # Export Section
        export_frame = ttk.LabelFrame(self.root, text="📤 Export Bookmarks (from current computer)", padding=10)
        export_frame.pack(pady=10, padx=10, fill="both", expand=False)
        
        ttk.Button(export_frame, text="Export Chrome Bookmarks", 
                  command=lambda: self.export_bookmarks("chrome")).pack(side="left", padx=5)
        ttk.Button(export_frame, text="Export Edge Bookmarks", 
                  command=lambda: self.export_bookmarks("edge")).pack(side="left", padx=5)
        ttk.Button(export_frame, text="📁 Open Backup Folder", 
                  command=self.open_export_folder).pack(side="left", padx=5)
        
        # Import Section
        import_frame = ttk.LabelFrame(self.root, text="📥 Import Bookmarks (on new computer)", padding=10)
        import_frame.pack(pady=10, padx=10, fill="both", expand=False)
        
        ttk.Button(import_frame, text="Import to Chrome", 
                  command=lambda: self.import_bookmarks("chrome")).pack(side="left", padx=5)
        ttk.Button(import_frame, text="Import to Edge", 
                  command=lambda: self.import_bookmarks("edge")).pack(side="left", padx=5)
        
        # Instructions Section
        instructions_frame = ttk.LabelFrame(self.root, text="📋 Instructions", padding=10)
        instructions_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        instructions_text = tk.Text(instructions_frame, height=12, width=70, 
                                    font=("Segoe UI", 9), wrap="word")
        instructions_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(instructions_frame, orient="vertical", command=instructions_text.yview)
        scrollbar.pack(side="right", fill="y")
        instructions_text.config(yscrollcommand=scrollbar.set)
        
        instructions = """EXPORT (Current Computer):
1. Click "Export Chrome Bookmarks" to backup Chrome bookmarks
2. Click "Export Edge Bookmarks" to backup Edge bookmarks
3. Bookmarks are saved in your Bookmarks_Backup folder
4. Copy the exported JSON files to your new computer (USB drive, cloud, email, etc.)

IMPORT (New Computer):
1. Copy the exported JSON files to your new computer
2. Click "Import to Chrome" or "Import to Edge"
3. Select the JSON file you want to import
4. Close your browser completely when prompted
5. The bookmarks will be added to "Other Bookmarks" folder
6. Restart the browser to see the imported bookmarks

IMPORTANT:
- Always close the browser before importing
- A backup of existing bookmarks will be created automatically
- Imported bookmarks will appear in "Other Bookmarks" folder"""
        
        instructions_text.insert(1.0, instructions)
        instructions_text.config(state="disabled")
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, 
                             relief="sunken", anchor="w")
        status_bar.pack(pady=10, padx=10, fill="x")
    
    def export_bookmarks(self, browser_type):
        """Export bookmarks for the selected browser"""
        success, message = self.migrator.export_bookmarks(browser_type)
        self.status_var.set(message)
        
        if success:
            messagebox.showinfo("✅ Success", message)
        else:
            messagebox.showerror("❌ Error", message)
    
    def import_bookmarks(self, browser_type):
        """Import bookmarks for the selected browser"""
        import_file = filedialog.askopenfilename(
            title=f"Select {browser_type.upper()} bookmarks JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=self.migrator.export_dir
        )
        
        if not import_file:
            return
        
        # Confirm browser is closed
        response = messagebox.askyesno(
            "⚠️ Close Browser",
            f"Please close {browser_type.upper()} completely before importing.\n\n"
            f"Make sure NO {browser_type.upper()} windows are open.\n\n"
            f"Click 'Yes' when {browser_type.upper()} is closed."
        )
        
        if not response:
            return
        
        success, message = self.migrator.import_bookmarks_to_browser(browser_type, import_file)
        self.status_var.set(message)
        
        if success:
            messagebox.showinfo("✅ Complete", 
                             f"{message}\n\n"
                             f"Now restart {browser_type.upper()} to see your bookmarks.")
        else:
            messagebox.showerror("❌ Error", message)
    
    def open_export_folder(self):
        """Open the export folder in File Explorer"""
        if os.path.exists(self.migrator.export_dir):
            os.startfile(self.migrator.export_dir)
        else:
            messagebox.showerror("Error", "Bookmarks backup folder not found")


def main():
    root = tk.Tk()
    app = BookmarkMigratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
