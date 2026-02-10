import gi
gi.require_version('Gtk', '4.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, Pango, PangoCairo
import math

class NativeBarChart(Gtk.DrawingArea):
    def __init__(self, title, unit, color=(0.2, 0.6, 1.0)):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_size_request(300, 250)
        
        self.set_draw_func(self.on_draw)
        
        # Interaction
        self.hover_index = None
        controller = Gtk.EventControllerMotion.new()
        controller.connect("motion", self.on_motion)
        controller.connect("leave", self.on_leave)
        self.add_controller(controller)
        
        self.title = title
        self.unit = unit
        self.base_color = color
        self.labels = []
        self.values = []
        self.y_max = 1.0

        self.margin_left = 60
        self.margin_bottom = 80 # Room for rotated labels
        self.margin_top = 40
        self.margin_right = 20

    def set_data(self, labels, values):
        self.labels = labels
        self.values = values
        
        max_val = max(values) if values else 1.0
        self.y_max = max_val * 1.1 if max_val > 0 else 1.0
        self.queue_draw()

    def on_motion(self, controller, x, y):
        w = self.get_width()
        gw = w - self.margin_left - self.margin_right
        if not self.values or gw <= 0: return
        
        bar_w_total = gw / len(self.values)
        if x < self.margin_left or x > w - self.margin_right:
            self.hover_index = None
        else:
            idx = int((x - self.margin_left) / bar_w_total)
            self.hover_index = idx if 0 <= idx < len(self.values) else None
            
        self.queue_draw()

    def on_leave(self, controller):
        self.hover_index = None
        self.queue_draw()

    def on_draw(self, area, cr, width, height):
        # Background
        cr.set_source_rgb(0.97, 0.97, 0.97)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        gw = width - self.margin_left - self.margin_right
        gh = height - self.margin_top - self.margin_bottom
        
        if not self.values:
            return

        # 1. Grid
        self._draw_grid(cr, width, height, gw, gh)
        
        # 2. Bars
        self._draw_bars(cr, width, height, gw, gh)
        
        # 3. Title
        layout = self.create_pango_layout(self.title)
        layout.set_font_description(Pango.FontDescription("Sans Bold 11"))
        cr.move_to(self.margin_left, 10)
        cr.set_source_rgb(0.2, 0.2, 0.2)
        PangoCairo.show_layout(cr, layout)

    def _draw_grid(self, cr, w, h, gw, gh):
        cr.set_line_width(1)
        steps = 4
        for i in range(steps + 1):
            y = self.margin_top + (gh * i / steps)
            cr.set_source_rgba(0, 0, 0, 0.08)
            cr.move_to(self.margin_left, y)
            cr.line_to(w - self.margin_right, y)
            cr.stroke()
            
            val = self.y_max * (1 - i/steps)
            label_text = f"{val:.1f} {self.unit}"
            layout = self.create_pango_layout(label_text)
            layout.set_font_description(Pango.FontDescription("Sans 8"))
            ink, logical = layout.get_extents()
            cr.move_to(self.margin_left - (logical.width/Pango.SCALE) - 10, y - (logical.height/Pango.SCALE)/2)
            cr.set_source_rgb(0.4, 0.4, 0.4)
            PangoCairo.show_layout(cr, layout)

    def _draw_bars(self, cr, w, h, gw, gh):
        n = len(self.values)
        bar_space = gw / n
        bar_w = bar_space * 0.7
        offset = (bar_space - bar_w) / 2
        
        for i, (label, val) in enumerate(zip(self.labels, self.values)):
            bx = self.margin_left + i * bar_space + offset
            bh = (val / self.y_max) * gh
            by = self.margin_top + gh - bh
            
            # Bar Color
            if i == self.hover_index:
                cr.set_source_rgba(self.base_color[0], self.base_color[1], self.base_color[2], 1.0)
            else:
                cr.set_source_rgba(self.base_color[0], self.base_color[1], self.base_color[2], 0.7)
                
            self._draw_round_rectangle(cr, bx, by, bar_w, bh, 3)
            cr.fill()
            
            # Label
            cr.save()
            cr.move_to(bx + bar_w/2, h - self.margin_bottom + 10)
            cr.rotate(math.pi / 4) # 45 degrees
            
            layout = self.create_pango_layout(label)
            layout.set_font_description(Pango.FontDescription("Sans 8"))
            layout.set_width(int(100 * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            
            cr.set_source_rgb(0.3, 0.3, 0.3)
            PangoCairo.show_layout(cr, layout)
            cr.restore()
            
            # Hover Tooltip
            if i == self.hover_index:
                self._draw_tooltip(cr, bx + bar_w/2, by, f"{val:.2f} {self.unit}", w)

    def _draw_tooltip(self, cr, px, py, text, w):
        layout = self.create_pango_layout()
        layout.set_markup(f"<b>{text}</b>")
        layout.set_font_description(Pango.FontDescription("Sans 9"))
        ink, logical = layout.get_extents()
        
        tw = (logical.width / Pango.SCALE) + 12
        th = (logical.height / Pango.SCALE) + 8
        tx = px - tw / 2
        ty = py - th - 10
        
        if tx < 0: tx = 5
        if tx + tw > w: tx = w - tw - 5
        
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.8)
        self._draw_round_rectangle(cr, tx, ty, tw, th, 4)
        cr.fill()
        
        cr.move_to(tx + 6, ty + 4)
        cr.set_source_rgb(1, 1, 1)
        PangoCairo.show_layout(cr, layout)

    def _draw_round_rectangle(self, cr, x, y, width, height, radius):
        if height < radius * 2: radius = height / 2
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -math.pi/2, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi/2)
        cr.arc(x + radius, y + height - radius, radius, math.pi/2, math.pi)
        cr.arc(x + radius, y + radius, radius, math.pi, 3*math.pi/2)
        cr.close_path()
