import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

class FilePicker(Gtk.Box):
    def __init__(self, label="Path", action=Gtk.FileChooserAction.OPEN, is_folder=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.dialog = Gtk.FileChooserNative(
            title=f"Select {label}",
            action=action,
            accept_label="_Open",
            cancel_label="_Cancel"
        )
        self.set_folder_mode(is_folder)
        
        self.label = Gtk.Label(label=label)
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        
        self.button = Gtk.Button(label="...")
        self.button.connect("clicked", self.on_browse)
        
        self.append(self.label)
        self.append(self.entry)
        self.append(self.button)
        
        self.dialog.connect("response", self.on_response)

    def set_folder_mode(self, is_folder):
        if is_folder:
            self.dialog.set_action(Gtk.FileChooserAction.SELECT_FOLDER)
        else:
            self.dialog.set_action(Gtk.FileChooserAction.OPEN)

    def on_browse(self, btn):
        self.dialog.show()

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            f = dialog.get_file()
            self.entry.set_text(f.get_path())

    def get_path(self):
        return self.entry.get_text()

    def set_path(self, path):
        self.entry.set_text(str(path))