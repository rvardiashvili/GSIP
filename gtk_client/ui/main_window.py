import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from .pages.inference import InferencePage
from .pages.batch_run import BatchRunPage
from .pages.analysis import AnalysisPage
from .pages.configs import ConfigsPage

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="GSIP Studio")
        self.set_default_size(1100, 700)
        
        # Use a simple Box with StackSidebar for compatibility
        # If Adwaita is available, Adw.Leaflet or similar would be better, but Stack is safe.
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        
        # Sidebar
        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(self.stack)
        sidebar.set_size_request(200, -1)
        
        # Pages
        self.stack.add_titled(InferencePage(), "inference", "Run Inference")
        self.stack.add_titled(BatchRunPage(), "benchmark", "Batch Run")
        self.stack.add_titled(AnalysisPage(), "analysis", "Analysis Dashboard")
        self.stack.add_titled(ConfigsPage(), "configs", "Config Editor")
        
        box.append(sidebar)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        box.append(self.stack)
        
        self.set_child(box)
