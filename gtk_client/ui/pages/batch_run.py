import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject
import sys
import json
from pathlib import Path
from ...core.runner import PipelineRunner
from ...core.config_io import PROJECT_ROOT, list_model_configs
from ..widgets.log_viewer import LogViewer
from ..widgets.file_picker import FilePicker

class BatchRunPage(Gtk.Paned):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_position(450)
        
        # --- LEFT SIDE: Config Editors ---
        left_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        left_main.set_margin_top(10)
        left_main.set_margin_bottom(10)
        left_main.set_margin_start(10)
        left_main.set_margin_end(5)
        left_main.set_size_request(350, -1)
        
        self.config_path = PROJECT_ROOT / "batch_config.json"
        
        # View Switcher
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.set_halign(Gtk.Align.CENTER)
        left_main.append(switcher)
        
        # 1. Code Editor View
        self.code_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        scrolled_code = Gtk.ScrolledWindow()
        scrolled_code.set_vexpand(True)
        scrolled_code.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.text_view = Gtk.TextView()
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.buffer = self.text_view.get_buffer()
        scrolled_code.set_child(self.text_view)
        
        self.code_view.append(scrolled_code)
        self.stack.add_titled(self.code_view, "code", "Code View")
        
        # 2. Visual Editor View
        self.visual_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Global Settings
        self.output_dir_entry = Gtk.Entry()
        self.output_dir_entry.set_placeholder_text("Output Directory (e.g. out/runs)")
        self.visual_view.append(Gtk.Label(label="Global Output Directory:", xalign=0))
        self.visual_view.append(self.output_dir_entry)
        
        self.visual_view.append(Gtk.Label(label="Global Config Overrides:", xalign=0))
        self.global_overrides_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.visual_view.append(self.global_overrides_list)
        
        add_global_ov_btn = Gtk.Button(label="+ Add Global Override")
        add_global_ov_btn.connect("clicked", lambda b: self.global_overrides_list.append(OverrideEntryRow()))
        self.visual_view.append(add_global_ov_btn)
        
        self.visual_view.append(Gtk.Label(label="Runs Configuration:", xalign=0))
        
        scrolled_visual = Gtk.ScrolledWindow()
        scrolled_visual.set_vexpand(True)
        self.run_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scrolled_visual.set_child(self.run_list_box)
        self.visual_view.append(scrolled_visual)
        
        add_run_btn = Gtk.Button(label="+ Add Run Group")
        add_run_btn.connect("clicked", self.add_empty_run_row)
        self.visual_view.append(add_run_btn)
        
        self.stack.add_titled(self.visual_view, "visual", "Visual Editor")
        
        # Connect switch events for Sync
        self.stack.connect("notify::visible-child", self.on_view_changed)
        
        left_main.append(self.stack)
        
        # Bottom Buttons
        btn_box = Gtk.Box(spacing=10)
        load_btn = Gtk.Button(label="Load JSON...")
        load_btn.connect("clicked", self.on_load_clicked)
        save_btn = Gtk.Button(label="Save Config")
        save_btn.connect("clicked", self.save_config)
        
        self.run_btn = Gtk.Button(label="Run Batch Suite")
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.connect("clicked", self.on_run)
        
        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.set_sensitive(False)
        self.stop_btn.connect("clicked", self.on_stop)
        
        btn_box.append(load_btn)
        btn_box.append(save_btn)
        btn_box.append(self.run_btn)
        btn_box.append(self.stop_btn)
        
        btn_scroll = Gtk.ScrolledWindow()
        btn_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        btn_scroll.set_child(btn_box)
        
        self.path_label = Gtk.Label(label=f"Config: {self.config_path.name}", xalign=0)
        left_main.append(self.path_label)
        left_main.append(btn_scroll)
        
        self.set_start_child(left_main)
        self.set_shrink_start_child(False)
        
        # --- RIGHT SIDE: Output ---
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_box.set_margin_top(10)
        right_box.set_margin_bottom(10)
        right_box.set_margin_start(5)
        right_box.set_margin_end(10)
        
        self.log_view = LogViewer()
        right_box.append(Gtk.Label(label="Execution Log", xalign=0))
        right_box.append(self.log_view)
        
        self.set_end_child(right_box)
        self.set_shrink_end_child(False)
        
        self.runner = None
        self.load_config() # Initial Load

    def on_view_changed(self, stack, param):
        name = stack.get_visible_child_name()
        if name == "visual":
            self.sync_json_to_visual()
        elif name == "code":
            self.sync_visual_to_json()

    def sync_json_to_visual(self):
        try:
            start, end = self.buffer.get_bounds()
            text = self.buffer.get_text(start, end, True)
            data = json.loads(text)
            
            self.output_dir_entry.set_text(data.get("output_dir", "out/runs"))
            
            # Global Overrides
            while self.global_overrides_list.get_first_child():
                self.global_overrides_list.remove(self.global_overrides_list.get_first_child())
                
            gov = data.get("global_overrides", [])
            for o in gov:
                self.global_overrides_list.append(OverrideEntryRow(o))
            
            # Clear List
            while self.run_list_box.get_first_child():
                self.run_list_box.remove(self.run_list_box.get_first_child())
                
            runs = data.get("runs", [])
            for r in runs:
                self.add_run_row(r)
                
        except Exception as e:
            print(f"Sync to Visual Failed: {e}")

    def sync_visual_to_json(self):
        try:
            # Global Overrides
            global_overrides = []
            child = self.global_overrides_list.get_first_child()
            while child:
                d = child.get_data()
                if d: global_overrides.append(d)
                child = child.get_next_sibling()
            
            data = {
                "output_dir": self.output_dir_entry.get_text(),
                "global_overrides": global_overrides,
                "runs": []
            }
            
            # Iterate children of run_list_box
            child = self.run_list_box.get_first_child()
            while child:
                if isinstance(child, RunRowWidget):
                    data["runs"].append(child.get_data())
                child = child.get_next_sibling()
            
            text = json.dumps(data, indent=2)
            self.buffer.set_text(text)
        except Exception as e:
            print(f"Sync to JSON Failed: {e}")

    def add_run_row(self, data=None):
        row = RunRowWidget(data)
        self.run_list_box.append(row)
        
    def add_empty_run_row(self, btn):
        self.add_run_row(None)

    def on_load_clicked(self, btn):
        dialog = Gtk.FileChooserNative(
            title="Select Batch Config",
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Open",
            cancel_label="_Cancel"
        )
        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files")
        filter_json.add_mime_type("application/json")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)
        dialog.connect("response", self.on_load_response)
        dialog.show()

    def on_load_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            self.config_path = Path(dialog.get_file().get_path())
            self.path_label.set_label(f"Config: {self.config_path.name}")
            self.load_config()

    def load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.buffer.set_text(f.read())
        else:
            self.buffer.set_text("{\n  \"output_dir\": \"out/runs\",\n  \"runs\": []\n}")
        
        if self.stack.get_visible_child_name() == "visual":
            self.sync_json_to_visual()

    def save_config(self, btn):
        if self.stack.get_visible_child_name() == "visual":
            self.sync_visual_to_json()
            
        start, end = self.buffer.get_bounds()
        text = self.buffer.get_text(start, end, True)
        try:
            json.loads(text) # Validate
            with open(self.config_path, 'w') as f:
                f.write(text)
            self.log_view.append_text("[System] Config saved.\n")
        except json.JSONDecodeError as e:
            self.log_view.append_text(f"[Error] Invalid JSON: {e}\n")

    def on_run(self, btn):
        self.save_config(None)
        
        script_path = (PROJECT_ROOT / "src" / "run_suite.py").resolve()
        
        cmd = [sys.executable, str(script_path), "--config", str(self.config_path)]
        
        self.log_view.clear()
        self.log_view.append_text(f"Starting Batch Suite...\n")
        
        self.run_btn.set_sensitive(False)
        self.stop_btn.set_sensitive(True)
        
        self.runner = PipelineRunner(
            cmd,
            on_output=self.log_view.append_text,
            on_finish=self.on_finish
        )
        self.runner.start()

    def on_stop(self, btn):
        if self.runner:
            self.runner.stop()

    def on_finish(self, code):
        self.run_btn.set_sensitive(True)
        self.stop_btn.set_sensitive(False)
        if code == 0:
            self.log_view.append_text("\nSuite Completed Successfully.\n")
        else:
            self.log_view.append_text(f"\nSuite Failed with code {code}\n")

class ModelEntryRow(Gtk.Box):
    def __init__(self, data=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5) # Changed to Vertical to stack expander
        self.data = data or {} # Str or Dict
        
        # Top Row: Name, Label, Delete
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        self.name_entry = Gtk.Entry(hexpand=True)
        self.name_entry.set_placeholder_text("Model Name (e.g. resnet_s2)")
        
        self.label_entry = Gtk.Entry(hexpand=True)
        self.label_entry.set_placeholder_text("Label (Optional)")
        
        del_btn = Gtk.Button(icon_name="user-trash-symbolic")
        del_btn.add_css_class("flat")
        del_btn.connect("clicked", lambda b: self.get_parent().remove(self))
        
        top_row.append(self.name_entry)
        top_row.append(self.label_entry)
        top_row.append(del_btn)
        self.append(top_row)
        
        # Overrides Expander
        expander = Gtk.Expander(label="Model Overrides")
        exp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        exp_box.set_margin_start(20) # Indent
        
        self.overrides_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        exp_box.append(self.overrides_list)
        
        add_ov_btn = Gtk.Button(label="+ Add Override")
        add_ov_btn.add_css_class("small")
        add_ov_btn.connect("clicked", lambda b: self.overrides_list.append(OverrideEntryRow()))
        exp_box.append(add_ov_btn)
        
        expander.set_child(exp_box)
        self.append(expander)
        
        # Populate
        if isinstance(self.data, str):
            self.name_entry.set_text(self.data)
        elif isinstance(self.data, dict):
            self.name_entry.set_text(self.data.get("name", ""))
            self.label_entry.set_text(self.data.get("label", ""))
            
            ov = self.data.get("config_overrides", [])
            for o in ov:
                self.overrides_list.append(OverrideEntryRow(o))

    def get_data(self):
        name = self.name_entry.get_text().strip()
        if not name: return None
        
        label = self.label_entry.get_text().strip()
        
        overrides = []
        child = self.overrides_list.get_first_child()
        while child:
            d = child.get_data()
            if d: overrides.append(d)
            child = child.get_next_sibling()
        
        if not label and not overrides:
            return name
            
        ret = {"name": name}
        if label: ret["label"] = label
        if overrides: ret["config_overrides"] = overrides
        return ret

class InputEntryRow(Gtk.Box):
    def __init__(self, path=""):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        self.path_entry = Gtk.Entry(hexpand=True)
        self.path_entry.set_text(path)
        self.append(self.path_entry)
        
        pick_btn = Gtk.Button(icon_name="document-open-symbolic")
        pick_btn.connect("clicked", self.on_pick)
        self.append(pick_btn)
        
        del_btn = Gtk.Button(icon_name="user-trash-symbolic")
        del_btn.add_css_class("flat")
        del_btn.connect("clicked", lambda b: self.get_parent().remove(self))
        self.append(del_btn)

    def on_pick(self, btn):
        dialog = Gtk.FileChooserNative(
            title="Select Input", action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Select", cancel_label="_Cancel"
        )
        dialog.connect("response", self.on_resp)
        dialog.show()
        
    def on_resp(self, d, r):
        if r == Gtk.ResponseType.ACCEPT:
            self.path_entry.set_text(d.get_file().get_path())

    def get_data(self):
        return self.path_entry.get_text().strip()

class OverrideEntryRow(Gtk.Box):
    def __init__(self, text=""):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.entry = Gtk.Entry(hexpand=True)
        self.entry.set_text(text)
        self.entry.set_placeholder_text("+key=value")
        self.append(self.entry)
        
        del_btn = Gtk.Button(icon_name="user-trash-symbolic")
        del_btn.add_css_class("flat")
        del_btn.connect("clicked", lambda b: self.get_parent().remove(self))
        self.append(del_btn)

    def get_data(self):
        return self.entry.get_text().strip()

class RunRowWidget(Gtk.Frame):
    def __init__(self, data=None):
        super().__init__()
        self.data = data or {}
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(10); main_box.set_margin_end(10)
        main_box.set_margin_top(10); main_box.set_margin_bottom(10)
        
        # Header
        header = Gtk.Box()
        header.append(Gtk.Label(label="Run Group", css_classes=["heading"]))
        del_btn = Gtk.Button(icon_name="user-trash-symbolic")
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", self.on_delete)
        header.append(Gtk.Label(hexpand=True))
        header.append(del_btn)
        main_box.append(header)
        
        # --- Section 1: Models ---
        sec1 = Gtk.Frame()
        sec1_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec1_box.set_margin_top(5); sec1_box.set_margin_bottom(5)
        sec1_box.set_margin_start(5); sec1_box.set_margin_end(5)
        
        sec1_box.append(Gtk.Label(label="Models", xalign=0, css_classes=["dim-label"]))
        self.models_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec1_box.append(self.models_list)
        
        add_mod_btn = Gtk.Button(label="+ Add Model")
        add_mod_btn.connect("clicked", lambda b: self.models_list.append(ModelEntryRow()))
        sec1_box.append(add_mod_btn)
        
        sec1.set_child(sec1_box)
        main_box.append(sec1)
        
        # --- Section 2: Inputs ---
        sec2 = Gtk.Frame()
        sec2_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec2_box.set_margin_top(5); sec2_box.set_margin_bottom(5)
        sec2_box.set_margin_start(5); sec2_box.set_margin_end(5)
        
        sec2_box.append(Gtk.Label(label="Input Paths", xalign=0, css_classes=["dim-label"]))
        self.inputs_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec2_box.append(self.inputs_list)
        
        add_inp_btn = Gtk.Button(label="+ Add Input")
        add_inp_btn.connect("clicked", lambda b: self.inputs_list.append(InputEntryRow()))
        sec2_box.append(add_inp_btn)
        
        sec2.set_child(sec2_box)
        main_box.append(sec2)
        
        # --- Section 3: Shared Overrides ---
        sec3 = Gtk.Frame()
        sec3_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec3_box.set_margin_top(5); sec3_box.set_margin_bottom(5)
        sec3_box.set_margin_start(5); sec3_box.set_margin_end(5)
        
        sec3_box.append(Gtk.Label(label="Shared Config Overrides", xalign=0, css_classes=["dim-label"]))
        self.overrides_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec3_box.append(self.overrides_list)
        
        add_ov_btn = Gtk.Button(label="+ Add Override")
        add_ov_btn.connect("clicked", lambda b: self.overrides_list.append(OverrideEntryRow()))
        sec3_box.append(add_ov_btn)
        
        sec3.set_child(sec3_box)
        main_box.append(sec3)
        
        self.set_child(main_box)
        self.populate_data()

    def populate_data(self):
        # 1. Models
        models = self.data.get("models", self.data.get("name", []))
        if isinstance(models, str): models = [models]
        
        # Retrieve root-level label (handle typo 'lable')
        root_label = self.data.get("label", self.data.get("lable", ""))
        
        for idx, m in enumerate(models):
            # If model is simple string, check if we should apply root label
            if isinstance(m, str):
                model_data = {"name": m}
                
                # Apply root label if present
                if root_label:
                    if isinstance(root_label, list):
                        # 1:1 mapping if list
                        if idx < len(root_label):
                            model_data["label"] = str(root_label[idx])
                    else:
                        # Single label string applies to the single model 
                        # (or prefix for multiple, but UI shows explicit field)
                        model_data["label"] = str(root_label)
                
                self.models_list.append(ModelEntryRow(model_data))
            else:
                # Already a dict (complex model definition)
                self.models_list.append(ModelEntryRow(m))
            
        # 2. Inputs
        inputs = self.data.get("input_path", [])
        if isinstance(inputs, str): inputs = [inputs]
        for i in inputs:
            self.inputs_list.append(InputEntryRow(i))
            
        # 3. Overrides
        overrides = self.data.get("config_overrides", [])
        for o in overrides:
            self.overrides_list.append(OverrideEntryRow(o))

    def get_data(self):
        # Models
        models_data = []
        child = self.models_list.get_first_child()
        while child:
            d = child.get_data()
            if d: models_data.append(d)
            child = child.get_next_sibling()
            
        # Inputs
        inputs_data = []
        child = self.inputs_list.get_first_child()
        while child:
            d = child.get_data()
            if d: inputs_data.append(d)
            child = child.get_next_sibling()
            
        # Overrides
        overrides_data = []
        child = self.overrides_list.get_first_child()
        while child:
            d = child.get_data()
            if d: overrides_data.append(d)
            child = child.get_next_sibling()
            
        result = {}
        
        # 1. Handle Models Unwrapping
        if len(models_data) == 1:
            single_model = models_data[0]
            if isinstance(single_model, dict):
                if "label" in single_model or "config_overrides" in single_model:
                     result["name"] = single_model["name"]
                     if "label" in single_model:
                         result["label"] = single_model["label"]
                     if "config_overrides" in single_model:
                         overrides_data.extend(single_model["config_overrides"])
                else:
                     result["name"] = single_model["name"]
            else:
                result["name"] = single_model
        elif len(models_data) > 1:
            result["models"] = models_data

        # 2. Handle Inputs Unwrapping
        if len(inputs_data) == 1:
            result["input_path"] = inputs_data[0]
        elif len(inputs_data) > 1:
            result["input_path"] = inputs_data
            
        # 3. Overrides
        if overrides_data:
            result["config_overrides"] = overrides_data
            
        return result

    def on_delete(self, btn):
        parent = self.get_parent()
        if parent:
            parent.remove(self)