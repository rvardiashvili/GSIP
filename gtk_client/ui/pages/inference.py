import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import sys
import os
import subprocess
from pathlib import Path
from ...core.runner import PipelineRunner
from ...core.config_io import list_model_configs, PROJECT_ROOT
from ..widgets.log_viewer import LogViewer
from ..widgets.file_picker import FilePicker

class InferencePage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        
        # 1. Configuration Area
        config_frame = Gtk.Frame(label="Inference Configuration")
        config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        config_box.set_margin_top(10)
        config_box.set_margin_bottom(10)
        config_box.set_margin_start(10)
        config_box.set_margin_end(10)
        config_frame.set_child(config_box)
        
        # Model Selector
        model_row = Gtk.Box(spacing=10)
        model_row.append(Gtk.Label(label="Model Config:"))
        self.model_combo = Gtk.DropDown.new_from_strings(list_model_configs())
        model_row.append(self.model_combo)
        config_box.append(model_row)
        
        # File Pickers (Both are folders)
        self.input_picker = FilePicker("Input Path:", is_folder=True)
        self.output_picker = FilePicker("Output Dir:", is_folder=True)
        
        config_box.append(self.input_picker)
        config_box.append(self.output_picker)
        
        self.append(config_frame)
        
        # 2. Controls
        control_box = Gtk.Box(spacing=10)
        self.run_btn = Gtk.Button(label="Run Inference")
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.connect("clicked", self.on_run)
        
        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.set_sensitive(False)
        self.stop_btn.connect("clicked", self.on_stop)
        
        # View Analysis Button (Hidden initially)
        self.analysis_btn = Gtk.Button(label="View Analysis")
        self.analysis_btn.set_visible(False)
        self.analysis_btn.connect("clicked", self.on_view_analysis)
        
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_hexpand(True)
        
        control_box.append(self.run_btn)
        control_box.append(self.stop_btn)
        control_box.append(self.analysis_btn)
        control_box.append(self.progress_bar)
        self.append(control_box)
        
        # 3. Output
        self.log_view = LogViewer()
        self.append(self.log_view)
        
        self.runner = None
        self.last_output_path = None

    def on_run(self, btn):
        # ... (Get input/output paths) ...
        # Assume correct variable names from context
        
        # Get selected model directly from the dropdown model (GtkStringList)
        selected_item = self.model_combo.get_selected_item()
        if selected_item:
             model = selected_item.get_string()
        else:
             model = "resnet_s2" # Fallback
             
        inp = self.input_picker.get_path()
        out = self.output_picker.get_path()
        
        if not inp or not out:
            self.log_view.append_text("Error: Please select input and output paths.\n")
            return
            
        self.last_output_path = out
        
        # Always point directly to the src/main.py file using the absolute project root
        main_py_path = (PROJECT_ROOT / "src" / "main.py").resolve()
        
        cmd = [
            sys.executable, str(main_py_path),
            f"model={model}",
            f"input_path={inp}",
            f"output_path={out}",
            "pipeline.output.save_preview=true" 
        ]
        
        self.log_view.clear()
        self.log_view.append_text(f"Starting command: {' '.join(cmd)}\n\n")
        
        self.run_btn.set_sensitive(False)
        self.stop_btn.set_sensitive(True)
        self.analysis_btn.set_visible(False)
        self.progress_bar.set_fraction(0.0)
        
        self.runner = PipelineRunner(
            cmd,
            on_output=self.log_view.append_text,
            on_progress=self.update_progress,
            on_finish=self.on_finish
        )
        self.runner.start()

    def on_stop(self, btn):
        if self.runner:
            self.runner.stop()
            self.log_view.append_text("\nStopping...\n")

    def update_progress(self, fraction):
        self.progress_bar.set_fraction(fraction)

    def on_finish(self, code):
        self.run_btn.set_sensitive(True)
        self.stop_btn.set_sensitive(False)
        if code == 0:
            self.log_view.append_text("\nDone!\n")
            self.progress_bar.set_fraction(1.0)
            self.analysis_btn.set_visible(True)
        else:
            self.log_view.append_text(f"\nFailed with code {code}\n")

    def on_view_analysis(self, btn):
        if self.last_output_path:
            # Switch to Analysis tab via MainWindow logic
            # Since we don't have direct access to main window stack easily without passing references,
            # we can just open the folder for now, OR rely on Analysis dashboard manual refresh.
            # Best UX: Open the folder in file manager
            subprocess.Popen(["xdg-open", self.last_output_path])
