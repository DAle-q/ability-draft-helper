"""Run with an explicit private test screenshot; the screenshot is not committed."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as ui
import capture
from recognizer import Recognizer,board_box
from PIL import Image

with tempfile.TemporaryDirectory() as temp:
    ui.STATE=Path(temp)/'state';capture.STATE=ui.STATE
    engine=Recognizer(Path(temp)/'learned');root=tk.Tk();root.withdraw();application=ui.App(root,engine)
    passed=[];errors=[]
    def after_ready(callback):
        if application.busy:root.after(50,lambda:after_ready(callback))
        else:
            try:callback()
            except Exception as exc:errors.append(exc);root.destroy()
    def learned_and_capture():
        assert len(application.results)==60
        assert application.photo.width()>0 and str(application.savebutton['state'])=='normal'
        r=application.results[0]
        x=r['x']*application.scale+application.offset[0];y=r['y']*application.scale+application.offset[1]
        application.edit(SimpleNamespace(x=x,y=y))
        popup=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel));popup.withdraw()
        listing=next(w for w in popup.winfo_children() if isinstance(w,tk.Listbox))
        index=next(i for i,s in enumerate(listing.get(0,'end')) if s.startswith('Chemical Rage —'))
        listing.selection_set(index)
        next(w for w in popup.winfo_children() if isinstance(w,ttk.Button) and w['text']=='Выбрать и запомнить').invoke()
        assert not application.editing and len(engine.examples)==1
        fresh=Recognizer(Path(temp)/'learned').recognize(application.im,'board')
        assert fresh[0]['name']=='Chemical Rage' and fresh[0]['accepted'] and fresh[0]['source']=='learned'
        with Image.open(sys.argv[1]) as im:capture.deliver(im)
        application.poll()
        assert application.selecting
        application.apply_selection(board_box(application.original.size))
        root.after(50,lambda:after_ready(finished))
    def finished():
        assert (ui.STATE/'settings.json').exists()
        assert len(application.results)==60
        with Image.open(sys.argv[1]) as im:capture.deliver(im)
        application.poll()
        assert not application.selecting
        root.after(50,lambda:after_ready(final_check))
    def final_check():
        assert application.results[0]['name']=='Chemical Rage'
        assert application.results[0]['source']=='learned'
        passed.append(True);root.destroy()
    root.after(10,lambda:application.load(sys.argv[1]));root.after(100,lambda:after_ready(learned_and_capture));root.after(25000,root.destroy)
    root.mainloop()
    if errors:raise errors[0]
    assert passed==[True],passed
    print('GUI PASS: board preview, manual learning, restart, capture inbox, calibration and repeated cropped capture')
