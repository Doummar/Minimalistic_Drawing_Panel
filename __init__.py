# Minimalistic Drawing Panel
# Created by Adel Aitah
# GitHub: https://github.com/Doummar/Minimalistic_Drawing_Panel
# Copyright (c) 2026 Adel Aitah — All rights reserved
"""
Minimalistic Drawing Panel — Anki handwriting addon
Low latency, smooth strokes, Surface Pen support,
automatic dark/light mode, configurable toolbar visibility.
"""

from aqt import mw, gui_hooks
from aqt.qt import *

ADDON_NAME = "Minimalistic Drawing Panel"
ADDON_AUTHOR  = "Adel Aitah"
ADDON_VERSION = "1.0.0"
ADDON_URL     = "https://github.com/Doummar/Minimalistic_Drawing_Panel"
HANDLE = 12

# ── Config ────────────────────────────────────────────────────────────────────

def _cfg():
    return mw.addonManager.getConfig(__name__) or {}

def _save_cfg(c):
    mw.addonManager.writeConfig(__name__, c)

def _pen_key():
    return _cfg().get("pen_key", "½")

def _barrel_enabled():
    return _cfg().get("barrel_enabled", True)

def _barrel_action():
    return _cfg().get("barrel_action", "toggle")

# ── Theme helpers ─────────────────────────────────────────────────────────────

_DARK_CACHE = [None]

def _is_dark():
    if _DARK_CACHE[0] is None:
        _DARK_CACHE[0] = QApplication.palette().window().color().lightness() < 128
    return _DARK_CACHE[0]

def _invalidate_dark_cache():
    _DARK_CACHE[0] = None

def _ink():
    """Theme-aware foreground colour for icons."""
    return QColor("#eeeeee") if _is_dark() else QColor("#1a1814")

def _th():
    """
    Return a dict of theme-aware colours for the settings panel.
    Uses the live Qt palette so it works in both light and dark Anki.
    """
    pal  = QApplication.palette()
    base = pal.base().color().name()          # input field bg
    win  = pal.window().color().name()        # dialog bg
    txt  = pal.windowText().color().name()    # normal text
    dim  = pal.placeholderText().color().name() if hasattr(pal, 'placeholderText') \
           else ("#aaa" if not _is_dark() else "#777")
    bdr  = "#555" if _is_dark() else "#ddd"
    hdr  = "#888" if _is_dark() else "#999"
    act  = pal.highlight().color().name()
    return dict(base=base, win=win, txt=txt, dim=dim,
                bdr=bdr, hdr=hdr, act=act)

# ── Stroke rendering ──────────────────────────────────────────────────────────

def _smooth_stroke(painter, pts, color, width, clip_rect):
    if len(pts) < 2:
        return
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.setClipRect(clip_rect)
    painter.setPen(QPen(color, max(0.5, width),
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin))
    p1 = p2 = pts[0]; p3 = pts[1]
    path = QPainterPath(QPointF((p1.x()+p2.x())/2, (p1.y()+p2.y())/2))
    for i in range(1, len(pts)):
        p1, p2, p3 = p2, p3, pts[i]
        path.quadTo(p2, QPointF((p2.x()+p3.x())/2, (p2.y()+p3.y())/2))
    path.lineTo(p3)
    painter.drawPath(path)
    painter.restore()


def _eraser_stroke(painter, pts, width, clip_rect):
    if len(pts) < 2:
        return
    painter.save()
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    painter.setClipRect(clip_rect)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(Qt.GlobalColor.transparent, width,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin))
    p1 = p2 = pts[0]; p3 = pts[1]
    path = QPainterPath(QPointF((p1.x()+p2.x())/2, (p1.y()+p2.y())/2))
    for i in range(1, len(pts)):
        p1, p2, p3 = p2, p3, pts[i]
        path.quadTo(p2, QPointF((p2.x()+p3.x())/2, (p2.y()+p3.y())/2))
    path.lineTo(p3)
    painter.drawPath(path)
    painter.restore()

# ── Cursors ───────────────────────────────────────────────────────────────────

def _pen_cursor():
    return QCursor(Qt.CursorShape.CrossCursor)

def _eraser_cursor():
    ink = _ink()
    px = QPixmap(24, 24); px.fill(Qt.GlobalColor.transparent)
    pp = QPainter(px); pp.setRenderHint(QPainter.RenderHint.Antialiasing)
    pp.setPen(QPen(ink, 1.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    pp.drawPolygon(QPolygonF([QPointF(4,17), QPointF(16,5),
                               QPointF(20,9), QPointF(8,21), QPointF(4,17)]))
    pp.drawLine(QPointF(13,4), QPointF(19,10))
    pp.drawLine(QPointF(3,21), QPointF(21,21))
    pp.end()
    return QCursor(px, 8, 21)

# ── Icon factories ────────────────────────────────────────────────────────────

def _pen_pixmap(size, color):
    """
    Core pen/pencil icon renderer.
    2× HiDPI, fully transparent bg, no shadow, outline-only.
    color = QColor for the strokes.
    """
    dpr = 2
    px  = QPixmap(size * dpr, size * dpr)
    px.fill(Qt.GlobalColor.transparent)
    px.setDevicePixelRatio(dpr)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 24.0
    p.setPen(QPen(color, 1.7, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPolyline(QPolygonF([
        QPointF(12*s,19*s), QPointF(19*s,12*s),
        QPointF(22*s,15*s), QPointF(15*s,22*s), QPointF(12*s,19*s)]))
    p.drawPolyline(QPolygonF([
        QPointF(18*s,13*s), QPointF(16.5*s,5.5*s),
        QPointF(2*s,2*s),   QPointF(5.5*s,16.5*s),
        QPointF(13*s,18*s), QPointF(18*s,13*s)]))
    p.drawLine(QPointF(2*s,2*s), QPointF(7*s,7*s))
    p.end()
    return px


def _make_pen_icon(size=22):
    """Theme-aware pen icon (for standalone use)."""
    return QIcon(_pen_pixmap(size, _ink()))


def _make_eraser_icon(size=20):
    ink = _ink()
    px = QPixmap(size, size); px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 20.0
    p.setPen(QPen(ink, 1.8, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(2*s, 6*s, 16*s, 9*s), 2*s, 2*s)
    p.drawLine(QPointF(2*s, 11*s), QPointF(18*s, 11*s))
    p.end()
    return QIcon(px)


def _make_clear_icon(size=20):
    ink = _ink()
    px = QPixmap(size, size); px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 20.0
    p.setPen(QPen(ink, 1.8, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(4*s, 8*s, 12*s, 10*s), 1.5*s, 1.5*s)
    p.drawLine(QPointF(2*s, 8*s), QPointF(18*s, 8*s))
    p.drawRoundedRect(QRectF(7*s, 5*s, 6*s, 3*s), 1.5*s, 1.5*s)
    p.drawLine(QPointF(8*s, 11*s), QPointF(8*s, 16*s))
    p.drawLine(QPointF(12*s, 11*s), QPointF(12*s, 16*s))
    p.end()
    return QIcon(px)

def _make_undo_icon(size=20):
    """Curved arrow pointing left (undo)."""
    ink = _ink()
    px = QPixmap(size, size); px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 20.0
    p.setPen(QPen(ink, 1.8, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    # Arc
    rect = QRectF(3*s, 4*s, 12*s, 12*s)
    p.drawArc(rect, 30*16, 240*16)
    # Arrowhead pointing left-down
    p.drawLine(QPointF(3*s, 10*s), QPointF(6*s, 7*s))
    p.drawLine(QPointF(3*s, 10*s), QPointF(7*s, 11*s))
    p.end()
    return QIcon(px)


def _make_redo_icon(size=20):
    """Curved arrow pointing right (redo)."""
    ink = _ink()
    px = QPixmap(size, size); px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 20.0
    p.setPen(QPen(ink, 1.8, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    rect = QRectF(5*s, 4*s, 12*s, 12*s)
    p.drawArc(rect, -60*16, -240*16)
    p.drawLine(QPointF(17*s, 10*s), QPointF(14*s, 7*s))
    p.drawLine(QPointF(17*s, 10*s), QPointF(13*s, 11*s))
    p.end()
    return QIcon(px)


# ── DrawZone ──────────────────────────────────────────────────────────────────

class DrawZone(QWidget):
    """
    Transparent overlay for handwriting.
    Surface Pen: nib tip = write, eraser tip = erase, barrel = configurable.
    Two-stage: instant wet-ink + post-release light smoothing.
    Palm rejection: only pointer-type Pen or Unknown from mouse is accepted;
    touch contacts with large contact area are ignored.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strokes      = []
        self._undo_stack   = []
        self._redo_stack   = []
        self._cur_pts      = []
        self._cur_color    = QColor("#1a1814")
        self._cur_width    = 3
        self._cur_erasing  = False
        self._drawing      = False
        self._erasing      = False
        self._active       = False
        self._pen_color    = QColor("#1a1814")
        self._pen_width    = 3
        self._eraser_width = 20
        self._pen_eraser_tip = False
        self._barrel_held    = False
        self._resizing         = False
        self._resize_left = self._resize_right = False
        self._resize_top  = self._resize_bottom = False
        self._resize_start     = QPoint()
        self._resize_start_geo = QRect()
        self._locked = _cfg().get("zone_locked", False)
        # Erase mode: set by toolbar ("dot" or "line")
        self._erase_mode = "dot"
        # Writing mode: affects jitter filter and smoothing
        self._writing_mode = "balanced"
        # Palm rejection: track pointer IDs that are pen
        self._active_pointer_id = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        QTimer.singleShot(0, self._update_mask)

    def _save_geometry(self):
        try:
            g = self.geometry()
            mw.pm.profile.update({"draw_zone_x": g.x(), "draw_zone_y": g.y(),
                                   "draw_zone_w": g.width(), "draw_zone_h": g.height()})
        except Exception:
            pass

    def _draw_area(self):
        return self.rect().adjusted(18, 18, -18, -18)

    def _edge_flags(self, pos):
        m = HANDLE; r = self.rect()
        return (pos.x() < m, pos.x() > r.width()-m,
                pos.y() < m, pos.y() > r.height()-m)

    def _update_mask(self):
        cs = 18; r = self.rect()
        if self._active:
            self.clearMask()
        else:
            reg  = QRegion(0, 0, cs, cs)
            reg += QRegion(r.width()-cs, 0,            cs, cs)
            reg += QRegion(0,            r.height()-cs, cs, cs)
            reg += QRegion(r.width()-cs, r.height()-cs, cs, cs)
            self.setMask(reg)

    # ── Public API ────────────────────────────────────────────────────────

    def set_active(self, active, erasing=False):
        self._active = active
        self._update_mask()
        self.update()
        if active:
            self.setCursor(_eraser_cursor() if erasing else _pen_cursor())
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_color(self, color):
        self._pen_color = QColor(color); self._erasing = False

    def set_eraser(self):  self._erasing = True
    def set_pen(self):     self._erasing = False

    def set_size(self, size):
        self._pen_width    = size
        self._eraser_width = max(size * 6, 20)

    def clear(self):
        if self._strokes:
            self._undo_stack.append([dict(s) for s in self._strokes])
            self._redo_stack.clear()
        self._strokes = []; self._cur_pts = []; self.update()

    def _want_erase(self):
        return self._barrel_held or self._pen_eraser_tip or self._erasing

    # ── Paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r   = self.rect()
        col = QColor(160, 160, 160, 120)
        p.setPen(QPen(col, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        lw = 8
        for cx,cy,dx,dy in [(0,0,1,1),(r.width(),0,-1,1),
                             (0,r.height(),1,-1),(r.width(),r.height(),-1,-1)]:
            p.drawLine(QPointF(cx,cy), QPointF(cx+dx*lw,cy))
            p.drawLine(QPointF(cx,cy), QPointF(cx,cy+dy*lw))
        inner = self._draw_area()
        p.setClipRect(inner)
        for s in self._strokes:
            if len(s['pts']) < 2: continue
            if s['erasing']:
                _eraser_stroke(p, s['pts'], s['width'], inner)
            else:
                _smooth_stroke(p, s['pts'], s['color'], s['width'], inner)
        if self._cur_pts and len(self._cur_pts) >= 2:
            if self._cur_erasing:
                _eraser_stroke(p, self._cur_pts, self._cur_width, inner)
            else:
                _smooth_stroke(p, self._cur_pts, self._cur_color, self._cur_width, inner)

    # ── Stroke helpers ────────────────────────────────────────────────────

    def _begin_stroke(self, pos):
        da   = self._draw_area()
        cpos = QPointF(max(float(da.left()), min(float(pos.x()), float(da.right()))),
                       max(float(da.top()),  min(float(pos.y()), float(da.bottom()))))
        erase = self._want_erase()
        self._drawing = True; self._cur_pts = [cpos]
        self._cur_color   = QColor(self._pen_color)
        self._cur_width   = self._eraser_width if erase else self._pen_width
        self._cur_erasing = erase

    def _add_point(self, pos):
        da   = self._draw_area()
        fpos = QPointF(max(float(da.left()), min(float(pos.x()), float(da.right()))),
                       max(float(da.top()),  min(float(pos.y()), float(da.bottom()))))
        if self._cur_pts:
            last = self._cur_pts[-1]
            dx = fpos.x()-last.x(); dy = fpos.y()-last.y()
            # Jitter threshold varies by writing mode
            # fast=0.5px, balanced=1.5px, precision=2.5px
            thresholds = {"fast": 0.25, "balanced": 2.25, "precision": 6.25}
            thr = thresholds.get(getattr(self, "_writing_mode", "balanced"), 2.25)
            if dx*dx + dy*dy < thr:
                return
        self._cur_pts.append(fpos)
        if len(self._cur_pts) >= 2:
            p0, p1 = self._cur_pts[-2], self._cur_pts[-1]
            pad = max(self._cur_width * 2, 8)
            self.update(QRect(int(min(p0.x(),p1.x())-pad), int(min(p0.y(),p1.y())-pad),
                              int(abs(p1.x()-p0.x())+pad*2), int(abs(p1.y()-p0.y())+pad*2)))
        else:
            self.update()

    def _commit_stroke(self):
        if self._drawing and len(self._cur_pts) >= 2:
            if self._cur_erasing and self._erase_mode == "line":
                # Line eraser: remove any stored stroke that the erase path touched
                self._line_erase(self._cur_pts)
            else:
                pts = self._cur_pts; n = len(pts)
                # Smoothing window by mode: fast=0 (none), balanced=1, precision=2
                win = {"fast": 0, "balanced": 1, "precision": 2}.get(
                    getattr(self, "_writing_mode", "balanced"), 1)
                if n >= 4 and win > 0:
                    out = []
                    for i in range(n):
                        lo = max(0,i-win); hi = min(n-1,i+win); cnt = hi-lo+1
                        out.append(QPointF(sum(pts[j].x() for j in range(lo,hi+1))/cnt,
                                           sum(pts[j].y() for j in range(lo,hi+1))/cnt))
                    pts = out
                # Save undo snapshot before modifying _strokes
                self._undo_stack.append([dict(s) for s in self._strokes])
                self._redo_stack.clear()
                self._strokes.append({'pts': pts, 'color': QColor(self._cur_color),
                                       'width': self._cur_width, 'erasing': self._cur_erasing})
        self._cur_pts = []; self._drawing = False; self.update()

    def undo(self):
        if not self._undo_stack: return
        self._redo_stack.append([dict(s) for s in self._strokes])
        self._strokes = self._undo_stack.pop()
        self._cur_pts = []; self.update()

    def redo(self):
        if not self._redo_stack: return
        self._undo_stack.append([dict(s) for s in self._strokes])
        self._strokes = self._redo_stack.pop()
        self._cur_pts = []; self.update()

    def _line_erase(self, erase_pts):
        """
        Line eraser: delete any stored ink stroke that the erase gesture touches.
        Uses bounding-box + point-proximity test — fast and accurate.
        Erase width sets proximity tolerance.
        """
        if not erase_pts:
            return
        tol = self._cur_width / 2.0 + 4.0  # touch tolerance in pixels
        tol_sq = tol * tol

        def seg_dist_sq(px, py, ax, ay, bx, by):
            """Squared distance from point (px,py) to segment (ax,ay)-(bx,by)."""
            dx = bx - ax; dy = by - ay
            if dx == 0 and dy == 0:
                return (px-ax)**2 + (py-ay)**2
            t = max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)))
            return (px - ax - t*dx)**2 + (py - ay - t*dy)**2

        def stroke_touched(stroke_pts, erase_pts, tol_sq):
            for ep in erase_pts:
                ex, ey = ep.x(), ep.y()
                for i in range(len(stroke_pts) - 1):
                    sp0 = stroke_pts[i]; sp1 = stroke_pts[i+1]
                    if seg_dist_sq(ex, ey, sp0.x(), sp0.y(), sp1.x(), sp1.y()) <= tol_sq:
                        return True
            return False

        kept = []
        changed = False
        for s in self._strokes:
            if not s.get('erasing', False):
                if stroke_touched(s['pts'], erase_pts, tol_sq):
                    changed = True  # drop this stroke
                    continue
            kept.append(s)
        if changed:
            self._undo_stack.append([dict(s) for s in self._strokes])
            self._redo_stack.clear()
            self._strokes = kept

    # ── Mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        btn = event.button()
        key = _pen_key()

        if btn == Qt.MouseButton.MiddleButton:
            # Middle click = toggle pen on/off (only action)
            _toggle_pen(); event.accept(); return

        if btn != Qt.MouseButton.LeftButton:
            is_toggle = (
                (key == "mouse_4" and btn == Qt.MouseButton.XButton1) or
                (key == "mouse_5" and btn == Qt.MouseButton.XButton2))
            if is_toggle:
                _toggle_pen(); event.accept(); return
            event.ignore()
            tgt = QApplication.widgetAt(event.globalPosition().toPoint())
            if tgt and tgt is not self: QApplication.sendEvent(tgt, event)
            return

        pos = event.position().toPoint()
        L,R,T,B = self._edge_flags(pos)
        if (L or R or T or B) and not self._locked:
            self._resizing = True
            self._resize_left=L; self._resize_right=R
            self._resize_top=T;  self._resize_bottom=B
            self._resize_start     = event.globalPosition().toPoint()
            self._resize_start_geo = self.geometry()
            return
        if self._active:
            self._begin_stroke(pos)
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        pos  = event.position().toPoint()
        gpos = event.globalPosition().toPoint()
        if self._resizing:
            delta = gpos - self._resize_start
            geo   = QRect(self._resize_start_geo)
            if self._resize_left:   geo.setLeft  (geo.left()   + delta.x())
            if self._resize_right:  geo.setRight (geo.right()  + delta.x())
            if self._resize_top:    geo.setTop   (geo.top()    + delta.y())
            if self._resize_bottom: geo.setBottom(geo.bottom() + delta.y())
            if geo.width() > 80 and geo.height() > 80:
                self.setGeometry(geo)
                # Strokes preserved on resize — they clip to new draw area
                QTimer.singleShot(0, self._update_mask)
                self._save_geometry()
            self.update(); return
        L,R,T,B = self._edge_flags(pos)
        if   (L and T) or (R and B): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (R and T) or (L and B): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif L or R:                  self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif T or B:                  self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif self._active:
            self.setCursor(_eraser_cursor() if self._want_erase() else _pen_cursor())
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        if not (event.buttons() & Qt.MouseButton.LeftButton and self._drawing):
            if not self._resizing: event.ignore()
            return
        self._add_point(pos)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.accept(); return
        self._commit_stroke(); self._resizing = False

    # ── Tablet (Surface Pen) ──────────────────────────────────────────────

    def tabletEvent(self, event):
        et = event.type()
        if et == QEvent.Type.TabletPress:
            pt = event.pointerType()
            if pt == QPointingDevice.PointerType.Finger:
                event.ignore(); return
            self._pen_eraser_tip = (pt == QPointingDevice.PointerType.Eraser)
            raw_barrel = bool(event.buttons() & Qt.MouseButton.RightButton)
            if raw_barrel and _barrel_enabled():
                action = _barrel_action()
                if action == "clear":
                    self.clear(); event.accept(); return
                elif action == "toggle":
                    _toggle_pen(); event.accept(); return
                self._barrel_held = True
            else:
                self._barrel_held = False
            if not self._active: _auto_activate()
            self._begin_stroke(event.position().toPoint())
            # Apply pressure to initial point
            pressure = event.pressure() if hasattr(event, "pressure") else 1.0
            if pressure > 0 and not self._cur_erasing:
                self._cur_width = max(0.5, self._pen_width * (0.4 + pressure * 0.8))
            self.setCursor(_eraser_cursor() if self._want_erase() else _pen_cursor())
            event.accept()
        elif et == QEvent.Type.TabletMove:
            if not self._drawing: event.accept(); return
            raw_barrel = bool(event.buttons() & Qt.MouseButton.RightButton)
            self._barrel_held = (raw_barrel and _barrel_enabled()
                                 and _barrel_action() == "erase")
            # Pressure-modulated width (Surface Pen)
            if not self._cur_erasing:
                pressure = event.pressure() if hasattr(event, "pressure") else 1.0
                if pressure > 0:
                    self._cur_width = max(0.5, self._pen_width * (0.4 + pressure * 0.8))
            self._add_point(event.position().toPoint())
            event.accept()
        elif et == QEvent.Type.TabletRelease:
            self._commit_stroke()
            self._pen_eraser_tip = False; self._barrel_held = False
            event.accept()
        else:
            event.ignore()


# ── Toolbar ───────────────────────────────────────────────────────────────────

class _HoldButton(QPushButton):
    """
    QPushButton that distinguishes short left-click from left-click-hold.
    Right-click is completely ignored (does nothing, no context menu).
    short_action : called on short left-click (< hold_ms)
    hold_action  : called when left button held >= hold_ms
    The hold_action replaces the clicked signal for long press.
    """
    def __init__(self, hold_ms=600, parent=None):
        super().__init__(parent)
        self._hold_ms     = hold_ms
        self._hold_timer  = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_active = False   # True while left button is held
        self._held_fired  = False   # True if hold action already triggered
        self.short_action = None
        self.hold_action  = None

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            e.ignore()   # right-click / middle-click → do nothing
            return
        self._held_fired = False
        self._hold_active = True
        self._hold_timer.start(self._hold_ms)
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            e.ignore(); return
        self._hold_timer.stop()
        if self._hold_active and not self._held_fired:
            # Short click → run short_action
            if self.short_action:
                self.short_action()
        self._hold_active = False
        e.accept()

    def _on_hold_timer(self):
        if self._hold_active:
            self._held_fired = True
            if self.hold_action:
                self.hold_action()

    def contextMenuEvent(self, e):
        e.ignore()   # suppress right-click context menus


class DrawToolbar(QWidget):
    """
    Minimalistic Drawing Panel toolbar.
    Collapsed: [pen] only.
    Expanded (pen active): [pen] [eraser] [thickness••] [trash]
    - Pen icon always uses theme ink colour (clean, no shadow)
    - Thickness dots show active ink colour
    - Hold thickness dots → colour picker
    - Hold eraser → erase mode (Line eraser / Dot eraser)
    - No toolbar background
    """

    BTN = 30

    # 5 thickness levels: (label, pt-value, dot-count)
    THICKNESS_LEVELS = [
        ("Thinnest", 1,  1),
        ("Thin",     2,  2),
        ("Medium",   4,  3),
        ("Thick",    7,  4),
        ("Thickest", 12, 5),
    ]

    def __init__(self, zone, parent=None):
        super().__init__(parent)
        self.zone      = zone
        self._drag_pos = None
        self._expanded = False  # tools hidden until pen is activated

        try:
            self._current_color = QColor(mw.pm.profile.get("draw_pen_color","#1a1814"))
        except Exception:
            self._current_color = QColor("#1a1814")

        cfg = _cfg()
        saved_sz = cfg.get("pen_size", 4)
        self._thick_idx = 2  # default medium
        for i, (_, v, _) in enumerate(self.THICKNESS_LEVELS):
            if saved_sz <= v:
                self._thick_idx = i; break

        # Erase mode: "dot" (default) or "line"
        self._erase_mode = cfg.get("erase_mode", "dot")

        # Writing mode: "fast" / "balanced" / "precision"
        self._writing_mode = cfg.get("writing_mode", "balanced")

        # (long-press handled by _HoldButton — no separate timers needed)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        self._layout = lay

        # ── 1. Pen button (always visible) ────────────────────────────────
        self.pen_btn = _HoldButton(hold_ms=600)
        self.pen_btn.setFixedSize(self.BTN, self.BTN)
        self.pen_btn.setCheckable(True)
        self.pen_btn.setToolTip(f"{ADDON_NAME} — click to draw, hold for writing mode")
        self.pen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pen_btn.short_action = self._on_pen_click
        self.pen_btn.hold_action  = self._show_pen_menu
        self.pen_btn._hold_timer.timeout.connect(self.pen_btn._on_hold_timer)
        lay.addWidget(self.pen_btn)

        # ── 2. Eraser (hidden until expanded) ────────────────────────────
        self.eraser_btn = _HoldButton(hold_ms=600)
        self.eraser_btn.setFixedSize(self.BTN, self.BTN)
        self.eraser_btn.setToolTip("Eraser — click to activate, hold for mode")
        self.eraser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eraser_btn.short_action = self._activate_eraser
        self.eraser_btn.hold_action  = self._show_erase_menu
        self.eraser_btn._hold_timer.timeout.connect(self.eraser_btn._on_hold_timer)
        lay.addWidget(self.eraser_btn)
        self.eraser_btn.hide()

        # ── 3. Thickness / colour button (hidden until expanded) ──────────
        self.thick_btn = _HoldButton(hold_ms=600)
        self.thick_btn.setFixedSize(self.BTN, self.BTN)
        self.thick_btn.setToolTip("Thickness — click to cycle, hold for colour")
        self.thick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thick_btn.short_action = self._cycle_thickness_click
        self.thick_btn.hold_action  = self._on_color
        self.thick_btn._hold_timer.timeout.connect(self.thick_btn._on_hold_timer)
        lay.addWidget(self.thick_btn)
        self.thick_btn.hide()

        # ── 4. Clear all (hidden until expanded) ──────────────────────────
        self.clear_btn = QPushButton()
        self.clear_btn.setFixedSize(self.BTN, self.BTN)
        self.clear_btn.setToolTip("Clear all strokes")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(zone.clear)
        lay.addWidget(self.clear_btn)
        self.clear_btn.hide()

        # ── 5. Undo button (hidden by default, shown in "full" mode) ──────
        self.undo_btn = QPushButton()
        self.undo_btn.setFixedSize(self.BTN, self.BTN)
        self.undo_btn.setToolTip("Undo  (Alt+Z)")
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.clicked.connect(lambda: zone.undo())
        lay.addWidget(self.undo_btn)
        self.undo_btn.hide()

        # ── 6. Redo button (hidden by default, shown in "full" mode) ──────
        self.redo_btn = QPushButton()
        self.redo_btn.setFixedSize(self.BTN, self.BTN)
        self.redo_btn.setToolTip("Redo  (Alt+Y)")
        self.redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_btn.clicked.connect(lambda: zone.redo())
        lay.addWidget(self.redo_btn)
        self.redo_btn.hide()

        self._tools = [self.eraser_btn, self.thick_btn, self.clear_btn,
                       self.undo_btn,   self.redo_btn]

        # Visibility mode: "minimal" | "standard" | "full"
        self._visibility_mode = _cfg().get("visibility_mode", "standard")

        self._apply_thickness()
        self._refresh_icons()
        self._update_styles()
        self.adjustSize()
        zone.set_color(self._current_color)
        zone._pen_color = QColor(self._current_color)

        # Tiny toggle dot
        self._eye_btn = _HoldButton(hold_ms=9999, parent=mw)  # no hold action
        self._eye_btn.setFixedSize(10, 10)
        self._eye_btn.setToolTip(f"Show/hide {ADDON_NAME} toolbar")
        self._eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._eye_btn.short_action = self._toggle_visibility
        self._eye_btn._hold_timer.timeout.connect(self._eye_btn._on_hold_timer)
        self._toolbar_visible = _cfg().get("toolbar_visible", True)
        self._update_eye_style()
        self._apply_visibility()
        self._eye_btn.show()
        self._eye_btn.raise_()

    # ── Eye dot ───────────────────────────────────────────────────────────

    def _update_eye_style(self):
        dark = _is_dark()
        col = ("rgba(120,120,120,180)" if dark else "rgba(80,80,80,160)") \
              if self._toolbar_visible else "rgba(180,80,80,200)"
        self._eye_btn.setStyleSheet(f"""
            QPushButton {{
                border-radius: 5px; background: {col}; border: none;
            }}
            QPushButton:hover {{ background: rgba(100,100,220,200); }}
        """)

    def _toggle_visibility(self):
        # Re-entrancy guard: prevent double-toggle if clicked rapidly
        if getattr(self, '_toggling', False):
            return
        self._toggling = True
        try:
            self._toolbar_visible = not self._toolbar_visible
            self._update_eye_style()
            self._apply_visibility()
            try: c = _cfg(); c["toolbar_visible"] = self._toolbar_visible; _save_cfg(c)
            except Exception: pass
        finally:
            self._toggling = False

    def _apply_visibility(self):
        """
        Show/hide toolbar buttons based on:
        1. _toolbar_visible  (eye-dot master switch)
        2. _expanded         (pen must be active to show tools)
        3. _visibility_mode  (minimal / standard / full)
        """
        # minimal:  pen + thick
        # standard: pen + eraser + thick + clear
        # full:     pen + eraser + thick + clear + undo + redo
        mode = getattr(self, "_visibility_mode", "standard")
        show_eraser = mode in ("standard", "full")
        show_thick  = True                           # always shown
        show_clear  = mode in ("standard", "full")
        show_undo   = mode == "full"
        show_redo   = mode == "full"

        vis = self._toolbar_visible
        exp = self._expanded
        self.pen_btn.setVisible(vis)
        self.eraser_btn.setVisible(vis and exp and show_eraser)
        self.thick_btn.setVisible(vis and exp and show_thick)
        self.clear_btn.setVisible(vis and exp and show_clear)
        self.undo_btn.setVisible(vis and exp and show_undo)
        self.redo_btn.setVisible(vis and exp and show_redo)
        self._eye_btn.setToolTip(
            f"Hide {ADDON_NAME} toolbar" if vis
            else f"Show {ADDON_NAME} toolbar")
        # adjustSize in a deferred call avoids recursive layout events
        QTimer.singleShot(0, self.adjustSize)
        QTimer.singleShot(10, self._position_eye_btn)

    def _position_eye_btn(self):
        try:
            if not hasattr(self, '_eye_btn') or self._eye_btn is None:
                return
            if not self._eye_btn.isVisible() and not self.isVisible():
                return
            x = self.x() + self.width() + 4
            y = self.y() + max(0, (self.height() - 10) // 2)
            self._eye_btn.move(x, y)
        except Exception:
            pass

    # ── Icons ─────────────────────────────────────────────────────────────

    def _make_thickness_icon(self, size):
        """
        Dot(s) icon in CURRENT INK COLOUR — acts as the colour indicator.
        1–5 dots for the 5 thickness levels.
        """
        _, _, dots = self.THICKNESS_LEVELS[self._thick_idx]
        col = self._current_color
        px = QPixmap(size, size); px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(col)
        r_map = {1: 4.5, 2: 3.5, 3: 2.8, 4: 2.3, 5: 2.0}
        r = r_map.get(dots, 2.5)
        spacing = (size - 2) / (dots + 1)
        cy = size / 2.0
        for i in range(dots):
            cx = spacing * (i + 1)
            p.drawEllipse(QPointF(cx, cy), r, r)
        p.end()
        return QIcon(px)

    def _refresh_icons(self):
        isz = self.BTN - 10
        self.pen_btn.setIcon(QIcon(_pen_pixmap(self.BTN - 6, _ink())))
        self.pen_btn.setIconSize(QSize(self.BTN - 6, self.BTN - 6))
        self.eraser_btn.setIcon(_make_eraser_icon(isz))
        self.eraser_btn.setIconSize(QSize(isz, isz))
        self.thick_btn.setIcon(self._make_thickness_icon(self.BTN - 4))
        self.thick_btn.setIconSize(QSize(self.BTN - 4, self.BTN - 4))
        self.clear_btn.setIcon(_make_clear_icon(isz))
        self.clear_btn.setIconSize(QSize(isz, isz))
        self.undo_btn.setIcon(_make_undo_icon(isz))
        self.undo_btn.setIconSize(QSize(isz, isz))
        self.redo_btn.setIcon(_make_redo_icon(isz))
        self.redo_btn.setIconSize(QSize(isz, isz))

    def _update_styles(self):
        dark  = _is_dark()
        fg    = "#eeeeee" if dark else "#1a1814"
        hover = "rgba(120,120,120,40)" if dark else "rgba(0,0,0,10)"
        r = self.BTN // 2
        self.pen_btn.setStyleSheet(f"""
            QPushButton {{
                border-radius: {r}px; border: none; color: {fg};
                background: transparent;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """)
        base_ss = f"""
            QPushButton {{
                border-radius: {r}px; border: none; color: {fg};
                background: transparent;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """
        for btn in self._tools:
            btn.setStyleSheet(base_ss)
        # Undo/redo slightly dimmed until there is history
        # (future enhancement — for now same style as other tools)

    def paintEvent(self, event):
        pass  # Transparent — no toolbar background

    # ── Writing mode ──────────────────────────────────────────────────────

    WRITING_MODES = [
        ("fast",      "Fast",      "Lowest latency, raw points"),
        ("balanced",  "Balanced",  "Default — smooth and responsive"),
        ("precision", "Precision", "Smoother, cleaner strokes"),
    ]

    def _show_pen_menu(self):
        """Hold pen icon → writing mode menu."""
        dark = _is_dark()
        bg   = "#2c2c2c" if dark else "#ffffff"
        txt  = "#eeeeee" if dark else "#222222"
        sel  = "#3a3a3a" if dark else "#f0f0f0"
        bdr  = "#444"    if dark else "#e0e0e0"
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {bg}; border: 1px solid {bdr};
                border-radius: 6px; padding: 4px 0; font-size: 11px;
            }}
            QMenu::item {{ padding: 5px 16px 5px 12px; color: {txt}; }}
            QMenu::item:selected {{ background: {sel}; }}
            QMenu::item:checked {{ font-weight: bold; }}
            QMenu::separator {{ height: 1px; background: {bdr}; margin: 2px 8px; }}
        """)
        acts = {}
        for val, label, desc in self.WRITING_MODES:
            a = menu.addAction(f"{label}  —  {desc}")
            a.setCheckable(True)
            a.setChecked(self._writing_mode == val)
            acts[a] = val

        def pick(action):
            if action in acts:
                self._set_writing_mode(acts[action])

        menu.triggered.connect(pick)
        pos = self.pen_btn.mapToGlobal(QPoint(0, self.pen_btn.height() + 4))
        menu.exec(pos)

    def _set_writing_mode(self, mode):
        self._writing_mode = mode
        self.zone._writing_mode = mode   # propagate to DrawZone
        self.pen_btn.setToolTip(
            f"{ADDON_NAME} — {mode.capitalize()} mode  (hold to change)")
        try: c = _cfg(); c["writing_mode"] = mode; _save_cfg(c)
        except Exception: pass

    # ── Collapse / Expand ─────────────────────────────────────────────────

    def _on_pen_click(self):
        """Toggle drawing on/off AND expand/collapse the tools."""
        # Toggle the checkable state manually since _HoldButton doesn't use clicked signal
        self.pen_btn.setChecked(not self.pen_btn.isChecked())
        chk = self.pen_btn.isChecked()
        self._expanded = chk
        self.zone.set_pen()
        self.zone.set_active(chk, erasing=False)
        self._apply_visibility()
        self._update_styles()
        self._clamp()
        QTimer.singleShot(0, self._position_eye_btn)

    def _clamp(self):
        if not self.parent(): return
        pw, ph = self.parent().width(), self.parent().height()
        self.move(max(8, min(self.x(), pw-self.width()-8)),
                  max(8, min(self.y(), ph-self.height()-8)))

    # ── Thickness ─────────────────────────────────────────────────────────

    def _apply_thickness(self):
        _, pt_val, _ = self.THICKNESS_LEVELS[self._thick_idx]
        self.zone.set_size(pt_val)
        label = self.THICKNESS_LEVELS[self._thick_idx][0]
        self.thick_btn.setToolTip(f"Thickness: {label} — click to cycle, hold for colour")
        try:
            c = _cfg(); c["pen_size"] = pt_val; _save_cfg(c)
        except Exception: pass

    def _cycle_thickness_click(self):
        """Short click on thickness dots → cycle to next level."""
        self._thick_idx = (self._thick_idx + 1) % len(self.THICKNESS_LEVELS)
        self._apply_thickness()
        self._refresh_icons()

    def _on_thick_released(self):
        pass  # kept for safety; _HoldButton handles this now

    # ── Eraser ────────────────────────────────────────────────────────────

    def _on_eraser_released(self):
        pass  # kept for safety; _HoldButton handles this now

    def _activate_eraser(self):
        self.zone.set_eraser()
        self.zone._erase_mode = self._erase_mode   # pass mode to zone
        self.zone.set_active(True, erasing=True)
        self.pen_btn.setChecked(True)
        self._update_styles()

    def _show_erase_menu(self):
        """Hold eraser → Line eraser / Dot eraser menu."""
        dark = _is_dark()
        bg   = "#2c2c2c" if dark else "#ffffff"
        txt  = "#eeeeee" if dark else "#222222"
        sel  = "#3a3a3a" if dark else "#f0f0f0"
        bdr  = "#444" if dark else "#e0e0e0"
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {bg}; border: 1px solid {bdr};
                border-radius: 6px; padding: 4px 0; font-size: 11px;
            }}
            QMenu::item {{ padding: 5px 16px 5px 12px; color: {txt}; }}
            QMenu::item:selected {{ background: {sel}; }}
            QMenu::item:checked {{ font-weight: bold; }}
        """)
        line_act = menu.addAction("Line eraser")
        dot_act  = menu.addAction("Dot eraser")
        line_act.setCheckable(True); line_act.setChecked(self._erase_mode == "line")
        dot_act.setCheckable(True);  dot_act.setChecked(self._erase_mode == "dot")

        def pick(action):
            self._erase_mode = "line" if action == line_act else "dot"
            self._activate_eraser()   # also sets zone._erase_mode
            try: c = _cfg(); c["erase_mode"] = self._erase_mode; _save_cfg(c)
            except Exception: pass

        menu.triggered.connect(pick)
        pos = self.eraser_btn.mapToGlobal(QPoint(0, self.eraser_btn.height() + 4))
        menu.exec(pos)

    # ── Colour ────────────────────────────────────────────────────────────

    def _on_color(self):
        """Colour picker — triggered by holding thickness dots."""
        col = QColorDialog.getColor(self._current_color, self, "Pick ink color")
        if col.isValid():
            self._current_color = col
            self.zone.set_color(col)
            self._refresh_icons()   # dots update immediately
            self._update_styles()
            try:
                mw.pm.profile["draw_pen_color"] = col.name()
                c = _cfg(); c["pen_color"] = col.name(); _save_cfg(c)
            except Exception: pass

    # ── Drag ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        btn = event.button(); key = _pen_key()
        if btn == Qt.MouseButton.RightButton:
            event.ignore(); return   # right-click on toolbar → no effect
        if btn == Qt.MouseButton.MiddleButton:
            _toggle_pen(); event.accept(); return
        if btn == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            return
        # XButton1/2
        if (key == "mouse_4" and btn == Qt.MouseButton.XButton1) or            (key == "mouse_5" and btn == Qt.MouseButton.XButton2):
            _toggle_pen(); event.accept(); return
        event.ignore()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or not self._drag_pos:
            event.ignore(); return
        self.move(event.globalPosition().toPoint() - self._drag_pos)

    def moveEvent(self, event):
        super().moveEvent(event)
        QTimer.singleShot(0, self._position_eye_btn)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: event.accept(); return
        self._drag_pos = None
        try:
            mw.pm.profile["draw_toolbar_x"] = self.x()
            mw.pm.profile["draw_toolbar_y"] = self.y()
        except Exception: pass


# ── Controller ────────────────────────────────────────────────────────────────

class Controller:
    def __init__(self):
        self._zone = None; self._toolbar = None

    def start(self):
        if self._zone is not None: return
        try:
            w, h = mw.width(), mw.height(); mg = 40
            self._zone = DrawZone(mw)
            try:
                zx=mw.pm.profile.get("draw_zone_x",mg); zy=mw.pm.profile.get("draw_zone_y",mg)
                zw=mw.pm.profile.get("draw_zone_w",w-mg*2); zh=mw.pm.profile.get("draw_zone_h",h-mg*2-60)
            except Exception:
                zx,zy,zw,zh = mg,mg,w-mg*2,h-mg*2-60
            self._zone.setGeometry(zx,zy,zw,zh)
            self._zone.show(); self._zone.raise_()
            self._toolbar = DrawToolbar(self._zone, mw)
            self._toolbar.adjustSize()
            tw=self._toolbar.sizeHint().width(); th=self._toolbar.sizeHint().height()
            try:
                sx=mw.pm.profile.get("draw_toolbar_x",w-tw-20)
                sy=mw.pm.profile.get("draw_toolbar_y",h-th-20)
            except Exception:
                sx,sy = w-tw-20, h-th-20
            self._toolbar.move(sx,sy)
            self._toolbar.show(); self._toolbar.raise_()
            mw.installEventFilter(self)
        except Exception as e:
            print(f"{ADDON_NAME} start error:", e)

    def eventFilter(self, obj, event):
        if event.type()==QEvent.Type.Resize and self._toolbar:
            w,h=mw.width(),mw.height()
            self._toolbar.adjustSize()
            self._toolbar.move(w-self._toolbar.sizeHint().width()-20,
                               h-self._toolbar.sizeHint().height()-20)
        return False


_controller = Controller()


def _auto_activate():
    tb = _controller._toolbar
    if tb and not tb.pen_btn.isChecked():
        tb.pen_btn.setChecked(True); tb._on_pen_click()

def _activate_pen():
    tb = _controller._toolbar
    if tb and not tb.pen_btn.isChecked():
        tb.pen_btn.setChecked(True); tb._on_pen_click()

def _deactivate_pen():
    tb = _controller._toolbar
    if tb and tb.pen_btn.isChecked():
        tb.pen_btn.setChecked(False); tb._on_pen_click()

def _toggle_pen():
    tb = _controller._toolbar
    if tb:
        tb.pen_btn.setChecked(not tb.pen_btn.isChecked()); tb._on_pen_click()

def _on_card_shown(*a, **kw):
    z = _controller._zone
    if z:
        if _cfg().get("auto_clear", True):
            z.clear()
        else:
            z._cur_pts = []; z._drawing = False
    _invalidate_dark_cache()
    tb = _controller._toolbar
    if tb:
        tb._refresh_icons(); tb._update_styles(); tb._update_eye_style()


# ── Key filter ────────────────────────────────────────────────────────────────

def _pen_key_label(key):
    return {"mouse_middle": "Middle mouse button",
            "mouse_4":      "Mouse button 4",
            "mouse_5":      "Mouse button 5"}.get(key, f"Key: {key}")


class _KeyFilter(QObject):
    def eventFilter(self, obj, event):
        key = _pen_key()
        if event.type() == QEvent.Type.MouseButtonPress:
            btn = event.button()
            # Middle click always toggles pen — the single allowed middle action
            if btn == Qt.MouseButton.MiddleButton:
                _toggle_pen(); return True
            # XButton1/2 toggle if configured
            if key.startswith("mouse_"):
                matched = (
                    (key=="mouse_4" and btn==Qt.MouseButton.XButton1) or
                    (key=="mouse_5" and btn==Qt.MouseButton.XButton2))
                if matched:
                    tb = _controller._toolbar
                    if tb and not tb.pen_btn.isChecked():
                        _toggle_pen(); return True
        if event.type() == QEvent.Type.KeyPress:
            z  = _controller._zone
            tb = _controller._toolbar
            pen_active = tb is not None and tb.pen_btn.isChecked()
            mod = event.modifiers()
            ctrl = bool(mod & Qt.KeyboardModifier.ControlModifier)
            alt  = bool(mod & Qt.KeyboardModifier.AltModifier)
            k    = event.key()
            # Undo/redo: ONLY intercept when drawing panel is active
            # This prevents conflict with Anki's own Ctrl+Z card controls.
            # Alt+Z / Alt+Y always work as safe drawing-only shortcuts.
            if z:
                if alt and k == Qt.Key.Key_Z:
                    z.undo(); return True
                if alt and k == Qt.Key.Key_Y:
                    z.redo(); return True
                if ctrl and k == Qt.Key.Key_Z and pen_active:
                    z.undo(); return True
                if ctrl and k == Qt.Key.Key_Y and pen_active:
                    z.redo(); return True
            if not key.startswith("mouse_"):
                matched = (
                    (key=="½" and (event.key()==0x00BD or event.text()=="½")) or
                    (key!="½" and event.text().upper()==key.upper()))
                if matched: _toggle_pen(); return True
        return False


_key_filter = _KeyFilter()


# ── Settings dialog ───────────────────────────────────────────────────────────

def _qlabel(text):
    l = QLabel(text); l.setWordWrap(True); return l

def _section_hdr(text):
    """Section header that respects the current theme."""
    t = _th()
    l = QLabel(text)
    l.setStyleSheet(
        f"font-weight:bold;font-size:10px;color:{t['hdr']};"
        "letter-spacing:1px;margin-top:10px;margin-bottom:2px;")
    return l


class _SettingsDialog(QDialog):
    BARREL_ACTION_OPTIONS = [
        ("toggle", "Toggle pen active / inactive"),
        ("clear",  "Delete all"),
    ]

    def __init__(self, current_key, zone_locked):
        super().__init__(mw)
        self.setWindowTitle(f"{ADDON_NAME} — Settings")
        self.setMinimumWidth(400)
        cfg = _cfg()
        t   = _th()   # theme colours, resolved once at dialog open

        self.result_key           = current_key
        self.result_locked        = zone_locked
        self.result_auto_clear    = cfg.get("auto_clear", True)
        self.result_barrel_en     = cfg.get("barrel_enabled", True)
        self.result_barrel_act    = cfg.get("barrel_action", "toggle")
        self.result_visibility_mode = cfg.get("visibility_mode", "standard")

        # ── Direct layout (no scroll — everything fits) ──────────────────
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(3)

        # ── Palette-aware style strings ───────────────────────────────────
        lbl_ss   = f"font-size:11px;color:{t['txt']};"
        dim_ss   = f"font-size:10px;color:{t['dim']};margin-left:2px;"
        combo_ss = (
            f"QComboBox{{font-size:11px;border:1px solid {t['bdr']};"
            f"border-radius:4px;padding:3px 8px;background:{t['base']};"
            f"color:{t['txt']};min-width:170px;}}"
            "QComboBox::drop-down{border:none;}"
            f"QComboBox QAbstractItemView{{font-size:11px;"
            f"background:{t['base']};color:{t['txt']};}}")
        cb_ss    = f"QCheckBox{{font-size:11px;color:{t['txt']};}}"
        key_ss   = (
            f"background:{t['base']};border-radius:5px;padding:7px 10px;"
            f"font-size:12px;font-weight:bold;border:1px solid {t['bdr']};"
            f"color:{t['txt']};")

        def row(label_text, widget):
            r = QHBoxLayout(); r.setSpacing(8)
            lbl = QLabel(label_text); lbl.setStyleSheet(lbl_ss)
            r.addWidget(lbl); r.addStretch(); r.addWidget(widget)
            lay.addLayout(r)

        # Title with pen icon
        title_row = QHBoxLayout(); title_row.setSpacing(8)
        pen_lbl = QLabel()
        pen_lbl.setPixmap(_pen_pixmap(18, _ink()))
        pen_lbl.setFixedSize(18, 18)
        title_row.addWidget(pen_lbl)
        title_lbl = QLabel(ADDON_NAME)
        title_lbl.setStyleSheet(f"font-size:14px;font-weight:bold;color:{t['txt']};")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)

        # ── PEN CONTROLS ─────────────────────────────────────────────────
        lay.addWidget(_section_hdr("PEN CONTROLS"))

        lbl_key = _qlabel("Toggle key / mouse button")
        lbl_key.setStyleSheet(lbl_ss)
        lay.addWidget(lbl_key)
        hint_key = _qlabel("Press any key or mouse button in this dialog to set it.")
        hint_key.setStyleSheet(dim_ss)
        lay.addWidget(hint_key)
        self._key_disp = QLabel(f"Current: {_pen_key_label(current_key)}")
        self._key_disp.setStyleSheet(key_ss)
        self._key_disp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_disp)
        lay.addSpacing(4)

        # Mouse middle button row removed per user request

        # ── SURFACE PEN SIDE BUTTON ───────────────────────────────────────
        lay.addSpacing(4)
        lay.addWidget(_section_hdr("SURFACE PEN SIDE BUTTON"))

        self._barrel_en_cb = QCheckBox("Side button enabled")
        self._barrel_en_cb.setStyleSheet(cb_ss)
        self._barrel_en_cb.setChecked(cfg.get("barrel_enabled", True))
        lay.addWidget(self._barrel_en_cb)

        self._barrel_combo = QComboBox()
        for val, lbl in self.BARREL_ACTION_OPTIONS:
            self._barrel_combo.addItem(lbl, val)
        cur_ba = cfg.get("barrel_action", "toggle")
        for i, (val, _) in enumerate(self.BARREL_ACTION_OPTIONS):
            if val == cur_ba: self._barrel_combo.setCurrentIndex(i); break
        self._barrel_combo.setStyleSheet(combo_ss)
        self._barrel_lbl = QLabel("Action")
        self._barrel_lbl.setStyleSheet(lbl_ss)
        barrel_row = QHBoxLayout(); barrel_row.setSpacing(8)
        barrel_row.addWidget(self._barrel_lbl)
        barrel_row.addStretch()
        barrel_row.addWidget(self._barrel_combo)
        lay.addLayout(barrel_row)

        # Info labels removed per user request

        def _on_barrel_toggle(state):
            en = bool(state)
            self._barrel_combo.setEnabled(en)
            self._barrel_lbl.setEnabled(en)
        self._barrel_en_cb.toggled.connect(_on_barrel_toggle)
        _on_barrel_toggle(cfg.get("barrel_enabled", True))

        # ── WRITING ───────────────────────────────────────────────────────
        lay.addWidget(_section_hdr("WRITING"))
        self._auto_clear_cb = QCheckBox("Auto-clear drawing on next card")
        self._auto_clear_cb.setStyleSheet(cb_ss)
        self._auto_clear_cb.setChecked(cfg.get("auto_clear", True))
        lay.addWidget(self._auto_clear_cb)


        # (Show toolbar removed — controlled via eye-dot on toolbar directly)

        # ── WRITING AREA ──────────────────────────────────────────────────
        lay.addWidget(_section_hdr("WRITING AREA"))
        self._lock_cb = QCheckBox("Lock drawing area (prevent accidental resize)")
        self._lock_cb.setStyleSheet(cb_ss)
        self._lock_cb.setChecked(zone_locked)
        lay.addWidget(self._lock_cb)

        # ── ABOUT ─────────────────────────────────────────────────────────
        lay.addWidget(_section_hdr("ABOUT"))
        about_lbl = QLabel(
            f"<b>{ADDON_NAME}</b>  v{ADDON_VERSION}<br>"
            f"Created by Adel")
        about_lbl.setStyleSheet(f"font-size:10px;color:{t['dim']};")
        lay.addWidget(about_lbl)

        # ── HELP ──────────────────────────────────────────────────────────
        lay.addWidget(_section_hdr("HELP"))

        btn_ss = (
            f"QPushButton{{background:transparent;border:1px solid {t['bdr']};"
            f"border-radius:5px;padding:5px 14px;font-size:11px;color:{t['txt']};}}"
            f"QPushButton:hover{{background:{t['base']};border-color:{t['txt']};}}")

        help_btn = QPushButton("Open Help Guide")
        help_btn.setStyleSheet(btn_ss)
        help_btn.clicked.connect(lambda: (_show_welcome(force=True), self.accept()))
        lay.addWidget(help_btn)

        issue_btn = QPushButton("⚑  Report an Issue")
        issue_btn.setStyleSheet(btn_ss)
        issue_btn.setToolTip("Opens GitHub Issues page")
        issue_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/Doummar/Minimalistic_Drawing_Panel/issues")))
        lay.addWidget(issue_btn)

        reset_btn = QPushButton("↺  Reset to Default")
        reset_btn.setStyleSheet(btn_ss)
        reset_btn.setToolTip("Restore all settings to default values")
        reset_btn.clicked.connect(self._reset_to_default)
        lay.addWidget(reset_btn)

        # ── Save / Cancel ─────────────────────────────────────────────────
        lay.addSpacing(10)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel)
        save_b = btns.button(QDialogButtonBox.StandardButton.Save)
        if save_b:
            save_b.setStyleSheet(
                "QPushButton{background:#2383e2;color:white;border:none;"
                "border-radius:5px;padding:5px 16px;font-weight:bold;}"
                "QPushButton:hover{background:#1a6fc7;}")
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.adjustSize()

    def _accept(self):
        self.result_locked          = self._lock_cb.isChecked()
        self.result_auto_clear      = self._auto_clear_cb.isChecked()
        self.result_barrel_en       = self._barrel_en_cb.isChecked()
        self.result_barrel_act      = self._barrel_combo.currentData()
        self.accept()

    def _reset_to_default(self):
        reply = QMessageBox.question(
            self, f"{ADDON_NAME} — Reset",
            "Reset all settings to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        # Apply defaults to config
        defaults = {
            "pen_key": "½", "pen_color": "#1a1814", "pen_size": 4,
            "erase_mode": "dot", "writing_mode": "balanced",
            "auto_clear": True, "toolbar_visible": True,
            "visibility_mode": "standard", "zone_locked": False,
            "barrel_enabled": True, "barrel_action": "toggle",
        }
        _save_cfg(defaults)
        # Update UI widgets to reflect defaults
        self._key_disp.setText(f"Current: {_pen_key_label('½')}")
        self.result_key = "½"
        self._auto_clear_cb.setChecked(True)
        self._lock_cb.setChecked(False)
        self._barrel_en_cb.setChecked(True)
        for i, (v, _) in enumerate(self.BARREL_ACTION_OPTIONS):
            if v == "toggle": self._barrel_combo.setCurrentIndex(i); break
        # Apply live to toolbar/zone
        tb = _controller._toolbar
        if tb:
            tb._current_color = QColor("#1a1814")
            tb._thick_idx = 2
            tb._erase_mode = "dot"
            tb._writing_mode = "balanced"
            tb.zone.set_color(QColor("#1a1814"))
            tb.zone._pen_color = QColor("#1a1814")
            tb.zone._writing_mode = "balanced"
            tb.zone._erase_mode = "dot"
            tb._apply_thickness()
            tb._refresh_icons()
            tb._update_styles()
        QMessageBox.information(self, f"{ADDON_NAME}", "Settings reset to default.")

    def _set_key(self, val):
        self.result_key = val
        self._key_disp.setText(f"Current: {_pen_key_label(val)}")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape: self.reject(); return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            super().keyPressEvent(e); return
        txt = e.text()
        if txt.strip(): self._set_key(txt)
        elif e.key() == 0x00BD: self._set_key("½")

    def mousePressEvent(self, e):
        if   e.button() == Qt.MouseButton.LeftButton:   super().mousePressEvent(e)
        elif e.button() == Qt.MouseButton.MiddleButton: self._set_key("mouse_middle")
        elif e.button() == Qt.MouseButton.XButton1:     self._set_key("mouse_4")
        elif e.button() == Qt.MouseButton.XButton2:     self._set_key("mouse_5")


# ── Welcome / help dialog ─────────────────────────────────────────────────────

def _show_welcome(force=False):
    """First-time welcome. Auto-shown once; reopenable from Settings."""
    cfg = _cfg()
    if not force and cfg.get("welcome_shown", False):
        return
    cfg["welcome_shown"] = True
    _save_cfg(cfg)

    t   = _th()
    dlg = QDialog(mw)
    dlg.setWindowTitle(f"{ADDON_NAME} — Guide")
    dlg.setMinimumWidth(460)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(26, 22, 26, 22)
    lay.setSpacing(8)

    # Title row with pen icon
    tr = QHBoxLayout(); tr.setSpacing(8)
    pi = QLabel(); pi.setPixmap(_pen_pixmap(20, _ink())); pi.setFixedSize(20,20)
    tr.addWidget(pi)
    tl = QLabel(ADDON_NAME)
    tl.setStyleSheet(f"font-size:16px;font-weight:bold;color:{t['txt']};")
    tr.addWidget(tl); tr.addStretch()
    lay.addLayout(tr)

    sub = QLabel("Write directly on your Anki cards using mouse, touch, or stylus.")
    sub.setWordWrap(True)
    sub.setStyleSheet(f"font-size:12px;color:{t['dim']};margin-bottom:4px;")
    lay.addWidget(sub)

    sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
    lay.addWidget(sep)

    def section(heading, items):
        h = QLabel(f"<b>{heading}</b>")
        h.setStyleSheet(f"font-size:12px;margin-top:6px;color:{t['txt']};")
        lay.addWidget(h)
        for item in items:
            r = QLabel(f"  • {item}"); r.setWordWrap(True)
            r.setStyleSheet(f"font-size:11px;color:{t['dim']};")
            lay.addWidget(r)

    section("What it does", [
        "Write & draw on any card during review",
        "Erase with the eraser tool (Line eraser or Dot eraser)",
        "Surface Pen: nib tip = write, eraser tip = erase automatically",
        "Side button = configurable (toggle pen / delete all)",
        "5 thickness levels — thickness dots show active ink colour",
        "Hold thickness dots to open colour picker",
        "Clear all strokes with the trash button",
        "Automatic dark / light mode",
        "Hide toolbar — tiny dot restores it",
    ])

    section("How to use", [
        "Click the pen icon to activate drawing (expands toolbar)",
        "Click again to collapse and deactivate",
        "Hold thickness dots (left-click + hold) to pick a colour",
        "Hold eraser icon (left-click + hold) to choose Line or Dot erase mode",
        "Hold pen icon (left-click + hold) to change writing mode",
        "Tiny dot next to toolbar = show/hide toggle (left-click)",
        "Undo: Alt+Z  (or Ctrl+Z when pen active)",
        "Redo: Alt+Y  (or Ctrl+Y when pen active)",
    ])

    section(f"Settings  (Tools → {ADDON_NAME} Settings)", [
        "Toggle key / mouse button",
        "Mouse middle button action",
        "Surface Pen side button action",
        "Show/hide toolbar",
        "Lock drawing area",
    ])

    sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
    lay.addWidget(sep2)

    btns = QHBoxLayout()
    open_s = QPushButton("Open Settings")
    open_s.setStyleSheet(
        f"QPushButton{{border:1px solid {t['bdr']};border-radius:5px;"
        f"padding:5px 14px;font-size:11px;color:{t['txt']};background:transparent;}}"
        f"QPushButton:hover{{background:{t['base']};}}")
    open_s.clicked.connect(lambda: (_show_draw_settings(), dlg.accept()))
    got = QPushButton("Got it  ✓")
    got.setDefault(True)
    got.setStyleSheet(
        "QPushButton{background:#2383e2;color:white;border:none;"
        "border-radius:6px;padding:6px 20px;font-weight:bold;font-size:12px;}"
        "QPushButton:hover{background:#1a6fc7;}")
    got.clicked.connect(dlg.accept)
    btns.addWidget(open_s); btns.addStretch(); btns.addWidget(got)
    lay.addLayout(btns)
    dlg.exec()


# ── Show / apply settings ─────────────────────────────────────────────────────

def _show_draw_settings():
    cfg = _cfg()
    dlg = _SettingsDialog(cfg.get("pen_key","½"), cfg.get("zone_locked",False))
    if dlg.exec() == QDialog.DialogCode.Accepted:
        cfg["pen_key"]          = dlg.result_key
        cfg["zone_locked"]      = dlg.result_locked
        cfg["auto_clear"]       = dlg.result_auto_clear
        cfg["barrel_enabled"]   = dlg.result_barrel_en
        cfg["barrel_action"]    = dlg.result_barrel_act
        cfg["visibility_mode"]  = dlg.result_visibility_mode
        _save_cfg(cfg)
        z = _controller._zone
        if z: z._locked = dlg.result_locked
        tb = _controller._toolbar
        if tb:
            tb._visibility_mode   = dlg.result_visibility_mode
            tb._apply_visibility()


def _install_shortcut():
    QApplication.instance().installEventFilter(_key_filter)


# ── Startup ───────────────────────────────────────────────────────────────────

def _on_profile_loaded():
    def _restore():
        _controller.start()
        cfg = _cfg()
        sz  = cfg.get("pen_size",    4)
        col = cfg.get("pen_color",   "#1a1814")
        lk  = cfg.get("zone_locked", False)
        tb  = _controller._toolbar
        if tb:
            for i, (_, v, _) in enumerate(tb.THICKNESS_LEVELS):
                if sz <= v:
                    tb._thick_idx = i; break
            tb._apply_thickness()
            tb._erase_mode    = cfg.get("erase_mode", "dot")
            tb._writing_mode  = cfg.get("writing_mode", "balanced")
            tb.zone._writing_mode = tb._writing_mode
            tb.zone._erase_mode   = tb._erase_mode
            tb._current_color = QColor(col)
            tb.zone.set_color(QColor(col))
            tb.zone._pen_color = QColor(col)
            tb._refresh_icons(); tb._update_styles()
            if hasattr(tb.zone, "_locked"): tb.zone._locked = lk
            tb._toolbar_visible   = cfg.get("toolbar_visible", True)
            tb._visibility_mode   = cfg.get("visibility_mode", "standard")
            tb._apply_visibility()

    QTimer.singleShot(500, _restore)
    QTimer.singleShot(600, _install_shortcut)

    # Single menu entry — Help Guide is inside Settings only
    act = QAction(f"{ADDON_NAME} Settings", mw)
    act.triggered.connect(_show_draw_settings)
    mw.form.menuTools.addAction(act)
    mw.addonManager.setConfigAction(__name__, _show_draw_settings)
    QTimer.singleShot(1200, _show_welcome)


gui_hooks.profile_did_open.append(_on_profile_loaded)
gui_hooks.reviewer_did_show_question.append(_on_card_shown)
