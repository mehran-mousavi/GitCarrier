import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import json
from datetime import datetime
import threading

# --- CONFIGURATION & THEME ---
# Modern color palette (Nord Theme inspired)
COLORS = {
    "bg_dark": "#2E3440",       # Main background
    "bg_light": "#3B4252",      # Panel background
    "fg_primary": "#D8DEE9",    # Primary text
    "fg_secondary": "#E5E9F0",  # Secondary text
    "accent": "#88C0D0",        # Accent color (Ice Blue)
    "success": "#A3BE8C",       # Success Green
    "warning": "#EBCB8B",       # Warning Yellow
    "error": "#BF616A",         # Error Red
    "select": "#4C566A"         # Selection highlight
}

FONT_MAIN = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_MONO = ("Consolas", 10)

class GitManager:
    """Handles all Git-related operations."""
    def __init__(self):
        self.repo_path = ""

    def set_repo_path(self, path):
        """Sets the repository path if it contains a .git folder."""
        if self.is_git_repo(path):
            self.repo_path = path
            return True
        return False

    def run_git(self, args):
        """Executes git commands in the project directory."""
        if not self.repo_path:
            return None
        try:
            # Prevent console window from popping up on Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                startupinfo=startupinfo
            )
            return result
        except Exception as e:
            print(f"Git Error: {e}")
            return None

    def is_git_repo(self, path):
        """Checks if the directory is a git repository."""
        return os.path.isdir(os.path.join(path, ".git"))

    def get_current_branch(self):
        """Returns the name of the currently active branch."""
        res = self.run_git(["branch", "--show-current"])
        return res.stdout.strip() if res else ""

    def get_all_branches(self):
        """Returns a list of all local branches."""
        res = self.run_git(["branch", "--format=%(refname:short)"])
        if res and res.returncode == 0:
            return [b.strip() for b in res.stdout.strip().split('\n') if b.strip()]
        return []

    def get_commits(self, branch, skip=0, limit=10):
        """Fetches a paginated list of commits."""
        # Format: Hash|Date|Author|Message
        fmt = "%h|%ad|%an|%s"
        cmd = ["log", branch, f"--pretty=format:{fmt}", "--date=short", f"-n {limit}", f"--skip={skip}"]
        res = self.run_git(cmd)
        
        commits = []
        if res and res.returncode == 0 and res.stdout:
            for line in res.stdout.split('\n'):
                parts = line.split('|')
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "date": parts[1],
                        "author": parts[2],
                        "msg": parts[3]
                    })
        return commits

    def create_bundle(self, start_point, branch, output_path):
        """
        Creates a git bundle.
        If start_point is provided: bundles range start_point..branch.
        If start_point is None: bundles the entire history of the branch.
        """
        if start_point:
            # Syntax: git bundle create file start..branch
            rev_range = f"{start_point}..{branch}"
        else:
            rev_range = branch

        res = self.run_git(["bundle", "create", output_path, rev_range])
        return res.returncode == 0, res.stderr or res.stdout

    def verify_bundle(self, bundle_path):
        """Verifies the integrity of the bundle file."""
        res = self.run_git(["bundle", "verify", bundle_path])
        return res.returncode == 0, res.stdout

    def fetch_bundle(self, bundle_path, branch):
        """Pulls changes from the bundle into the current branch."""
        res = self.run_git(["pull", bundle_path, branch])
        return res.returncode == 0, res.stdout


class ModernUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GitCarrier Pro - Offline Git Sync")
        self.geometry("900x650")
        self.configure(bg=COLORS["bg_dark"])
        
        # Initialize Styles
        self.setup_styles()
        
        # Logic Controller
        self.git = GitManager()
        self.current_page = 0
        self.page_size = 15
        self.selected_commit_hash = None # Start point for bundle
        
        # UI Construction
        self.create_header()
        self.create_main_area()
        self.create_status_bar()

        # Load persisted settings
        self.load_settings()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam') # Clean base theme

        # General config
        style.configure(".", background=COLORS["bg_dark"], foreground=COLORS["fg_primary"], font=FONT_MAIN)
        style.configure("TFrame", background=COLORS["bg_dark"])
        style.configure("TLabel", background=COLORS["bg_dark"], foreground=COLORS["fg_primary"])
        
        # Primary Action Button (Accent Color)
        style.configure("Accent.TButton", 
                        background=COLORS["accent"], 
                        foreground=COLORS["bg_dark"], 
                        borderwidth=0, 
                        font=("Segoe UI", 11, "bold"),
                        padding=6) # Internal padding in style
        style.map("Accent.TButton", background=[('active', COLORS["success"])])

        # Standard Button
        style.configure("TButton", 
                        background=COLORS["bg_light"], 
                        foreground=COLORS["fg_primary"], 
                        borderwidth=0)
        style.map("TButton", background=[('active', COLORS["select"])])

        # Treeview (Table)
        style.configure("Treeview", 
                        background=COLORS["bg_light"], 
                        foreground=COLORS["fg_primary"], 
                        fieldbackground=COLORS["bg_light"],
                        rowheight=30,
                        borderwidth=0)
        style.configure("Treeview.Heading", 
                        background=COLORS["bg_dark"], 
                        foreground=COLORS["accent"], 
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0)
        style.map("Treeview", background=[('selected', COLORS["select"])])

        # Notebook (Tabs)
        style.configure("TNotebook", background=COLORS["bg_dark"], borderwidth=0)
        style.configure("TNotebook.Tab", 
                        background=COLORS["bg_light"], 
                        foreground=COLORS["fg_primary"],
                        padding=[15, 8],
                        font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[('selected', COLORS["accent"])], foreground=[('selected', COLORS["bg_dark"])])

    def create_header(self):
        header_frame = ttk.Frame(self, padding=20)
        header_frame.pack(fill="x", side="top")

        # Title / Logo
        lbl_title = ttk.Label(header_frame, text="GitCarrier", font=("Segoe UI", 18, "bold"), foreground=COLORS["accent"])
        lbl_title.pack(side="left")

        # Project Selection
        self.path_var = tk.StringVar(value="No Project Selected")
        
        btn_browse = ttk.Button(header_frame, text="📂 Open Project", command=self.browse_folder, style="Accent.TButton")
        btn_browse.pack(side="right", padx=5)
        
        lbl_path = ttk.Label(header_frame, textvariable=self.path_var, font=FONT_MONO, foreground=COLORS["fg_secondary"])
        lbl_path.pack(side="right", padx=10)

    def create_main_area(self):
        # Tab Container
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=10)

        # Tab 1: Pack (Home)
        self.tab_pack = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.tab_pack, text="  📤 Pack (Home -> Work)  ")
        self.setup_pack_tab()

        # Tab 2: Unpack (Work)
        self.tab_unpack = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.tab_unpack, text="  📥 Unpack (Work -> Home)  ")
        self.setup_unpack_tab()

    def setup_pack_tab(self):
        # Top Controls (Branch selection)
        controls_frame = ttk.Frame(self.tab_pack)
        controls_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(controls_frame, text="Select Branch:").pack(side="left")
        
        # Changed state to normal momentarily if needed, but readonly is safer
        self.branch_combo = ttk.Combobox(controls_frame, state="readonly", width=25)
        self.branch_combo.pack(side="left", padx=10)
        self.branch_combo.bind("<<ComboboxSelected>>", lambda e: self.load_commits(reset_page=True))

        ttk.Button(controls_frame, text="🔄 Refresh", command=lambda: self.refresh_project_info()).pack(side="left")

        # Commits Table
        columns = ("hash", "date", "author", "msg")
        self.tree = ttk.Treeview(self.tab_pack, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("hash", text="Hash")
        self.tree.heading("date", text="Date")
        self.tree.heading("author", text="Author")
        self.tree.heading("msg", text="Message")
        
        self.tree.column("hash", width=80, anchor="center")
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("author", width=120, anchor="w")
        self.tree.column("msg", width=400, anchor="w")
        
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_commit_select)

        # Pagination controls
        nav_frame = ttk.Frame(self.tab_pack, padding=(0, 10))
        nav_frame.pack(fill="x")
        
        self.btn_prev = ttk.Button(nav_frame, text="< Newer", command=self.prev_page)
        self.btn_prev.pack(side="left")
        
        self.lbl_page = ttk.Label(nav_frame, text="Page 1")
        self.lbl_page.pack(side="left", padx=10)
        
        self.btn_next = ttk.Button(nav_frame, text="Older >", command=self.next_page)
        self.btn_next.pack(side="left")

        # Bottom Action Bar
        action_frame = ttk.Frame(self.tab_pack, style="TFrame", padding=(0, 15, 0, 5))
        action_frame.pack(fill="x", pady=5)
        
        self.lbl_selection = ttk.Label(action_frame, text="Bundle Content: ALL History (Default)", foreground=COLORS["accent"], font=("Segoe UI", 11, "bold"))
        self.lbl_selection.pack(side="left", fill="x", expand=True)

        # --- UI FIX: Added padding (ipadx/ipady) to make button larger ---
        btn_create = ttk.Button(action_frame, text="🚀 Create Bundle", style="Accent.TButton", command=self.create_bundle_action)
        btn_create.pack(side="right", ipadx=20, ipady=5) 

    def setup_unpack_tab(self):
        container = ttk.Frame(self.tab_unpack)
        container.place(relx=0.5, rely=0.4, anchor="center")

        ttk.Label(container, text="Select .bundle file to merge into current branch", font=("Segoe UI", 14)).pack(pady=20)

        btn_select_bundle = ttk.Button(container, text="📂 Select Bundle File", style="Accent.TButton", command=self.apply_bundle_action)
        btn_select_bundle.pack(ipadx=30, ipady=10)

        self.lbl_unpack_status = ttk.Label(container, text="", foreground=COLORS["fg_secondary"])
        self.lbl_unpack_status.pack(pady=20)

    def create_status_bar(self):
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(self, textvariable=self.status_var, background=COLORS["bg_light"], padding=5, font=("Segoe UI", 9))
        status_bar.pack(fill="x", side="bottom")

    # --- LOGIC HANDLERS ---

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            if self.git.set_repo_path(path):
                self.path_var.set(path)
                self.save_settings(path)
                self.refresh_project_info()
            else:
                messagebox.showerror("Error", "This folder is not a Git repository.")

    def refresh_project_info(self):
        """Loads branches and auto-selects the active one."""
        if not self.git.repo_path: return

        branches = self.git.get_all_branches()
        current = self.git.get_current_branch()
        
        # Logic fix: Ensure combobox values are set before setting the current selection
        self.branch_combo['values'] = branches
        
        if current and current in branches:
            self.branch_combo.set(current)
        elif branches:
            self.branch_combo.current(0)
            
        self.load_commits(reset_page=True)
        self.status_var.set(f"Loaded project: {os.path.basename(self.git.repo_path)}")

    def load_commits(self, reset_page=False):
        if not self.git.repo_path: return
        
        if reset_page:
            self.current_page = 0
            self.selected_commit_hash = None
            self.lbl_selection.config(text="Bundle Content: ALL History (Default)")

        branch = self.branch_combo.get()
        if not branch: return

        skip = self.current_page * self.page_size
        commits = self.git.get_commits(branch, skip, self.page_size)

        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Populate tree
        for c in commits:
            self.tree.insert("", "end", values=(c['hash'], c['date'], c['author'], c['msg']))

        self.lbl_page.config(text=f"Page {self.current_page + 1}")
        
        # Button state logic
        self.btn_prev.config(state="normal" if self.current_page > 0 else "disabled")
        self.btn_next.config(state="normal" if len(commits) == self.page_size else "disabled")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_commits()

    def next_page(self):
        self.current_page += 1
        self.load_commits()

    def on_commit_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            item = self.tree.item(selected_item)
            c_hash = item['values'][0]
            c_msg = item['values'][3]
            self.selected_commit_hash = c_hash
            
            # UX: Explain range clearly
            self.lbl_selection.config(text=f"Start Point: {c_hash} ({c_msg[:30]}...)\nBundle will include everything AFTER this commit.")

    def create_bundle_action(self):
        if not self.git.repo_path: return
        
        branch = self.branch_combo.get()
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        default_name = f"{os.path.basename(self.git.repo_path)}_{branch}_{date_str}.bundle"
        
        target_file = filedialog.asksaveasfilename(
            defaultextension=".bundle",
            initialfile=default_name,
            filetypes=[("Git Bundle", "*.bundle")]
        )

        if target_file:
            self.status_var.set("Creating bundle... please wait.")
            self.update_idletasks()
            
            # Run in background thread
            threading.Thread(target=self._run_bundle_creation, args=(target_file, branch)).start()

    def _run_bundle_creation(self, filepath, branch):
        success, msg = self.git.create_bundle(self.selected_commit_hash, branch, filepath)
        if success:
            v_success, v_msg = self.git.verify_bundle(filepath)
            if v_success:
                messagebox.showinfo("Success", f"Bundle created & Verified successfully!\nSaved at: {filepath}")
                self.status_var.set("Bundle ready.")
            else:
                messagebox.showwarning("Warning", f"Bundle created but verification failed:\n{v_msg}")
        else:
            messagebox.showerror("Error", f"Failed to create bundle:\n{msg}")
            self.status_var.set("Error creating bundle.")

    def apply_bundle_action(self):
        if not self.git.repo_path:
             messagebox.showerror("Error", "Please select a project folder first.")
             return

        bundle_file = filedialog.askopenfilename(filetypes=[("Git Bundle", "*.bundle")])
        if bundle_file:
            self.status_var.set("Verifying bundle...")
            v_success, v_msg = self.git.verify_bundle(bundle_file)
            
            if not v_success:
                messagebox.showerror("Invalid Bundle", f"This bundle is corrupted or invalid:\n{v_msg}")
                return

            if messagebox.askyesno("Confirm Merge", "Bundle is valid. Do you want to MERGE it into your current branch?"):
                branch = self.git.get_current_branch()
                self.status_var.set("Merging bundle...")
                success, msg = self.git.fetch_bundle(bundle_file, branch)
                
                if success:
                    messagebox.showinfo("Success", "Changes merged successfully!")
                    self.refresh_project_info()
                else:
                    messagebox.showerror("Merge Failed", f"Git output:\n{msg}")

    # --- PERSISTENCE ---
    def load_settings(self):
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    data = json.load(f)
                    path = data.get("last_repo", "")
                    if path and os.path.exists(path):
                        if self.git.set_repo_path(path):
                            self.path_var.set(path)
                            self.refresh_project_info()
        except:
            pass

    def save_settings(self, path):
        try:
            with open("settings.json", "w") as f:
                json.dump({"last_repo": path}, f)
        except:
            pass

if __name__ == "__main__":
    app = ModernUI()
    app.mainloop()