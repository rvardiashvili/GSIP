import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk

class LegendWidget(Gtk.Box):
    def __init__(self, classmap_data):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.set_margin_top(2)
        self.set_margin_bottom(2)
        self.set_margin_start(2)
        self.set_margin_end(2)
        
        title = Gtk.Label(label="Legend")
        title.add_css_class("dim-label") # More subtle title
        title.set_halign(Gtk.Align.START)
        self.append(title)
        
        # ScrolledWindow to prevent legend from blowing up the UI
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(120)
        scroll.set_propagate_natural_height(True)
        
        # Use FlowBox for compact layout
        self.flow = Gtk.FlowBox()
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_max_children_per_line(15) 
        self.flow.set_min_children_per_line(1)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_column_spacing(8)
        self.flow.set_row_spacing(2)
        
        scroll.set_child(self.flow)
        self.append(scroll)
        
        # Sort by index
        if classmap_data:
            sorted_items = sorted(classmap_data.items(), key=lambda item: item[1]['index'])
            
            for label, info in sorted_items:
                color = info['color'] # [r, g, b]
                
                # Item Container
                item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                
                # Color Swatch
                swatch = Gtk.DrawingArea()
                swatch.set_content_width(12)
                swatch.set_content_height(12)
                swatch.set_draw_func(self._draw_swatch, color)
                
                lbl = Gtk.Label(label=label)
                lbl.add_css_class("caption")
                lbl.set_max_width_chars(25)
                lbl.set_ellipsize(3) # pango.EllipsizeMode.END
                
                item_box.append(swatch)
                item_box.append(lbl)
                
                self.flow.append(item_box)
            
    def _draw_swatch(self, area, cr, width, height, color):
        if color and len(color) >= 3:
            r, g, b = color[:3]
            # Fill
            cr.set_source_rgba(r/255.0, g/255.0, b/255.0, 1.0)
            cr.rectangle(1, 1, width-2, height-2)
            cr.fill()
            
            # Border
            cr.set_source_rgba(0, 0, 0, 0.3)
            cr.set_line_width(1)
            cr.rectangle(0.5, 0.5, width-1, height-1)
            cr.stroke()
