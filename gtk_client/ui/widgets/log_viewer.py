import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango

class LogViewer(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_min_content_height(200)
        
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        
        # Style
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"textview { font-family: monospace; font-size: 10pt; }")
        self.text_view.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.buffer = self.text_view.get_buffer()
        self.set_child(self.text_view)

    def append_text(self, text):
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert(end_iter, text)
        
        # Auto-scroll
        adj = self.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def clear(self):
        self.buffer.set_text("")
