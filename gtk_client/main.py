import sys
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

# Adjust path to find core modules if needed
import os
sys.path.append(os.getcwd())

from gtk_client.ui.main_window import MainWindow

class GSIPApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.gsip.studio", flags=0)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()

def main():
    app = GSIPApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

if __name__ == "__main__":
    main()
