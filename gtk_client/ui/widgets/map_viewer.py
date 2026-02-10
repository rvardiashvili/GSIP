import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk
import cairo

class MapViewer(Gtk.Box):
    def __init__(self, title, image_path, metric_type=None, legend_widget=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("card")
        self.set_hexpand(True)
        
        # Title
        header = Gtk.Box()
        header.set_margin_top(8)
        header.set_margin_bottom(8)
        header.set_margin_start(12)
        lbl = Gtk.Label(label=title)
        lbl.add_css_class("heading")
        header.append(lbl)
        self.append(header)
        
        # Image
        self.overlay = Gtk.Overlay()
        self.overlay.set_hexpand(True)
        self.overlay.set_vexpand(True)
        
        try:
            texture = Gdk.Texture.new_from_filename(str(image_path))
            self.pic = Gtk.Picture.new_for_paintable(texture)
            self.pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            self.pic.set_can_shrink(True)
            # Min height to ensure it's visible
            self.pic.set_size_request(-1, 300) 
            self.overlay.set_child(self.pic)
        except Exception:
            self.overlay.set_child(Gtk.Label(label="Image not found"))
            
        self.append(self.overlay)
        
        # Footer (Legend or Gradient)
        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        footer.set_margin_top(10)
        footer.set_margin_bottom(10)
        footer.set_margin_start(10)
        footer.set_margin_end(10)
        
        if legend_widget:
            # Classification Legend
            footer.append(legend_widget)
        elif metric_type:
            # Native Gradient Bar
            footer.append(self.create_gradient_bar(metric_type))
            
        self.append(footer)

    def create_gradient_bar(self, metric_type):
        """
        Creates a CSS-styled gradient bar with native labels.
        metric_type: 'viridis', 'magma', 'plasma'
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        # Labels
        labels = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        l1 = Gtk.Label(label="Low / 0.0")
        l1.add_css_class("dim-label")
        l2 = Gtk.Label(label="High / 1.0")
        l2.add_css_class("dim-label")
        l2.set_hexpand(True)
        l2.set_halign(Gtk.Align.END)
        labels.append(l1)
        labels.append(l2)
        box.append(labels)
        
        # Bar
        bar = Gtk.Box()
        bar.set_size_request(-1, 12)
        bar.add_css_class(f"grad-{metric_type}") # CSS classes defined in main.py or style
        
        # We need to inject CSS for this if not global
        # I'll create a DrawingArea fallback if CSS isn't easy here, but CSS is cleaner.
        # I'll assume global CSS is loaded.
        
        # Using a DrawingArea for the gradient is safer/native
        da = Gtk.DrawingArea()
        da.set_content_height(15)
        da.set_hexpand(True)
        da.set_draw_func(self.draw_gradient, metric_type)
        
        box.append(da)
        return box

    def draw_gradient(self, area, cr, width, height, metric_type):
        # Native Cairo Gradient
        pat = cairo.LinearGradient(0.0, 0.0, width, 0.0)
        
        # Simple approximations of colormaps
        if metric_type == 'viridis':
            pat.add_color_stop_rgb(0.0, 0.26, 0.01, 0.32) # Purple
            pat.add_color_stop_rgb(0.5, 0.12, 0.62, 0.53) # Teal
            pat.add_color_stop_rgb(1.0, 0.99, 0.90, 0.14) # Yellow
        elif metric_type == 'magma':
            pat.add_color_stop_rgb(0.0, 0.00, 0.00, 0.00) # Black
            pat.add_color_stop_rgb(0.5, 0.72, 0.22, 0.48) # Red/Purple
            pat.add_color_stop_rgb(1.0, 0.98, 0.99, 0.75) # White/Yellow
        elif metric_type == 'plasma':
            pat.add_color_stop_rgb(0.0, 0.05, 0.03, 0.52) # Blue
            pat.add_color_stop_rgb(0.5, 0.79, 0.28, 0.47) # Red
            pat.add_color_stop_rgb(1.0, 0.94, 0.97, 0.13) # Yellow
            
        cr.rectangle(0, 0, width, height)
        cr.set_source(pat)
        cr.fill()
