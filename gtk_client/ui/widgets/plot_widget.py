import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

# Try to import GTK4 backend
try:
    from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
    from matplotlib.backends.backend_gtk4 import NavigationToolbar2GTK4 as NavigationToolbar
    MATPLOTLIB_GTK = True
except ImportError:
    MATPLOTLIB_GTK = False
    import io
    from gi.repository import GdkPixbuf

class PlotWidget(Gtk.Box):
    def __init__(self, figure):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_size_request(600, 400)
        
        if MATPLOTLIB_GTK:
            self.canvas = FigureCanvas(figure)
            self.canvas.set_vexpand(True)
            self.canvas.set_hexpand(True)
            
            self.toolbar = NavigationToolbar(self.canvas)
            self.append(self.toolbar)
            self.append(self.canvas)
        else:
            # Fallback to static image
            buf = io.BytesIO()
            figure.savefig(buf, format='png', dpi=100)
            plt.close(figure)
            buf.seek(0)
            
            loader = GdkPixbuf.PixbufLoader.new_with_type('png')
            loader.write(buf.read())
            loader.close()
            pixbuf = loader.get_pixbuf()
            
            img = Gtk.Image.new_from_pixbuf(pixbuf)
            img.set_vexpand(True)
            self.append(img)
            self.append(Gtk.Label(label="(Interactive plots unavailable: install matplotlib gtk4 backend)"))