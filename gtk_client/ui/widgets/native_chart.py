import gi
gi.require_version('Gtk', '4.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, Pango, PangoCairo
import math

class NativeChart(Gtk.DrawingArea):
    def __init__(self, title, unit, color=(0.2, 0.4, 0.8)):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_size_request(300, 200)
        
        self.set_draw_func(self.on_draw)
        
        # Interaction State
        self.hover_time = None 
        self.hover_active = False
        self.sync_group = [] # List of other NativeChart instances
        
        controller = Gtk.EventControllerMotion.new()
        controller.connect("motion", self.on_motion)
        controller.connect("leave", self.on_leave)
        self.add_controller(controller)
        
        self.title = title
        self.unit = unit
        self.line_color = color
        self.data_points = [] 
        self.normalized_points = [] 
        self.y_max = 1.0
        self.x_max = 1.0

        self.margin_left = 60
        self.margin_bottom = 30
        self.margin_top = 40
        self.margin_right = 20

    def sync_with(self, other):
        if other not in self.sync_group:
            self.sync_group.append(other)

    def set_data(self, points):
        if not points: 
            self.data_points = []
            self.normalized_points = []
            self.queue_draw()
            return
            
        self.data_points = points
        t0 = points[0][0]
        self.normalized_points = [(p[0] - t0, p[1]) for p in points]
        
        max_val = max(p[1] for p in self.normalized_points) if self.normalized_points else 1.0
        self.y_max = max_val * 1.1 if max_val > 0 else 1.0
        
        self.x_max = self.normalized_points[-1][0]
        if self.x_max == 0: self.x_max = 1.0
        
        self.queue_draw()

    def on_motion(self, controller, x, y):
        graph_w = self.get_width() - self.margin_left - self.margin_right
        if graph_w <= 0: return
        
        # Calculate time at this X
        t_hover = ((x - self.margin_left) / graph_w) * self.x_max
        t_hover = max(0, min(self.x_max, t_hover))
        
        self._internal_set_hover(t_hover)
        for other in self.sync_group:
            other._internal_set_hover(t_hover)

    def on_leave(self, controller):
        self._internal_clear_hover()
        for other in self.sync_group:
            other._internal_clear_hover()

    def _internal_set_hover(self, t_hover):
        self.hover_active = True
        self.hover_time = t_hover
        self.queue_draw()

    def _internal_clear_hover(self):
        self.hover_active = False
        self.hover_time = None
        self.queue_draw()

    def on_draw(self, area, cr, width, height):
        # 1. Background
        cr.set_source_rgb(0.97, 0.97, 0.97)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        graph_w = width - self.margin_left - self.margin_right
        graph_h = height - self.margin_top - self.margin_bottom
        
        if not self.normalized_points:
            self._draw_no_data(cr, width, height)
            return

        # 2. Grid
        self._draw_grid(cr, width, height, graph_w, graph_h)
        
        # 3. Data
        self._draw_data(cr, width, height, graph_w, graph_h)
        
        # 4. Interaction (Sync-aware)
        if self.hover_active and self.hover_time is not None:
            self._draw_hover(cr, width, height, graph_w, graph_h)

        # 5. Title
        layout = self.create_pango_layout(self.title)
        layout.set_font_description(Pango.FontDescription("Sans Bold 11"))
        cr.move_to(self.margin_left, 10)
        cr.set_source_rgb(0.2, 0.2, 0.2)
        PangoCairo.show_layout(cr, layout)

    def _draw_no_data(self, cr, w, h):
        layout = self.create_pango_layout("No Data")
        ink, logical = layout.get_extents()
        cr.move_to((w - (logical.width / Pango.SCALE))/2, (h - (logical.height / Pango.SCALE))/2)
        cr.set_source_rgb(0.5, 0.5, 0.5)
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

    def _draw_data(self, cr, w, h, gw, gh):
        path_points = []
        for t, v in self.normalized_points:
            x = self.margin_left + (t / self.x_max) * gw
            y = self.margin_top + (1 - (v / self.y_max)) * gh
            path_points.append((x,y))
            
        # Area
        cr.set_source_rgba(self.line_color[0], self.line_color[1], self.line_color[2], 0.1)
        cr.move_to(self.margin_left, h - self.margin_bottom)
        for x, y in path_points:
            cr.line_to(x, y)
        cr.line_to(path_points[-1][0], h - self.margin_bottom)
        cr.close_path()
        cr.fill()
        
        # Line
        cr.set_source_rgb(*self.line_color)
        cr.set_line_width(2)
        first = True
        for x, y in path_points:
            if first:
                cr.move_to(x, y)
                first = False
            else:
                cr.line_to(x, y)
        cr.stroke()

    def _draw_hover(self, cr, w, h, gw, gh):
        # Find closest point based on shared hover_time
        closest_point = min(self.normalized_points, key=lambda p: abs(p[0] - self.hover_time))
        
        px = self.margin_left + (closest_point[0] / self.x_max) * gw
        py = self.margin_top + (1 - (closest_point[1] / self.y_max)) * gh
        
        # Vertical Guide
        cr.set_source_rgba(0, 0, 0, 0.2)
        cr.set_line_width(1)
        cr.move_to(px, self.margin_top)
        cr.line_to(px, h - self.margin_bottom)
        cr.stroke()
        
        # Point
        cr.arc(px, py, 4, 0, 2*math.pi)
        cr.set_source_rgb(1, 1, 1)
        cr.fill_preserve()
        cr.set_source_rgb(*self.line_color)
        cr.set_line_width(2)
        cr.stroke()
        
        # Tooltip
        text = f"{closest_point[1]:.2f} {self.unit}\n{closest_point[0]:.1f}s"
        layout = self.create_pango_layout()
        layout.set_markup(f"<b>{text}</b>")
        layout.set_font_description(Pango.FontDescription("Sans 9"))
        ink, logical = layout.get_extents()
        
        tw = (logical.width / Pango.SCALE) + 12
        th = (logical.height / Pango.SCALE) + 8
        tx = px + 10
        ty = py - th - 10
        
        if tx + tw > w: tx = px - tw - 10
        if ty < 0: ty = py + 10
        
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.8)
        self._draw_round_rectangle(cr, tx, ty, tw, th, 4)
        cr.fill()
        
        cr.move_to(tx + 6, ty + 4)
        cr.set_source_rgb(1, 1, 1)
        PangoCairo.show_layout(cr, layout)

    def _draw_round_rectangle(self, cr, x, y, width, height, radius):
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -math.pi/2, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi/2)
        cr.arc(x + radius, y + height - radius, radius, math.pi/2, math.pi)
        cr.arc(x + radius, y + radius, radius, math.pi, 3*math.pi/2)
        cr.close_path()
