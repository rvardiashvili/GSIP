import sys
import os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

# Fix imports: Add project root to sys.path
# Assumes structure: [root]/gtk_client/main.py
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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
