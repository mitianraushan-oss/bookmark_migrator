"""
Bookmark Migrator - Extract and Import bookmarks from Chrome and Edge browsers
Allows you to backup bookmarks and restore them on a new computer
"""

import json
import os
import shutil
import subprocess
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from urllib.parse import urlparse
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
        """Recursively extract bookmarks from the bookmark tree, preserving structure"""
        if node.get('type') == 'url':
            bookmark_entry = {
                'name': node.get('name', 'Untitled'),
                'url': node.get('url', ''),
                'type': 'url'
            }
            if 'date_added' in node:
                bookmark_entry['date_added'] = node.get('date_added')
            if 'id' in node:
                bookmark_entry['id'] = node.get('id')
            bookmarks_list.append(bookmark_entry)
        elif node.get('type') == 'folder':
            folder_data = {
                'name': node.get('name', 'Folder'),
                'type': 'folder',
                'children': []
            }
            # Copy other properties if they exist
            if 'date_added' in node:
                folder_data['date_added'] = node.get('date_added')
            if 'id' in node:
                folder_data['id'] = node.get('id')
            
            # Recursively extract children
            for child in node.get('children', []):
                self.extract_bookmarks_recursive(child, folder_data['children'])
            
            # Only add folder if it has children or no children at all (preserve structure)
            bookmarks_list.append(folder_data)
    
    def remove_empty_folders(self, items):
        """Recursively remove empty folders from bookmarks"""
        cleaned_items = []
        
        for item in items:
            if item.get('type') == 'folder':
                # Recursively clean children
                if item.get('children'):
                    cleaned_children = self.remove_empty_folders(item['children'])
                    item['children'] = cleaned_children
                
                # Only keep folder if it has children
                if item.get('children') and len(item['children']) > 0:
                    cleaned_items.append(item)
            else:
                # Keep all bookmarks
                cleaned_items.append(item)
        
        return cleaned_items
    
    def check_export_file(self, import_file):
        """Check and display what's in an export file"""
        if not os.path.exists(import_file):
            return False, "File not found"
        
        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                bookmarks = json.load(f)
            
            def count_items(items):
                """Count bookmarks and folders recursively"""
                bookmark_count = 0
                folder_count = 0
                
                for item in items:
                    if item.get('type') == 'url':
                        bookmark_count += 1
                    elif item.get('type') == 'folder':
                        folder_count += 1
                        # Count nested items
                        if item.get('children'):
                            nested_bm, nested_fo = count_items(item['children'])
                            bookmark_count += nested_bm
                            folder_count += nested_fo
                
                return bookmark_count, folder_count
            
            bm_count, folder_count = count_items(bookmarks)
            return True, f"✅ Found {bm_count} bookmarks in {folder_count} folders"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
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
    
    def import_bookmarks_to_browser(self, browser_type, import_file, import_to_bar=False):
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
        
        # Create directories if they don't exist (for new computer setup)
        bookmark_dir = os.path.dirname(bookmark_file)
        os.makedirs(bookmark_dir, exist_ok=True)
        
        # If bookmarks file doesn't exist, create a default structure
        if not os.path.exists(bookmark_file):
            default_bookmarks = {
                "checksum": "00000000000000000000000000000000",
                "roots": {
                    "bookmark_bar": {
                        "children": [],
                        "date_added": "13000000000000000",
                        "date_modified": "0",
                        "id": "1",
                        "name": "Bookmarks bar",
                        "type": "folder"
                    },
                    "other": {
                        "children": [],
                        "date_added": "13000000000000000",
                        "date_modified": "0",
                        "id": "2",
                        "name": "Other bookmarks",
                        "type": "folder"
                    },
                    "synced": {
                        "children": [],
                        "date_added": "13000000000000000",
                        "date_modified": "0",
                        "id": "3",
                        "name": "Mobile bookmarks",
                        "type": "folder"
                    }
                },
                "version": 1
            }
            try:
                with open(bookmark_file, 'w', encoding='utf-8') as f:
                    json.dump(default_bookmarks, f, indent=2, ensure_ascii=False)
            except Exception as e:
                return False, f"Error creating bookmark file: {str(e)}"
        
        # Backup existing bookmarks
        backup_file = bookmark_file + ".backup"
        try:
            if os.path.exists(bookmark_file):
                shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up existing bookmarks: {str(e)}"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Determine target folder
            target_folder = "bookmark_bar" if import_to_bar else "other"
            
            # Add imported bookmarks to target folder, avoiding duplicates
            if 'roots' in existing_data and target_folder in existing_data['roots']:
                if 'children' not in existing_data['roots'][target_folder]:
                    existing_data['roots'][target_folder]['children'] = []
                
                # Get existing URLs to avoid duplicates
                existing_urls = set()
                existing_names = {}
                
                def collect_existing(node, folder_name=""):
                    if node.get('type') == 'url':
                        existing_urls.add(node.get('url', ''))
                        key = (node.get('name', ''), node.get('url', ''))
                        existing_names[key] = True
                    elif node.get('type') == 'folder':
                        for child in node.get('children', []):
                            collect_existing(child, node.get('name', ''))
                
                # Collect existing bookmarks from target folder
                for child in existing_data['roots'][target_folder]['children']:
                    collect_existing(child)
                
                # Count added bookmarks
                added_count = 0
                duplicate_count = 0
                
                # Add imported bookmarks, skip duplicates
                for item in imported_bookmarks:
                    if self._has_duplicate(item, existing_urls, existing_names):
                        duplicate_count += 1
                    else:
                        existing_data['roots'][target_folder]['children'].append(item)
                        self._add_to_existing(item, existing_urls)
                        added_count += 1
                
                # Update checksum (Chrome validates this)
                existing_data['checksum'] = "00000000000000000000000000000000"
                
                # Clean up empty folders
                existing_data['roots'][target_folder]['children'] = self.remove_empty_folders(
                    existing_data['roots'][target_folder]['children']
                )
            
            with open(bookmark_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            dup_msg = f" ({duplicate_count} duplicates skipped)" if duplicate_count > 0 else ""
            return True, f"✅ Imported {added_count} bookmarks to {browser_name}{dup_msg}!"
        except Exception as e:
            return False, f"Error preparing bookmarks: {str(e)}"
    
    def _has_duplicate(self, item, existing_urls, existing_names):
        """Check if bookmark already exists (for duplicates prevention)"""
        if item.get('type') == 'url':
            url = item.get('url', '')
            if url in existing_urls:
                return True
        return False
    
    def _add_to_existing(self, item, existing_urls):
        """Add URLs from imported item to existing set"""
        if item.get('type') == 'url':
            existing_urls.add(item.get('url', ''))
        elif item.get('type') == 'folder':
            for child in item.get('children', []):
                self._add_to_existing(child, existing_urls)
    
    def is_browser_running(self, browser_type):
        """Check via tasklist whether the browser process is still running
        (Edge/Chrome can keep running in the background even after all windows are closed)"""
        process_name = "msedge.exe" if browser_type == "edge" else "chrome.exe"
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return process_name.lower() in result.stdout.lower()
        except Exception:
            return False

    def close_browser_processes(self, browser_type, timeout=10):
        """Force-close all instances of the browser (including background processes)"""
        process_name = "msedge.exe" if browser_type == "edge" else "chrome.exe"
        try:
            subprocess.run(
                ["taskkill", "/IM", process_name, "/F", "/T"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass
        
        # Wait for the process to actually exit before we touch the Bookmarks file
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.is_browser_running(browser_type):
                return True
            time.sleep(0.5)
        return not self.is_browser_running(browser_type)

    def clean_empty_bookmarks_folders(self, browser_type):
        """Clean empty folders from bookmarks in Chrome or Edge"""
        if browser_type == "chrome":
            bookmark_file = self.chrome_bookmark_path
            browser_name = "Chrome"
        else:
            bookmark_file = self.edge_bookmark_path
            browser_name = "Edge"
        
        if not os.path.exists(bookmark_file):
            return False, f"{browser_name} bookmarks file not found"
        
        if self.is_browser_running(browser_type):
            return False, (
                f"{browser_name} is still running (possibly in the background) and will "
                f"overwrite this file with its in-memory bookmarks, undoing the cleanup. "
                f"Please fully quit {browser_name} (check the system tray / Task Manager, "
                f"and disable 'Continue running background apps') before cleaning."
            )
        
        # Backup existing bookmarks
        backup_file = bookmark_file + ".backup"
        try:
            shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up bookmarks: {str(e)}"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Clean all root folders
            for root_key in ['bookmark_bar', 'other', 'synced']:
                if root_key in existing_data['roots']:
                    if 'children' in existing_data['roots'][root_key]:
                        cleaned = self.remove_empty_folders(existing_data['roots'][root_key]['children'])
                        existing_data['roots'][root_key]['children'] = cleaned
            
            # Update checksum
            existing_data['checksum'] = "00000000000000000000000000000000"
            
            with open(bookmark_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            return True, (
                f"✅ Empty folders cleaned! Backup saved to {backup_file}\n\n"
                f"⚠️ If Favorites/Bookmarks sync is signed in, the sync server still has the old "
                f"empty folders and may restore them on next launch. For a permanent fix, delete "
                f"empty folders via {browser_name}'s own favorites manager (so the deletion syncs), "
                f"or turn off sync before relying on this file-based cleanup."
            )
        except Exception as e:
            return False, f"Error cleaning folders: {str(e)}"

    def _walk_folders(self, children, path, out):
        """Collect every folder node with a reference to its parent children list (for in-place removal)"""
        for node in children:
            if node.get('type') == 'folder':
                out.append({'node': node, 'parent': children, 'path': path})
                self._walk_folders(node.get('children', []), path + [node.get('name', '')], out)

    def _walk_urls(self, children, path, out):
        """Collect every bookmark (url) node with a reference to its parent children list"""
        for node in children:
            if node.get('type') == 'url':
                out.append({'node': node, 'parent': children, 'path': path})
            elif node.get('type') == 'folder':
                self._walk_urls(node.get('children', []), path + [node.get('name', '')], out)

    def find_duplicates(self, browser_type):
        """Preview duplicate bookmark URLs and duplicate-named folders without modifying anything"""
        bookmark_file = self.chrome_bookmark_path if browser_type == "chrome" else self.edge_bookmark_path
        browser_name = "Chrome" if browser_type == "chrome" else "Edge"
        
        if not os.path.exists(bookmark_file):
            return None, f"{browser_name} bookmarks file not found"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return None, f"Error reading bookmarks: {str(e)}"
        
        all_folders, all_urls = [], []
        for root_key in ['bookmark_bar', 'other', 'synced']:
            root = data.get('roots', {}).get(root_key)
            if root:
                self._walk_folders(root.get('children', []), [root_key], all_folders)
                self._walk_urls(root.get('children', []), [root_key], all_urls)
        
        url_groups = {}
        for entry in all_urls:
            url = (entry['node'].get('url') or '').strip()
            if url:
                url_groups.setdefault(url, []).append(entry)
        dup_urls = {u: v for u, v in url_groups.items() if len(v) > 1}
        
        name_groups = {}
        for entry in all_folders:
            name = (entry['node'].get('name') or '').strip()
            if name:
                name_groups.setdefault(name, []).append(entry)
        dup_folders = {n: v for n, v in name_groups.items() if len(v) > 1}
        
        return {
            'duplicate_url_extra_count': sum(len(v) - 1 for v in dup_urls.values()),
            'duplicate_url_groups': len(dup_urls),
            'duplicate_folder_extra_count': sum(len(v) - 1 for v in dup_folders.values()),
            'duplicate_folder_groups': len(dup_folders),
        }, None

    def remove_duplicate_bookmarks(self, browser_type, merge_duplicate_folders=True):
        """Remove duplicate bookmark URLs (keeping the first occurrence) and, if requested,
        merge folders that share the same name (moving their children into the first one found)"""
        bookmark_file = self.chrome_bookmark_path if browser_type == "chrome" else self.edge_bookmark_path
        browser_name = "Chrome" if browser_type == "chrome" else "Edge"
        
        if not os.path.exists(bookmark_file):
            return False, f"{browser_name} bookmarks file not found"
        
        if self.is_browser_running(browser_type):
            return False, (
                f"{browser_name} is still running (possibly in the background) and will "
                f"overwrite this file with its in-memory bookmarks, undoing the cleanup. "
                f"Please fully quit {browser_name} before cleaning."
            )
        
        backup_file = bookmark_file + ".backup"
        try:
            shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up bookmarks: {str(e)}"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            merged_folder_count = 0
            if merge_duplicate_folders:
                all_folders = []
                for root_key in ['bookmark_bar', 'other', 'synced']:
                    root = data.get('roots', {}).get(root_key)
                    if root:
                        self._walk_folders(root.get('children', []), [root_key], all_folders)
                
                name_groups = {}
                for entry in all_folders:
                    name = (entry['node'].get('name') or '').strip()
                    if name:
                        name_groups.setdefault(name, []).append(entry)
                
                for name, entries in name_groups.items():
                    if len(entries) <= 1:
                        continue
                    keeper = entries[0]['node']
                    for dup_entry in entries[1:]:
                        dup_node = dup_entry['node']
                        keeper.setdefault('children', []).extend(dup_node.get('children', []))
                        dup_entry['parent'][:] = [c for c in dup_entry['parent'] if c is not dup_node]
                        merged_folder_count += 1
            
            # Re-walk since folder merging may have moved bookmarks around
            all_urls = []
            for root_key in ['bookmark_bar', 'other', 'synced']:
                root = data.get('roots', {}).get(root_key)
                if root:
                    self._walk_urls(root.get('children', []), [root_key], all_urls)
            
            url_groups = {}
            for entry in all_urls:
                url = (entry['node'].get('url') or '').strip()
                if url:
                    url_groups.setdefault(url, []).append(entry)
            
            removed_url_count = 0
            for url, entries in url_groups.items():
                if len(entries) <= 1:
                    continue
                for dup_entry in entries[1:]:
                    dup_node = dup_entry['node']
                    dup_entry['parent'][:] = [c for c in dup_entry['parent'] if c is not dup_node]
                    removed_url_count += 1
            
            # Merging/removal can leave newly-empty folders behind
            for root_key in ['bookmark_bar', 'other', 'synced']:
                if root_key in data['roots'] and 'children' in data['roots'][root_key]:
                    data['roots'][root_key]['children'] = self.remove_empty_folders(
                        data['roots'][root_key]['children']
                    )
            
            data['checksum'] = "00000000000000000000000000000000"
            
            with open(bookmark_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True, (
                f"✅ Removed {removed_url_count} duplicate bookmark(s) and merged {merged_folder_count} "
                f"duplicate-named folder(s). Backup saved to {backup_file}"
            )
        except Exception as e:
            return False, f"Error removing duplicates: {str(e)}"

    def _domain_folder_name(self, url):
        """Derive a grouping folder name (site domain) from a bookmark URL"""
        try:
            netloc = urlparse(url).netloc.lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            return netloc or 'Other'
        except Exception:
            return 'Other'

    def _next_id_generator(self, data):
        """Generate unique, ever-increasing string ids for new bookmark nodes"""
        max_id = [0]
        
        def scan(node):
            try:
                max_id[0] = max(max_id[0], int(node.get('id', 0)))
            except (TypeError, ValueError):
                pass
            for child in node.get('children', []):
                scan(child)
        
        for root_key in ['bookmark_bar', 'other', 'synced']:
            root = data.get('roots', {}).get(root_key)
            if root:
                scan(root)
        
        def next_id():
            max_id[0] += 1
            return str(max_id[0])
        
        return next_id

    def find_loose_bookmarks(self, browser_type):
        """Preview bookmarks sitting directly under a root, not inside any folder"""
        bookmark_file = self.chrome_bookmark_path if browser_type == "chrome" else self.edge_bookmark_path
        browser_name = "Chrome" if browser_type == "chrome" else "Edge"
        
        if not os.path.exists(bookmark_file):
            return None, f"{browser_name} bookmarks file not found"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return None, f"Error reading bookmarks: {str(e)}"
        
        by_root = {}
        for root_key in ['bookmark_bar', 'other', 'synced']:
            root = data.get('roots', {}).get(root_key)
            if root:
                count = sum(1 for c in root.get('children', []) if c.get('type') == 'url')
                if count:
                    by_root[root_key] = count
        
        return {'total_loose': sum(by_root.values()), 'by_root': by_root}, None

    def organize_loose_bookmarks(self, browser_type):
        """Move bookmarks sitting directly under a root into new/existing folders
        grouped by site domain, leaving bookmarks already inside folders untouched"""
        bookmark_file = self.chrome_bookmark_path if browser_type == "chrome" else self.edge_bookmark_path
        browser_name = "Chrome" if browser_type == "chrome" else "Edge"
        
        if not os.path.exists(bookmark_file):
            return False, f"{browser_name} bookmarks file not found"
        
        if self.is_browser_running(browser_type):
            return False, (
                f"{browser_name} is still running (possibly in the background) and will "
                f"overwrite this file with its in-memory bookmarks. Please fully quit "
                f"{browser_name} before organizing."
            )
        
        backup_file = bookmark_file + ".backup"
        try:
            shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up bookmarks: {str(e)}"
        
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            next_id = self._next_id_generator(data)
            moved_count = 0
            created_folders = 0
            
            for root_key in ['bookmark_bar', 'other', 'synced']:
                root = data.get('roots', {}).get(root_key)
                if not root or 'children' not in root:
                    continue
                
                children = root['children']
                loose_urls = [c for c in children if c.get('type') == 'url']
                if not loose_urls:
                    continue
                
                existing_folders = {c.get('name'): c for c in children if c.get('type') == 'folder'}
                
                domain_groups = {}
                for node in loose_urls:
                    domain = self._domain_folder_name(node.get('url', ''))
                    domain_groups.setdefault(domain, []).append(node)
                
                for domain, nodes in domain_groups.items():
                    if domain in existing_folders:
                        existing_folders[domain].setdefault('children', []).extend(nodes)
                    else:
                        new_folder = {
                            'type': 'folder',
                            'id': next_id(),
                            'name': domain,
                            'date_added': str(int((time.time() + 11644473600) * 1000000)),
                            'children': nodes
                        }
                        children.append(new_folder)
                        existing_folders[domain] = new_folder
                        created_folders += 1
                    moved_count += len(nodes)
                
                loose_ids = {id(n) for n in loose_urls}
                root['children'] = [c for c in children if not (c.get('type') == 'url' and id(c) in loose_ids)]
            
            data['checksum'] = "00000000000000000000000000000000"
            
            with open(bookmark_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True, (
                f"✅ Organized {moved_count} loose bookmark(s) into {created_folders} new domain "
                f"folder(s) (plus any matching existing folders). Backup saved to {backup_file}\n\n"
                f"You can rename these folders or move bookmarks around manually afterward."
            )
        except Exception as e:
            return False, f"Error organizing bookmarks: {str(e)}"


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
        ttk.Button(import_frame, text="✓ Verify Export File", 
                  command=self.verify_export_file).pack(side="left", padx=5)
        
        # Cleanup Section
        cleanup_frame = ttk.LabelFrame(self.root, text="🧹 Cleanup", padding=10)
        cleanup_frame.pack(pady=10, padx=10, fill="both", expand=False)
        
        ttk.Button(cleanup_frame, text="🧹 Clean Empty Folders", 
                  command=self.clean_empty_folders_prompt).pack(side="left", padx=5)
        ttk.Button(cleanup_frame, text="🔁 Remove Duplicate Bookmarks", 
                  command=self.remove_duplicates_prompt).pack(side="left", padx=5)
        ttk.Button(cleanup_frame, text="📂 Organize Loose Bookmarks", 
                  command=self.organize_loose_bookmarks_prompt).pack(side="left", padx=5)
        
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
4. Choose import location (Bookmarks Bar or Other Bookmarks)
5. Close your browser completely when prompted
6. Empty folders will be automatically cleaned up
7. Restart the browser to see the imported bookmarks

ADDITIONAL FEATURES:
- "Verify Export File" - Check if export file has bookmarks before importing
- "Clean Empty Folders" - Manually remove empty bookmark folders
- "Remove Duplicate Bookmarks" - Keep only 1 copy of each URL and merge folders that share a name (asks for confirmation first)
- "Organize Loose Bookmarks" - Groups bookmarks sitting directly in the bar/other/synced roots (not inside any folder) into new folders named after their site domain, so you can rename/rearrange them afterward

IMPORTANT:
- Always close the browser before importing
- A backup of existing bookmarks will be created automatically
- Empty folders are automatically removed during import"""
        
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
        
        # Ask where to import
        location = messagebox.askquestion(
            "📍 Import Location",
            "Where do you want to import bookmarks?\n\n"
            "Click 'Yes' → Bookmarks Bar (Easy Access)\n"
            "Click 'No' → Other Bookmarks (Organized)",
            icon='question'
        )
        
        import_to_bar = (location == 'yes')
        
        if not self._ensure_browser_closed(browser_type):
            return
        
        success, message = self.migrator.import_bookmarks_to_browser(browser_type, import_file, import_to_bar)
        self.status_var.set(message)
        
        if success:
            location_text = "Bookmarks Bar" if import_to_bar else "Other Bookmarks"
            messagebox.showinfo("✅ Complete", 
                             f"{message}\n\n"
                             f"Bookmarks added to: {location_text}\n"
                             f"Now restart {browser_type.upper()} to see your bookmarks.")
        else:
            messagebox.showerror("❌ Error", message)
    
    def verify_export_file(self):
        """Verify contents of an export file"""
        import_file = filedialog.askopenfilename(
            title="Select export file to verify",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=self.migrator.export_dir
        )
        
        if not import_file:
            return
        
        success, message = self.migrator.check_export_file(import_file)
        self.status_var.set(message)
        
        if success:
            messagebox.showinfo("✓ Export File Verified", message)
        else:
            messagebox.showerror("❌ Error", message)
    
    def clean_empty_folders_prompt(self):
        """Prompt to clean empty folders from bookmarks"""
        # Ask which browser
        response = messagebox.askquestion(
            "🧹 Clean Empty Folders",
            "Which browser do you want to clean?\n\n"
            "Click 'Yes' → Chrome\n"
            "Click 'No' → Edge",
            icon='question'
        )
        
        browser_type = "chrome" if response == 'yes' else "edge"
        
        if not self._ensure_browser_closed(browser_type):
            return
        
        success, message = self.migrator.clean_empty_bookmarks_folders(browser_type)
        self.status_var.set(message)
        
        if success:
            messagebox.showinfo("✅ Cleaned", message)
        else:
            messagebox.showerror("❌ Error", message)
    
    def remove_duplicates_prompt(self):
        """Prompt to preview and remove duplicate bookmarks / merge duplicate-named folders"""
        response = messagebox.askquestion(
            "🔁 Remove Duplicate Bookmarks",
            "Which browser do you want to check?\n\n"
            "Click 'Yes' → Chrome\n"
            "Click 'No' → Edge",
            icon='question'
        )
        browser_type = "chrome" if response == 'yes' else "edge"
        
        if not self._ensure_browser_closed(browser_type):
            return
        
        preview, error = self.migrator.find_duplicates(browser_type)
        if error:
            messagebox.showerror("❌ Error", error)
            return
        
        if preview['duplicate_url_extra_count'] == 0 and preview['duplicate_folder_extra_count'] == 0:
            messagebox.showinfo("✅ No Duplicates", f"No duplicate bookmarks or folders found in {browser_type.upper()}.")
            return
        
        confirm = messagebox.askyesno(
            "⚠️ Confirm Cleanup",
            f"Found in {browser_type.upper()}:\n\n"
            f"• {preview['duplicate_url_extra_count']} duplicate bookmark(s) across "
            f"{preview['duplicate_url_groups']} URL(s) — only the first copy of each will be kept.\n\n"
            f"• {preview['duplicate_folder_extra_count']} duplicate folder(s) sharing a name across "
            f"{preview['duplicate_folder_groups']} name(s) — their contents will be merged into the "
            f"first folder found, and the extra empty folders removed.\n\n"
            f"Proceed with cleanup?"
        )
        
        if not confirm:
            return
        
        success, message = self.migrator.remove_duplicate_bookmarks(browser_type, merge_duplicate_folders=True)
        self.status_var.set(message)
        
        if success:
            messagebox.showinfo("✅ Cleaned", message)
        else:
            messagebox.showerror("❌ Error", message)
    
    def organize_loose_bookmarks_prompt(self):
        """Prompt to preview and organize loose (not-in-a-folder) bookmarks into domain folders"""
        response = messagebox.askquestion(
            "📂 Organize Loose Bookmarks",
            "Which browser do you want to organize?\n\n"
            "Click 'Yes' → Chrome\n"
            "Click 'No' → Edge",
            icon='question'
        )
        browser_type = "chrome" if response == 'yes' else "edge"
        
        if not self._ensure_browser_closed(browser_type):
            return
        
        preview, error = self.migrator.find_loose_bookmarks(browser_type)
        if error:
            messagebox.showerror("❌ Error", error)
            return
        
        if preview['total_loose'] == 0:
            messagebox.showinfo("✅ Nothing To Do", f"No loose bookmarks found outside folders in {browser_type.upper()}.")
            return
        
        breakdown = "\n".join(f"  • {root}: {count}" for root, count in preview['by_root'].items())
        confirm = messagebox.askyesno(
            "⚠️ Confirm Organize",
            f"Found {preview['total_loose']} bookmark(s) not inside any folder in {browser_type.upper()}:\n\n"
            f"{breakdown}\n\n"
            f"They will be grouped into new folders named after each bookmark's site domain "
            f"(e.g. 'github.com'). You can rename/rearrange these folders afterward.\n\n"
            f"Proceed?"
        )
        
        if not confirm:
            return
        
        success, message = self.migrator.organize_loose_bookmarks(browser_type)
        self.status_var.set(message)
        
        if success:
            messagebox.showinfo("✅ Organized", message)
        else:
            messagebox.showerror("❌ Error", message)
    
    def _ensure_browser_closed(self, browser_type):
        """Verify (and if needed, force-close) the browser process so it can't overwrite
        the Bookmarks file after we edit it. Returns True if safe to proceed."""
        if not self.migrator.is_browser_running(browser_type):
            return True
        
        confirm = messagebox.askyesno(
            "⚠️ Browser Still Running",
            f"{browser_type.upper()} is still running (it may be in the background/system tray).\n\n"
            f"If it stays open, it will overwrite this file when it eventually closes, undoing "
            f"any changes.\n\n"
            f"Click 'Yes' to force-close {browser_type.upper()} now and continue, or 'No' to cancel."
        )
        
        if not confirm:
            return False
        
        closed = self.migrator.close_browser_processes(browser_type)
        if not closed:
            messagebox.showerror(
                "❌ Error",
                f"Could not fully close {browser_type.upper()}. Please close it manually "
                f"(check Task Manager) and try again."
            )
            return False
        
        return True
    
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
