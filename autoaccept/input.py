"""Send Enter only to the still-focused Dota XWayland client."""
import ctypes as C
from ctypes.util import find_library

class Hint(C.Structure):
    _fields_=[('name',C.c_void_p),('cls',C.c_void_p)]

class XInput:
    def __init__(self):
        self.x=C.CDLL(find_library('X11'));self.t=C.CDLL(find_library('Xtst'))
        D=C.c_void_p;W=C.c_ulong;I=C.c_int;P=C.POINTER
        def bind(lib,name,args,ret=I):
            f=getattr(lib,name);f.argtypes=args;f.restype=ret;return f
        bind(self.x,'XOpenDisplay',[C.c_char_p],D)
        bind(self.x,'XCloseDisplay',[D]);bind(self.x,'XFree',[D])
        bind(self.x,'XGetInputFocus',[D,P(W),P(I)])
        bind(self.x,'XGetClassHint',[D,W,P(Hint)])
        bind(self.x,'XQueryTree',[D,W,P(W),P(W),P(P(W)),P(C.c_uint)])
        bind(self.x,'XSync',[D,I])
        bind(self.x,'XQueryPointer',[D,W,P(W),P(W),P(I),P(I),P(I),P(I),P(C.c_uint)])
        bind(self.x,'XKeysymToKeycode',[D,W],C.c_ubyte)
        bind(self.x,'XQueryKeymap',[D,C.c_char_p])
        bind(self.t,'XTestFakeKeyEvent',[D,C.c_uint,I,W])
        self.d=self.x.XOpenDisplay(None)
        if not self.d:raise RuntimeError('XWayland display unavailable')
    def close(self):
        if self.d:self.x.XCloseDisplay(self.d);self.d=None
    def focused(self):
        w=C.c_ulong();revert=C.c_int();self.x.XGetInputFocus(self.d,C.byref(w),C.byref(revert))
        for _ in range(10):
            if w.value<=1:return None
            hint=Hint()
            if self.x.XGetClassHint(self.d,w,C.byref(hint)):
                cls=C.string_at(hint.cls).decode(errors='replace').lower() if hint.cls else ''
                for p in (hint.name,hint.cls):
                    if p:self.x.XFree(p)
                if cls in ('dota2','steam_app_570'):return w.value
            root=C.c_ulong();parent=C.c_ulong();children=C.POINTER(C.c_ulong)();n=C.c_uint()
            if not self.x.XQueryTree(self.d,w,C.byref(root),C.byref(parent),C.byref(children),C.byref(n)):return None
            if children:self.x.XFree(children)
            w=parent
        return None
    def press_enter(self,expected_window):
        if not expected_window or self.focused()!=expected_window:return False
        key=self.x.XKeysymToKeycode(self.d,0xff0d)
        if not key:return False
        keys=C.create_string_buffer(32);self.x.XQueryKeymap(self.d,keys)
        if keys.raw[key//8] & (1 << (key%8)):return False
        root=C.c_ulong();child=C.c_ulong();rx=C.c_int();ry=C.c_int();wx=C.c_int();wy=C.c_int();mask=C.c_uint()
        self.x.XQueryPointer(self.d,expected_window,C.byref(root),C.byref(child),C.byref(rx),C.byref(ry),C.byref(wx),C.byref(wy),C.byref(mask))
        # Do not combine Enter with held Ctrl/Alt/Shift/Meta or mouse buttons.
        if mask.value & 0x1fed:return False
        if self.focused()!=expected_window:return False
        self.t.XTestFakeKeyEvent(self.d,key,1,0)
        self.t.XTestFakeKeyEvent(self.d,key,0,0)
        self.x.XSync(self.d,0);return True
