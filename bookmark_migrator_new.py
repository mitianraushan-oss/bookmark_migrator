"""
Bookmark Migrator - Extract and Import bookmarks from Chrome and Edge browsers
Allows you to backup bookmarks and restore them on a new computer
Cross-platform: Windows, macOS, and Linux (requires Python 3 + tkinter, no extra dependencies)
"""

import json
import os
import platform
import shutil
import subprocess
import threading
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from urllib.parse import urlparse
import urllib.request
import urllib.error
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

class BookmarkMigrator:
    def __init__(self):
        system = platform.system()
        if system == "Windows":
            self.chrome_bookmark_path = os.path.expanduser(
                r"~\AppData\Local\Google\Chrome\User Data\Default\Bookmarks"
            )
            self.edge_bookmark_path = os.path.expanduser(
                r"~\AppData\Local\Microsoft\Edge\User Data\Default\Bookmarks"
            )
        elif system == "Darwin":  # macOS
            self.chrome_bookmark_path = os.path.expanduser(
                "~/Library/Application Support/Google/Chrome/Default/Bookmarks"
            )
            self.edge_bookmark_path = os.path.expanduser(
                "~/Library/Application Support/Microsoft Edge/Default/Bookmarks"
            )
        else:  # Linux
            self.chrome_bookmark_path = os.path.expanduser(
                "~/.config/google-chrome/Default/Bookmarks"
            )
            self.edge_bookmark_path = os.path.expanduser(
                "~/.config/microsoft-edge/Default/Bookmarks"
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
        """Check whether the browser process is still running, cross-platform
        (Edge/Chrome can keep running in the background even after all windows are closed)"""
        system = platform.system()
        try:
            if system == "Windows":
                process_name = "msedge.exe" if browser_type == "edge" else "chrome.exe"
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
                return process_name.lower() in result.stdout.lower()
            else:
                names = ["Microsoft Edge", "msedge", "microsoft-edge"] if browser_type == "edge" \
                    else ["Google Chrome", "chrome", "google-chrome"]
                for name in names:
                    result = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout.strip():
                        return True
                return False
        except Exception:
            return False

    def close_browser_processes(self, browser_type, timeout=10):
        """Force-close all instances of the browser (including background processes), cross-platform"""
        system = platform.system()
        try:
            if system == "Windows":
                process_name = "msedge.exe" if browser_type == "edge" else "chrome.exe"
                subprocess.run(
                    ["taskkill", "/IM", process_name, "/F", "/T"],
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                names = ["Microsoft Edge", "msedge"] if browser_type == "edge" else ["Google Chrome", "google-chrome"]
                for name in names:
                    subprocess.run(["pkill", "-f", name], capture_output=True, text=True)
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

    ROOT_DISPLAY = {'bookmark_bar': 'Bookmarks Bar', 'other': 'Other Bookmarks', 'synced': 'Mobile Bookmarks'}

    def _load_bookmark_data(self, browser_type):
        bookmark_file = self.chrome_bookmark_path if browser_type == "chrome" else self.edge_bookmark_path
        browser_name = "Chrome" if browser_type == "chrome" else "Edge"
        if not os.path.exists(bookmark_file):
            return None, None, None, f"{browser_name} bookmarks file not found"
        try:
            with open(bookmark_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return None, None, None, f"Error reading bookmarks: {str(e)}"
        return data, bookmark_file, browser_name, None

    def search_bookmarks(self, browser_type, query):
        """Search bookmark titles/URLs (case-insensitive) across all folders"""
        data, _, _, error = self._load_bookmark_data(browser_type)
        if error:
            return None, error
        
        query_lower = query.strip().lower()
        results = []
        
        def walk(node, path_parts):
            for child in node.get('children', []):
                if child.get('type') == 'url':
                    name, url = child.get('name', ''), child.get('url', '')
                    if query_lower in name.lower() or query_lower in url.lower():
                        results.append({
                            'id': child.get('id', ''),
                            'name': name,
                            'url': url,
                            'path': ' / '.join(path_parts)
                        })
                elif child.get('type') == 'folder':
                    walk(child, path_parts + [child.get('name', '(unnamed)')])
        
        for root_key in ['bookmark_bar', 'other', 'synced']:
            root = data.get('roots', {}).get(root_key)
            if root:
                walk(root, [self.ROOT_DISPLAY[root_key]])
        
        return results, None

    def list_folder_paths(self, browser_type):
        """Return breadcrumb-style folder paths (e.g. 'Bookmarks Bar / Work / Projects') for a folder picker"""
        data, _, _, error = self._load_bookmark_data(browser_type)
        if error:
            return None, error
        
        paths = []
        
        def walk(node, path_parts):
            for child in node.get('children', []):
                if child.get('type') == 'folder':
                    new_path = path_parts + [child.get('name', '(unnamed)')]
                    paths.append(' / '.join(new_path))
                    walk(child, new_path)
        
        for root_key in ['bookmark_bar', 'other', 'synced']:
            root = data.get('roots', {}).get(root_key)
            if root:
                display = self.ROOT_DISPLAY[root_key]
                paths.append(display)
                walk(root, [display])
        
        return paths, None

    def add_bookmark_to_folder(self, browser_type, folder_path, name, url):
        """Add a new bookmark to an existing folder identified by its breadcrumb path"""
        data, bookmark_file, browser_name, error = self._load_bookmark_data(browser_type)
        if error:
            return False, error
        
        if self.is_browser_running(browser_type):
            return False, (
                f"{browser_name} is still running (possibly in the background) and will "
                f"overwrite this file with its in-memory bookmarks. Please fully quit "
                f"{browser_name} before adding bookmarks."
            )
        
        parts = [p.strip() for p in folder_path.split('/')]
        reverse_root = {v: k for k, v in self.ROOT_DISPLAY.items()}
        if not parts or parts[0] not in reverse_root:
            return False, f"Invalid folder path: {folder_path}"
        
        node = data['roots'][reverse_root[parts[0]]]
        for part in parts[1:]:
            match = next((c for c in node.get('children', []) if c.get('type') == 'folder' and c.get('name') == part), None)
            if not match:
                return False, f"Folder not found: {folder_path}"
            node = match
        
        backup_file = bookmark_file + ".backup"
        try:
            shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up bookmarks: {str(e)}"
        
        next_id = self._next_id_generator(data)
        new_bookmark = {
            'type': 'url',
            'id': next_id(),
            'name': name,
            'url': url,
            'date_added': str(int((time.time() + 11644473600) * 1000000))
        }
        node.setdefault('children', []).append(new_bookmark)
        data['checksum'] = "00000000000000000000000000000000"
        
        try:
            with open(bookmark_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return False, f"Error saving bookmarks: {str(e)}"
        
        return True, f"✅ Added '{name}' to {folder_path} in {browser_name}. Backup saved to {backup_file}"

    def update_bookmark(self, browser_type, bookmark_id, new_name=None, new_url=None):
        """Update the name and/or URL of an existing bookmark, identified by its stable id
        (used to fix broken/changed links found via search)"""
        data, bookmark_file, browser_name, error = self._load_bookmark_data(browser_type)
        if error:
            return False, error
        
        if self.is_browser_running(browser_type):
            return False, (
                f"{browser_name} is still running (possibly in the background) and will "
                f"overwrite this file with its in-memory bookmarks. Please fully quit "
                f"{browser_name} before editing bookmarks."
            )
        
        target = None
        
        def find(node):
            nonlocal target
            for child in node.get('children', []):
                if target is not None:
                    return
                if child.get('type') == 'url' and str(child.get('id', '')) == str(bookmark_id):
                    target = child
                    return
                elif child.get('type') == 'folder':
                    find(child)
        
        for root_key in ['bookmark_bar', 'other', 'synced']:
            if target is not None:
                break
            root = data.get('roots', {}).get(root_key)
            if root:
                find(root)
        
        if target is None:
            return False, "Bookmark not found (it may have been moved or removed since searching)."
        
        backup_file = bookmark_file + ".backup"
        try:
            shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up bookmarks: {str(e)}"
        
        if new_name is not None and new_name.strip():
            target['name'] = new_name.strip()
        if new_url is not None and new_url.strip():
            target['url'] = new_url.strip()
        data['checksum'] = "00000000000000000000000000000000"
        
        try:
            with open(bookmark_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return False, f"Error saving bookmarks: {str(e)}"
        
        return True, f"✅ Updated bookmark in {browser_name}. Backup saved to {backup_file}"

    def delete_bookmark(self, browser_type, bookmark_id):
        """Remove a single bookmark identified by its stable id"""
        data, bookmark_file, browser_name, error = self._load_bookmark_data(browser_type)
        if error:
            return False, error
        
        if self.is_browser_running(browser_type):
            return False, (
                f"{browser_name} is still running (possibly in the background) and will "
                f"overwrite this file with its in-memory bookmarks. Please fully quit "
                f"{browser_name} before removing bookmarks."
            )
        
        target_parent, target_node = None, None
        
        def find(node):
            nonlocal target_parent, target_node
            children = node.get('children', [])
            for child in children:
                if target_node is not None:
                    return
                if child.get('type') == 'url' and str(child.get('id', '')) == str(bookmark_id):
                    target_parent, target_node = children, child
                    return
                elif child.get('type') == 'folder':
                    find(child)
        
        for root_key in ['bookmark_bar', 'other', 'synced']:
            if target_node is not None:
                break
            root = data.get('roots', {}).get(root_key)
            if root:
                find(root)
        
        if target_node is None:
            return False, "Bookmark not found (it may have been moved or removed since searching)."
        
        backup_file = bookmark_file + ".backup"
        try:
            shutil.copy2(bookmark_file, backup_file)
        except Exception as e:
            return False, f"Error backing up bookmarks: {str(e)}"
        
        target_parent[:] = [c for c in target_parent if c is not target_node]
        data['checksum'] = "00000000000000000000000000000000"
        
        try:
            with open(bookmark_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return False, f"Error saving bookmarks: {str(e)}"
        
        return True, f"✅ Removed bookmark from {browser_name}. Backup saved to {backup_file}"

    @staticmethod
    def _check_single_url(url, timeout=6):
        """Check a single URL's reachability. Returns (status, code) where status is
        'ok', 'broken' (reachable but error response), 'error' (unreachable/timeout), or 'skipped'"""
        if not url or not url.lower().startswith(('http://', 'https://')):
            return 'skipped', None
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BookmarkChecker/1.0'}
        
        def request(method):
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.getcode()
        
        try:
            code = request('HEAD')
            return ('ok', code) if code < 400 else ('broken', code)
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 501):
                try:
                    code2 = request('GET')
                    return ('ok', code2) if code2 < 400 else ('broken', code2)
                except urllib.error.HTTPError as e2:
                    return 'broken', e2.code
                except Exception:
                    return 'error', e.code
            return ('ok', e.code) if e.code < 400 else ('broken', e.code)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ValueError):
            return 'error', None
        except Exception:
            return 'error', None

    def check_bookmark_links(self, browser_type, progress_callback=None, max_workers=10, timeout=6):
        """Check every bookmark's URL for reachability. Returns a list of bookmark dicts
        (id/name/url/path) each annotated with 'status' ('ok'/'broken'/'error'/'skipped') and 'code'"""
        bookmarks, error = self.search_bookmarks(browser_type, '')
        if error:
            return None, error
        
        total = len(bookmarks)
        done = 0
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_bm = {executor.submit(self._check_single_url, bm['url'], timeout): bm for bm in bookmarks}
            for future in as_completed(future_to_bm):
                bm = future_to_bm[future]
                status, code = future.result()
                results.append({**bm, 'status': status, 'code': code})
                done += 1
                if progress_callback:
                    progress_callback(done, total)
        
        return results, None

    def open_url_in_browser(self, browser_type, url):
        """Open a URL in the specified browser (Edge or Chrome), cross-platform,
        falling back to the OS default handler if the browser can't be located"""
        system = platform.system()
        
        if system == "Darwin":
            app_name = "Microsoft Edge" if browser_type == "edge" else "Google Chrome"
            try:
                subprocess.Popen(["open", "-a", app_name, url])
                return True, None
            except Exception as e:
                return False, str(e)
        
        if system == "Windows":
            candidates = {
                'edge': [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
                ],
                'chrome': [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                ],
            }
            for exe in candidates.get(browser_type, []):
                if os.path.exists(exe):
                    try:
                        subprocess.Popen([exe, url])
                        return True, None
                    except Exception as e:
                        return False, str(e)
            
            try:
                os.startfile(url)
                return True, None
            except Exception as e:
                return False, str(e)
        
        # Linux
        binary = "microsoft-edge" if browser_type == "edge" else "google-chrome"
        try:
            subprocess.Popen([binary, url])
            return True, None
        except Exception:
            try:
                subprocess.Popen(["xdg-open", url])
                return True, None
            except Exception as e:
                return False, str(e)


class BookmarkMigratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("📚 Bookmark Migrator - Extract & Import Bookmarks")
        self.root.geometry("680x620")
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
        
        # Manage Bookmarks Section
        manage_frame = ttk.LabelFrame(self.root, text="🔗 Manage Bookmarks", padding=10)
        manage_frame.pack(pady=10, padx=10, fill="both", expand=False)
        
        ttk.Button(manage_frame, text="🔎 Search Bookmarks", 
                  command=self.search_bookmarks_dialog).pack(side="left", padx=5)
        ttk.Button(manage_frame, text="➕ Add Bookmark to Folder", 
                  command=self.add_bookmark_dialog).pack(side="left", padx=5)
        ttk.Button(manage_frame, text="🩺 Check Broken Links", 
                  command=self.check_broken_links_dialog).pack(side="left", padx=5)
        
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
- "Search Bookmarks" - Find bookmarks by title or URL across all folders, open them, or edit a broken/changed URL
- "Add Bookmark to Folder" - Manually add a new bookmark into any existing folder
- "Check Broken Links" - Test every bookmark's URL and flag ones that return errors or can't be reached, so you can fix or remove them

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
    
    def search_bookmarks_dialog(self):
        """Open a dialog to search bookmarks by title/URL across all folders"""
        dialog = tk.Toplevel(self.root)
        dialog.title("🔎 Search Bookmarks")
        dialog.geometry("560x420")
        dialog.transient(self.root)
        
        top = ttk.Frame(dialog, padding=10)
        top.pack(fill="x")
        
        ttk.Label(top, text="Browser:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        browser_var = tk.StringVar(value="edge")
        browser_combo = ttk.Combobox(top, textvariable=browser_var, values=["edge", "chrome"], state="readonly", width=10)
        browser_combo.grid(row=0, column=1, padx=(0, 15))
        
        ttk.Label(top, text="Search:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        query_var = tk.StringVar()
        query_entry = ttk.Entry(top, textvariable=query_var, width=30)
        query_entry.grid(row=0, column=3, padx=(0, 10))
        query_entry.focus_set()
        
        results_frame = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        results_frame.pack(fill="both", expand=True)
        
        columns = ("name", "url", "path")
        tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        tree.heading("name", text="Name")
        tree.heading("url", text="URL")
        tree.heading("path", text="Folder")
        tree.column("name", width=140)
        tree.column("url", width=220)
        tree.column("path", width=160)
        tree.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.config(yscrollcommand=scrollbar.set)
        
        def do_search():
            query = query_var.get().strip()
            if not query:
                messagebox.showwarning("⚠️ Missing Input", "Enter something to search for.")
                return
            results, error = self.migrator.search_bookmarks(browser_var.get(), query)
            tree.delete(*tree.get_children())
            if error:
                messagebox.showerror("❌ Error", error)
                return
            if not results:
                messagebox.showinfo("No Results", f"No bookmarks matched '{query}'.")
                return
            for r in results:
                tree.insert("", "end", iid=str(r['id']), values=(r['name'], r['url'], r['path']))
        
        ttk.Button(top, text="Search", command=do_search).grid(row=0, column=4)
        query_entry.bind("<Return>", lambda e: do_search())
        
        def open_selected(event=None):
            selection = tree.selection()
            if not selection:
                return
            url = tree.item(selection[0], "values")[1]
            success, error = self.migrator.open_url_in_browser(browser_var.get(), url)
            if not success:
                messagebox.showerror("❌ Error", f"Could not open URL: {error}")
        
        tree.bind("<Double-1>", open_selected)
        
        def edit_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("⚠️ Nothing Selected", "Select a bookmark to edit first.")
                return
            bookmark_id = selection[0]
            current_name, current_url, _ = tree.item(bookmark_id, "values")
            self._open_edit_bookmark_dialog(browser_var.get(), bookmark_id, current_name, current_url,
                                             on_saved=lambda name, url: tree.item(bookmark_id, values=(name, url, tree.item(bookmark_id, "values")[2])))
        
        actions = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        actions.pack(fill="x")
        ttk.Button(actions, text=f"🌐 Open Selected in Browser", command=open_selected).pack(side="left")
        ttk.Button(actions, text="✏️ Edit Selected (fix broken URL)", command=edit_selected).pack(side="left", padx=(10, 0))
        ttk.Label(actions, text="  (or double-click a result)", font=("Segoe UI", 8)).pack(side="left")
    
    def add_bookmark_dialog(self):
        """Open a dialog to add a new bookmark into an existing folder"""
        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Add Bookmark to Folder")
        dialog.geometry("480x260")
        dialog.transient(self.root)
        
        form = ttk.Frame(dialog, padding=15)
        form.pack(fill="both", expand=True)
        
        ttk.Label(form, text="Browser:").grid(row=0, column=0, sticky="w", pady=5)
        browser_var = tk.StringVar(value="edge")
        browser_combo = ttk.Combobox(form, textvariable=browser_var, values=["edge", "chrome"], state="readonly", width=27)
        browser_combo.grid(row=0, column=1, pady=5, sticky="w")
        
        ttk.Label(form, text="Name:").grid(row=1, column=0, sticky="w", pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form, textvariable=name_var, width=40).grid(row=1, column=1, pady=5, sticky="w")
        
        ttk.Label(form, text="URL:").grid(row=2, column=0, sticky="w", pady=5)
        url_var = tk.StringVar()
        ttk.Entry(form, textvariable=url_var, width=40).grid(row=2, column=1, pady=5, sticky="w")
        
        ttk.Label(form, text="Folder:").grid(row=3, column=0, sticky="w", pady=5)
        folder_var = tk.StringVar()
        folder_combo = ttk.Combobox(form, textvariable=folder_var, values=[], state="readonly", width=37)
        folder_combo.grid(row=3, column=1, pady=5, sticky="w")
        
        def refresh_folders(*_):
            paths, error = self.migrator.list_folder_paths(browser_var.get())
            if error:
                folder_combo['values'] = []
                return
            folder_combo['values'] = paths
            if paths:
                folder_var.set(paths[0])
        
        browser_combo.bind("<<ComboboxSelected>>", refresh_folders)
        refresh_folders()
        
        def do_add():
            name, url, folder_path = name_var.get().strip(), url_var.get().strip(), folder_var.get()
            if not name or not url or not folder_path:
                messagebox.showwarning("⚠️ Missing Input", "Name, URL, and Folder are all required.")
                return
            if not self._ensure_browser_closed(browser_var.get()):
                return
            success, message = self.migrator.add_bookmark_to_folder(browser_var.get(), folder_path, name, url)
            if success:
                messagebox.showinfo("✅ Added", message)
                dialog.destroy()
            else:
                messagebox.showerror("❌ Error", message)
        
        ttk.Button(form, text="Add Bookmark", command=do_add).grid(row=4, column=1, pady=15, sticky="e")
    
    def _open_edit_bookmark_dialog(self, browser_type, bookmark_id, current_name, current_url, on_saved):
        """Small dialog to fix a broken/changed bookmark URL (or rename it) in place"""
        dialog = tk.Toplevel(self.root)
        dialog.title("✏️ Edit Bookmark")
        dialog.geometry("460x180")
        dialog.transient(self.root)
        
        form = ttk.Frame(dialog, padding=15)
        form.pack(fill="both", expand=True)
        
        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        name_var = tk.StringVar(value=current_name)
        ttk.Entry(form, textvariable=name_var, width=45).grid(row=0, column=1, pady=5, sticky="w")
        
        ttk.Label(form, text="URL:").grid(row=1, column=0, sticky="w", pady=5)
        url_var = tk.StringVar(value=current_url)
        ttk.Entry(form, textvariable=url_var, width=45).grid(row=1, column=1, pady=5, sticky="w")
        
        def do_save():
            new_name, new_url = name_var.get().strip(), url_var.get().strip()
            if not new_name or not new_url:
                messagebox.showwarning("⚠️ Missing Input", "Name and URL are both required.")
                return
            if not self._ensure_browser_closed(browser_type):
                return
            success, message = self.migrator.update_bookmark(browser_type, bookmark_id, new_name, new_url)
            if success:
                messagebox.showinfo("✅ Updated", message)
                on_saved(new_name, new_url)
                dialog.destroy()
            else:
                messagebox.showerror("❌ Error", message)
        
        ttk.Button(form, text="Save Changes", command=do_save).grid(row=2, column=1, pady=15, sticky="e")
    
    def check_broken_links_dialog(self):
        """Dialog to test every bookmark's URL and flag broken/unreachable ones"""
        dialog = tk.Toplevel(self.root)
        dialog.title("🩺 Check Broken Links")
        dialog.geometry("760x480")
        dialog.transient(self.root)
        
        top = ttk.Frame(dialog, padding=10)
        top.pack(fill="x")
        
        ttk.Label(top, text="Browser:").pack(side="left")
        browser_var = tk.StringVar(value="edge")
        browser_combo = ttk.Combobox(top, textvariable=browser_var, values=["edge", "chrome"], state="readonly", width=10)
        browser_combo.pack(side="left", padx=(5, 15))
        
        progress_var = tk.StringVar(value="Click Start to check all bookmark links")
        ttk.Label(top, textvariable=progress_var).pack(side="left", padx=(0, 15))
        
        start_btn = ttk.Button(top, text="▶ Start Check")
        start_btn.pack(side="left")
        
        results_frame = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        results_frame.pack(fill="both", expand=True)
        
        columns = ("name", "url", "path", "status")
        tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        tree.heading("name", text="Name")
        tree.heading("url", text="URL")
        tree.heading("path", text="Folder")
        tree.heading("status", text="Status")
        tree.column("name", width=150)
        tree.column("url", width=250)
        tree.column("path", width=150)
        tree.column("status", width=110)
        tree.tag_configure("broken", background="#ffd6d6")
        tree.tag_configure("error", background="#fff3cd")
        tree.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.config(yscrollcommand=scrollbar.set)
        
        result_queue = queue.Queue()
        
        def worker(browser_type):
            def progress_cb(done, total):
                result_queue.put(('progress', done, total))
            results, error = self.migrator.check_bookmark_links(browser_type, progress_callback=progress_cb)
            result_queue.put(('done', results, error))
        
        def poll_queue():
            try:
                while True:
                    item = result_queue.get_nowait()
                    if item[0] == 'progress':
                        _, done, total = item
                        progress_var.set(f"Checking... {done}/{total}")
                    elif item[0] == 'done':
                        _, results, error = item
                        start_btn.config(state="normal")
                        if error:
                            messagebox.showerror("❌ Error", error)
                            progress_var.set("Error")
                            return
                        tree.delete(*tree.get_children())
                        broken_count = 0
                        for r in results:
                            tags = ()
                            if r['status'] == 'broken':
                                tags, broken_count = ("broken",), broken_count + 1
                            elif r['status'] == 'error':
                                tags, broken_count = ("error",), broken_count + 1
                            status_text = f"{r['status']} ({r['code']})" if r.get('code') else r['status']
                            tree.insert("", "end", iid=str(r['id']), values=(r['name'], r['url'], r['path'], status_text), tags=tags)
                        progress_var.set(f"Done: {len(results)} checked, {broken_count} broken/unreachable")
                        return
            except queue.Empty:
                pass
            dialog.after(150, poll_queue)
        
        def start_check():
            start_btn.config(state="disabled")
            tree.delete(*tree.get_children())
            progress_var.set("Starting...")
            threading.Thread(target=worker, args=(browser_var.get(),), daemon=True).start()
            dialog.after(150, poll_queue)
        
        start_btn.config(command=start_check)
        
        def get_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("⚠️ Nothing Selected", "Select a bookmark first.")
                return None
            return selection[0]
        
        def open_selected():
            bid = get_selected()
            if not bid:
                return
            url = tree.item(bid, "values")[1]
            success, error = self.migrator.open_url_in_browser(browser_var.get(), url)
            if not success:
                messagebox.showerror("❌ Error", f"Could not open URL: {error}")
        
        def edit_selected():
            bid = get_selected()
            if not bid:
                return
            name, url, path, status = tree.item(bid, "values")
            self._open_edit_bookmark_dialog(
                browser_var.get(), bid, name, url,
                on_saved=lambda n, u: tree.item(bid, values=(n, u, path, "unchecked - re-run to verify"), tags=())
            )
        
        def remove_selected():
            bid = get_selected()
            if not bid:
                return
            name = tree.item(bid, "values")[0]
            if not messagebox.askyesno("⚠️ Confirm Delete", f"Remove bookmark '{name}' from {browser_var.get().upper()}?"):
                return
            if not self._ensure_browser_closed(browser_var.get()):
                return
            success, message = self.migrator.delete_bookmark(browser_var.get(), bid)
            self.status_var.set(message)
            if success:
                tree.delete(bid)
            else:
                messagebox.showerror("❌ Error", message)
        
        actions = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        actions.pack(fill="x")
        ttk.Button(actions, text="🌐 Open Selected", command=open_selected).pack(side="left")
        ttk.Button(actions, text="✏️ Edit Selected", command=edit_selected).pack(side="left", padx=(10, 0))
        ttk.Button(actions, text="🗑️ Remove Selected", command=remove_selected).pack(side="left", padx=(10, 0))
    
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
        """Open the export folder in the OS file browser, cross-platform"""
        if not os.path.exists(self.migrator.export_dir):
            messagebox.showerror("Error", "Bookmarks backup folder not found")
            return
        
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(self.migrator.export_dir)
            elif system == "Darwin":
                subprocess.Popen(["open", self.migrator.export_dir])
            else:
                subprocess.Popen(["xdg-open", self.migrator.export_dir])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {str(e)}")


def main():
    root = tk.Tk()
    app = BookmarkMigratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
