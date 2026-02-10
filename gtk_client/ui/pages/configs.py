import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from pathlib import Path
import logging
import subprocess

log = logging.getLogger(__name__)

class ConfigsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_vexpand(True)
        
        # Header / Global Actions
        header_bar = Gtk.Box(spacing=10)
        header_bar.set_margin_top(10)
        header_bar.set_margin_bottom(5)
        header_bar.set_margin_start(10)
        
        btn_adapters = Gtk.Button(label="Open Adapters Folder")
        btn_adapters.connect("clicked", lambda b: self.open_folder("src/eo_core/adapters"))
        
        btn_reporters = Gtk.Button(label="Open Reporters Folder")
        btn_reporters.connect("clicked", lambda b: self.open_folder("src/eo_core/reporters"))
        
        header_bar.append(btn_adapters)
        header_bar.append(btn_reporters)
        self.append(header_bar)
        
        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)
        self.append(self.notebook)
        
        self.current_file = None
        self.buffer = Gtk.TextBuffer()
        
        # Categories mapping
        self.categories = {
            "Model": "configs/model",
            "Pipeline": "configs/pipeline",
            "Data Source": "configs/data_source",
            "Global": "configs"
        }
        
        self.list_boxes = {} # name -> list_box
        
        for name, path in self.categories.items():
            self.add_category_tab(name, Path(path))

    def open_folder(self, path_str):
        p = Path(path_str).resolve()
        if p.exists():
            subprocess.Popen(["xdg-open", str(p)])
        else:
            log.warning(f"Folder not found: {p}")

    def add_category_tab(self, name, root_path):
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(250)
        paned.set_vexpand(True)
        
        # List Side
        list_box_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # New Config Button (Only for specific categories if desired, doing all for now)
        if name != "Global":
            new_btn = Gtk.Button(label=f"New {name}...")
            new_btn.connect("clicked", lambda b, n=name, p=root_path: self.on_new_config(n, p))
            list_box_container.append(new_btn)
        
        list_box = Gtk.ListBox()
        list_box.connect("row-selected", self.on_row_selected)
        self.list_boxes[name] = list_box
        
        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_list.set_child(list_box)
        scrolled_list.set_vexpand(True)
        list_box_container.append(scrolled_list)
        
        paned.set_start_child(list_box_container)
        
        # Editor Side
        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        editor_box.set_vexpand(True)
        
        toolbar = Gtk.Box(spacing=6)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        toolbar.set_margin_start(6)
        
        save_btn = Gtk.Button(label="Save Changes")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self.on_save)
        toolbar.append(save_btn)
        
        self.status_label = Gtk.Label(label="")
        toolbar.append(self.status_label)
        
        editor_box.append(toolbar)
        
        self.text_view = Gtk.TextView()
        self.text_view.set_monospace(True)
        self.text_view.set_buffer(self.buffer)
        self.text_view.set_vexpand(True)
        self.text_view.set_bottom_margin(50)
        
        scrolled_text = Gtk.ScrolledWindow()
        scrolled_text.set_vexpand(True)
        scrolled_text.set_child(self.text_view)
        editor_box.append(scrolled_text)
        
        paned.set_end_child(editor_box)
        
        self.refresh_list(name, root_path, list_box)
        
        self.notebook.append_page(paned, Gtk.Label(label=name))

    def refresh_list(self, name, root_path, list_box):
        # Clear
        while list_box.get_first_child():
            list_box.remove(list_box.get_first_child())
            
        if root_path.exists():
            pattern = "*.yaml" if name != "Global" else "config.yaml"
            for p in sorted(root_path.glob(pattern)):
                if p.is_file():
                    row = Gtk.ListBoxRow()
                    lbl = Gtk.Label(label=p.name, xalign=0, margin_start=10, margin_top=5, margin_bottom=5)
                    row.set_child(lbl)
                    row.path = p
                    list_box.append(row)

    def on_row_selected(self, box, row):
        if row:
            self.current_file = row.path
            with open(self.current_file, 'r') as f:
                self.buffer.set_text(f.read())
            self.status_label.set_text(f"Editing: {row.path.name}")
        else:
            self.current_file = None
            self.status_label.set_text("")

    def on_save(self, btn):
        if self.current_file:
            start, end = self.buffer.get_bounds()
            text = self.buffer.get_text(start, end, True)
            with open(self.current_file, 'w') as f:
                f.write(text)
            self.status_label.set_text(f"Saved: {self.current_file.name}")
            log.info(f"Saved {self.current_file}")

    def on_new_config(self, category, root_path):
        # Simple Dialog
        dialog = Gtk.Window()
        dialog.set_title(f"New {category} Config")
        dialog.set_modal(True)
        dialog.set_transient_for(self.get_root())
        dialog.set_default_size(300, 100)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        entry = Gtk.Entry()
        entry.set_placeholder_text("config_name (no extension)")
        box.append(entry)
        
        create_btn = Gtk.Button(label="Create")
        create_btn.add_css_class("suggested-action")
        
        def do_create(btn):
            name = entry.get_text().strip()
            if not name: return
            if not name.endswith(".yaml"): name += ".yaml"
            
            new_path = root_path / name
            if new_path.exists():
                print("File exists!")
                return
                
            # Create empty file
            with open(new_path, 'w') as f:
                f.write("# New Configuration\n")
            
            # Refresh list
            self.refresh_list(category, root_path, self.list_boxes[category])
            dialog.close()
            
        create_btn.connect("clicked", do_create)
        box.append(create_btn)
        
        dialog.set_child(box)
        dialog.present()