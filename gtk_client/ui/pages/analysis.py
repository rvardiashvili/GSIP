import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GObject
from pathlib import Path
import subprocess
import json
import zipfile
import threading
from gi.repository import Gtk, Gdk, GObject, GLib
from ...core.config_io import scan_benchmark_results, load_json
from ..widgets.file_picker import FilePicker
from ..widgets.native_chart import NativeChart
from ..widgets.native_bar_chart import NativeBarChart
from ..widgets.map_viewer import MapViewer
from ..widgets.legend_widget import LegendWidget

class AnalysisPage(Gtk.Paned):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_position(300)
        
        # --- LEFT SIDE: Navigation ---
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        # Folder Picker
        self.folder_picker = FilePicker("Root Folder", is_folder=True)
        self.folder_picker.set_path(str(Path("out/benchmarks_final").resolve()))
        left_box.append(self.folder_picker)
        
        refresh_btn = Gtk.Button(label="Scan for Reports")
        refresh_btn.connect("clicked", self.on_refresh)
        left_box.append(refresh_btn)
        
        # List of Runs
        self.list_box = Gtk.ListBox()
        self.list_box.connect("row-selected", self.on_row_selected)
        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_vexpand(True)
        scrolled_list.set_child(self.list_box)
        left_box.append(scrolled_list)
        
        self.set_start_child(left_box)
        
        # --- RIGHT SIDE: Details ---
        self.detail_scrolled = Gtk.ScrolledWindow()
        self.detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.detail_box.set_margin_top(20)
        self.detail_box.set_margin_bottom(20)
        self.detail_box.set_margin_start(20)
        self.detail_box.set_margin_end(20)
        self.detail_scrolled.set_child(self.detail_box)
        
        self.set_end_child(self.detail_scrolled)
        
        self.benchmark_files = [] 
        self.cached_data = {} 

    def on_refresh(self, btn):
        while self.list_box.get_first_child():
            self.list_box.remove(self.list_box.get_first_child())
            
        path = self.folder_picker.get_path()
        if not path: return
        
        self.benchmark_files = scan_benchmark_results(path)
        self.benchmark_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not self.benchmark_files:
            return

        # Add "Summary Comparison" Row
        row = Gtk.ListBoxRow()
        lbl = Gtk.Label(label="📊 Global Comparison", xalign=0, margin_start=10, margin_top=10, margin_bottom=10)
        lbl.add_css_class("title-4")
        row.set_child(lbl)
        row.is_summary = True
        self.list_box.append(row)

        for f in self.benchmark_files:
            if "consolidated_results" in f.parts:
                continue
                
            row = Gtk.ListBoxRow()
            try:
                tile_name = f.parent.name
                timestamp = f.parent.parent.name
                run_label = f.parent.parent.parent.name
                display_name = f"{run_label} / {timestamp}"
            except:
                tile_name = "Unknown"
                display_name = f.name

            lbl = Gtk.Label(label=display_name, xalign=0, margin_start=10, margin_top=5, margin_bottom=5)
            row.set_tooltip_text(f"Tile: {tile_name}")
            
            row.set_child(lbl)
            row.path = f
            self.list_box.append(row)

    def on_row_selected(self, box, row):
        if not row: return
        
        while self.detail_box.get_first_child():
            self.detail_box.remove(self.detail_box.get_first_child())
            
        if hasattr(row, 'is_summary') and row.is_summary:
            self.show_summary_view()
        else:
            self.show_detail_view(row.path)

    def get_data(self, path):
        if path not in self.cached_data:
            try:
                self.cached_data[path] = load_json(path)
            except:
                self.cached_data[path] = None
        return self.cached_data[path]

    def show_summary_view(self):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        
        title = Gtk.Label(label="Global Benchmark Comparison")
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        header.append(title)
        
        export_btn = Gtk.Button(label="Export All to ZIP")
        export_btn.add_css_class("suggested-action")
        export_btn.connect("clicked", self.on_export_clicked)
        header.append(export_btn)
        
        self.detail_box.append(header)
        
        valid_data = []
        for f in self.benchmark_files:
            if "consolidated_results" in f.parts: continue
            d = self.get_data(f)
            if d: valid_data.append((f, d))
            
        if not valid_data:
            self.detail_box.append(Gtk.Label(label="No valid benchmark data found for summary."))
            return

        # Prepare Data for Bar Charts
        labels = []
        mem_vals = []
        time_vals = []
        
        root_path = Path(self.folder_picker.get_path()).resolve()
        
        for f, d in valid_data:
            # Label: Relative path from scan root for better grouping context
            try:
                rel = f.parent.relative_to(root_path)
                label = str(rel)
            except:
                label = f.parent.name
                
            labels.append(label)
            
            # Memory
            sys_stats = d.get('system_stats', {})
            mem = sys_stats.get('process_ram_used_gb', {}).get('max', 0)
            mem_vals.append(mem)
            
            # Time
            dur = d.get('meta', {}).get('duration_seconds', 0)
            time_vals.append(dur)

        # 1. Memory Bar Chart
        mem_chart = NativeBarChart("Peak Memory Usage", "GB", color=(0.2, 0.4, 0.8))
        mem_chart.set_data(labels, mem_vals)
        self.detail_box.append(mem_chart)
        
        self.detail_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 2. Performance Bar Chart
        time_chart = NativeBarChart("Execution Duration", "s", color=(0.1, 0.7, 0.3))
        time_chart.set_data(labels, time_vals)
        self.detail_box.append(time_chart)

    def on_export_clicked(self, btn):
        dialog = Gtk.FileDialog.new()
        dialog.set_initial_name("benchmark_export.zip")
        # In GTK4, dialog.save takes (parent_window, cancellable, callback)
        # We need to find the parent window.
        parent = self.get_root()
        if not isinstance(parent, Gtk.Window):
            parent = None
            
        dialog.save(parent, None, self.on_export_dialog_response)

    def on_export_dialog_response(self, dialog, result):
        try:
            file_info = dialog.save_finish(result)
            if file_info:
                zip_path = file_info.get_path()
                self.do_export(zip_path)
        except Exception as e:
            print(f"Export selection failed: {e}")

    def do_export(self, zip_path):
        def export_task():
            root_path = Path(self.folder_picker.get_path()).resolve()
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for f in self.benchmark_files:
                        zf.write(f, f.relative_to(root_path))
                        
                        parent_dir = f.parent
                        for img in parent_dir.glob("*"):
                            if img.is_file():
                                # SKIP LARGE TIFF FILES
                                if img.suffix.lower() in ['.tif', '.tiff']:
                                    continue
                                    
                                if img.suffix.lower() in ['.png', '.jpg', '.jpeg', '.json']:
                                    if img == f: continue
                                    zf.write(img, img.relative_to(root_path))
                
                GLib.idle_add(self.show_notification, "Export successful", f"Saved to {zip_path}")
            except Exception as e:
                GLib.idle_add(self.show_notification, "Export failed", str(e))

        self.show_notification("Export started", "Creating ZIP archive (excluding TIFs)...")
        thread = threading.Thread(target=export_task, daemon=True)
        thread.start()

    def show_notification(self, title, message):
        # Very basic feedback using a status label if we had one, or print for now.
        # Ideally we'd have a Toast/MessageDialog.
        print(f"NOTIFICATION: {title} - {message}")
        # We can add a temporary label to detail_box
        info = Gtk.Label(label=f"ℹ️ {title}: {message}")
        info.add_css_class("dim-label")
        self.detail_box.insert_child_after(info, self.detail_box.get_first_child())
        # Auto-remove after 5 seconds
        GLib.timeout_add_seconds(5, lambda: self.detail_box.remove(info))

    def show_detail_view(self, path):
        data = self.get_data(path)
        if not data:
            self.detail_box.append(Gtk.Label(label="Error loading JSON data"))
            return
            
        meta = data.get('meta', {})
        sys_stats = data.get('system_stats', {})
        
        # 1. Header
        try:
            run_label = path.parent.parent.parent.name
            timestamp = path.parent.parent.name
        except:
            run_label = "Unknown"
            timestamp = "Unknown"

        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        title = Gtk.Label(label=f"Run: {run_label}")
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        
        id_lbl = Gtk.Label(label=f"ID: {timestamp}", xalign=0)
        id_lbl.add_css_class("dim-label")
        
        date_lbl = Gtk.Label(label=f"Date: {meta.get('start')}", xalign=0)
        dur_lbl = Gtk.Label(label=f"Duration: {meta.get('duration_seconds', 0):.2f}s", xalign=0)
        
        header_box.append(title)
        header_box.append(id_lbl)
        header_box.append(date_lbl)
        header_box.append(dur_lbl)
        self.detail_box.append(header_box)
        
        # 2. Key Metrics Grid (Native System Monitor Style)
        grid = Gtk.Grid(column_spacing=40, row_spacing=15)
        
        def add_stat(label, val, row, col):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            l = Gtk.Label(label=label, xalign=0)
            l.add_css_class("dim-label")
            v = Gtk.Label(label=str(val), xalign=0)
            v.add_css_class("title-2") # Big text
            box.append(l)
            box.append(v)
            grid.attach(box, col, row, 1, 1)

        proc_ram = sys_stats.get('process_ram_used_gb', {}).get('max', 'N/A')
        add_stat("Max Memory", f"{proc_ram} GB", 0, 0)
        
        gpu = sys_stats.get('gpu_util_percent', {}).get('mean', 'N/A')
        add_stat("Avg GPU", f"{gpu}%", 0, 1)
        
        cpu = sys_stats.get('cpu_percent', {}).get('mean', 'N/A')
        add_stat("Avg CPU", f"{cpu}%", 0, 2)
        
        self.detail_box.append(grid)
        self.detail_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # 3. Native Time Series Charts
        ts_data = data.get('time_series', [])
        if ts_data:
            lbl = Gtk.Label(label="Resource Usage History", xalign=0)
            lbl.add_css_class("heading")
            self.detail_box.append(lbl)
            
            chart_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
            chart_box.set_hexpand(True)
            
            # RAM Chart
            ram_points = [(x['timestamp'], x.get('process_ram_used_gb', 0)) for x in ts_data]
            chart_ram = NativeChart("Memory", "GB", color=(0.2, 0.6, 1.0))
            chart_ram.set_data(ram_points)
            chart_box.append(chart_ram)
            
            # GPU Chart
            if 'gpu_util_percent' in ts_data[0]:
                gpu_points = [(x['timestamp'], x.get('gpu_util_percent', 0)) for x in ts_data]
                chart_gpu = NativeChart("GPU Utilization", "%", color=(0.2, 0.8, 0.4))
                chart_gpu.set_data(gpu_points)
                chart_box.append(chart_gpu)
                
                # Sync them
                chart_ram.sync_with(chart_gpu)
                chart_gpu.sync_with(chart_ram)
            
            self.detail_box.append(chart_box)
            self.detail_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 4. Maps Dashboard (Native Viewers)
        classmap_path = list(path.parent.glob("*_classmap.json"))
        classmap_data = {}
        if classmap_path:
            try:
                with open(classmap_path[0], 'r') as f:
                    classmap_data = json.load(f)
            except:
                pass

        maps_grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        
        # A. Classification Map
        class_img = list(path.parent.glob("*preview_class.png"))
        if class_img:
            # Legend Widget
            legend = LegendWidget(classmap_data) if classmap_data else None
            viewer = MapViewer("Classification Map", class_img[0], legend_widget=legend)
            maps_grid.append(viewer)

        # B. Uncertainty Maps (Native Gradients)
        def add_metric_map(glob_pattern, title, metric_type):
            imgs = list(path.parent.glob(glob_pattern))
            if imgs:
                viewer = MapViewer(title, imgs[0], metric_type=metric_type)
                maps_grid.append(viewer)

        add_metric_map("*preview_maxprob.png", "Confidence", "viridis")
        add_metric_map("*preview_entropy.png", "Entropy", "magma")
        add_metric_map("*preview_gap.png", "Margin (Gap)", "plasma")
        
        self.detail_box.append(maps_grid)
        
        # Open Folder Button
        open_btn = Gtk.Button(label="Open Output Folder")
        open_btn.connect("clicked", lambda b: subprocess.Popen(["xdg-open", str(path.parent)]))
        self.detail_box.append(open_btn)