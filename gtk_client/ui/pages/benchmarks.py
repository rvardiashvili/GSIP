import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
import sys
import json
from pathlib import Path
from ...core.runner import PipelineRunner
from ..widgets.log_viewer import LogViewer

class BenchmarkPage(Gtk.Paned):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_position(400) # Split
        
        # LEFT: Config Editor
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left_box.set_margin_top(10)
        left_box.set_margin_bottom(10)
        left_box.set_margin_start(10)
        left_box.set_margin_end(5)
        
        self.config_path = Path("benchmark_config.json")
        
        # Text Editor
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.text_view = Gtk.TextView()
        self.text_view.set_monospace(True)
        self.buffer = self.text_view.get_buffer()
        self.load_config()
        scrolled.set_child(self.text_view)
        
        # Buttons
        btn_box = Gtk.Box(spacing=10)
        
        load_btn = Gtk.Button(label="Load JSON...")
        load_btn.connect("clicked", self.on_load_clicked)
        
        save_btn = Gtk.Button(label="Save Config")
        save_btn.connect("clicked", self.save_config)
        
        self.run_btn = Gtk.Button(label="Run Suite")
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
        
        self.path_label = Gtk.Label(label=f"Config: {self.config_path.name}", xalign=0)
        left_box.append(self.path_label)
        left_box.append(scrolled)
        left_box.append(btn_box)
        
        self.set_start_child(left_box)
        
        # RIGHT: Output
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_box.set_margin_top(10)
        right_box.set_margin_bottom(10)
        right_box.set_margin_start(5)
        right_box.set_margin_end(10)
        
        self.log_view = LogViewer()
        right_box.append(Gtk.Label(label="Execution Log", xalign=0))
        right_box.append(self.log_view)
        
        self.set_end_child(right_box)
        
        self.runner = None

    def on_load_clicked(self, btn):
        dialog = Gtk.FileChooserNative(
            title="Select Benchmark Config",
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Open",
            cancel_label="_Cancel"
        )
        # Filter for JSON
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
            self.buffer.set_text("{\n  \"output_dir\": \"out/benchmarks\",\n  \"benchmarks\": []\n}")

    def save_config(self, btn):
        start, end = self.buffer.get_bounds()
        text = self.buffer.get_text(start, end, True)
        try:
            # Validate JSON
            json.loads(text)
            with open(self.config_path, 'w') as f:
                f.write(text)
            self.log_view.append_text("[System] Config saved.\n")
        except json.JSONDecodeError as e:
            self.log_view.append_text(f"[Error] Invalid JSON: {e}\n")

    def on_run(self, btn):
        # Auto-save before run
        self.save_config(None)
        
        cmd = [sys.executable, "src/benchmark_suite.py", "--config", str(self.config_path)]
        
        self.log_view.clear()
        self.log_view.append_text(f"Starting Benchmark Suite...\n")
        
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
