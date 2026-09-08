"""Local desktop screenshot annotator. No uploads or network calls."""
import json
import subprocess
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk
from instance import Instance
from recognizer import Recognizer,annotate,ROOT,prepare_image

class App:
    def __init__(self,root,inbox=None):
        self.inbox=inbox;self.seen_request=None;self.editing=False
        self.root=root;root.title('Ability Draft — draft helper');root.geometry('1280x820')
        # Maximize after the window is mapped so KDE applies its work area.
        root.after(0, self.maximize)
        self.im=None;self.results=[];self.busy=False;self.messages=queue.Queue()
        root.after(100,self.poll)
        bar=ttk.Frame(root,padding=12);bar.pack(fill='x')
        self.openbutton=ttk.Button(bar,text='Open screenshot',command=self.open);self.openbutton.pack(side='left')
        self.savebutton=ttk.Button(bar,text='Save PNG',command=self.save,state='disabled');self.savebutton.pack(side='left',padx=10)
        ttk.Button(bar,text='Start overlay',command=self.start_overlay).pack(side='left',padx=6)
        ttk.Button(bar,text='Stop overlay',command=self.stop_overlay).pack(side='left')
        ttk.Label(bar,text='Windrun · 7.41d · overall win rate').pack(side='right')
        self.status=tk.StringVar(value='Open a draft screenshot. Click an icon to correct its name.')
        ttk.Label(root,textvariable=self.status,padding=8).pack(fill='x')
        self.canvas=tk.Canvas(root,bg='#121923',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.render());self.canvas.bind('<Button-1>',self.edit)
        ttk.Label(root,text='Offline processing. ? means an uncertain match.',padding=8).pack(fill='x')
        self.engine=Recognizer()
    def start_overlay(self):
        try:
            probe=subprocess.run(['/usr/bin/python3','-c','from PyQt6 import QtWidgets, QtDBus'],capture_output=True,timeout=5)
            if probe.returncode:raise RuntimeError('Overlay requires PyQt6 with QtDBus in /usr/bin/python3.')
            with (ROOT/'state/overlay.log').open('a') as log:
                subprocess.Popen(['/usr/bin/python3',str(ROOT/'overlay/viewer.py'),sys.executable],stdout=log,stderr=log,start_new_session=True)
            self.status.set('Overlay started. Return to Dota. Updates every 7 seconds; pause/stop from the tray. Screenshot editing stays here.')
        except Exception as exc:messagebox.showerror('Overlay unavailable',str(exc))

    def stop_overlay(self):
        try:
            subprocess.run(['qdbus6','io.github.dale.AbilityDraftOverlay','/Overlay','io.github.dale.AbilityDraftOverlay.stop'],capture_output=True,timeout=3)
            self.status.set('Overlay stopped. Screenshot mode remains available.')
        except Exception as exc:messagebox.showerror('Could not stop overlay',str(exc))

    def maximize(self):
        try:
            self.root.state('zoomed')
        except tk.TclError:
            self.root.attributes('-zoomed', True)

    def open(self):
        path=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg *.webp')])
        if path:self.load(path)
    def load(self,path):
        if self.busy:return
        try:
            im=Image.open(path);im.load();self.im=prepare_image(im.convert('RGB'))
        except Exception as exc:messagebox.showerror('Could not open',str(exc));return
        self.results=[];self.render();self.busy=True;self.openbutton.config(state='disabled');self.savebutton.config(state='disabled');self.status.set('Recognizing icons...')
        def work():
            try:
                results=self.engine.recognize(self.im)
                self.messages.put(('done',results))
            except Exception as exc:
                self.messages.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        try:
            kind,value=self.messages.get_nowait()
            self.done(value) if kind=='done' else self.failed(value)
        except queue.Empty:pass
        if self.inbox and not self.busy and not self.editing:
            try:
                request=self.inbox.read()
                if request and request['id']!=self.seen_request:
                    self.seen_request=request['id']
                    self.load(request['path'])
            except (OSError,ValueError,KeyError) as exc:
                self.status.set('Screenshot delivery failed: '+str(exc))
        self.root.after(100,self.poll)
    def failed(self,error):
        self.busy=False;self.openbutton.config(state='normal');self.status.set(error)
    def done(self,results):
        self.results=results;self.busy=False;self.openbutton.config(state='normal');self.savebutton.config(state='normal');self.render()
        n=sum(r['accepted'] for r in results);self.status.set(f'Recognized {n} of {len(results)}. AVG = mean skill win rate, not build win chance. Click an icon to correct it.')
    def render(self):
        if self.im is None:return
        out=annotate(self.im,self.results);w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height());self.scale=min(w/out.width,h/out.height)
        size=(max(1,int(out.width*self.scale)),max(1,int(out.height*self.scale)))
        self.photo=ImageTk.PhotoImage(out.resize(size,Image.Resampling.LANCZOS));self.offset=((w-size[0])/2,(h-size[1])/2)
        self.canvas.delete('all');self.canvas.create_image(*self.offset,anchor='nw',image=self.photo)
    def save(self):
        if not self.results:return
        path=filedialog.asksaveasfilename(defaultextension='.png',initialfile='ability-draft.png',filetypes=[('PNG','*.png')])
        if path:
            try:annotate(self.im,self.results).save(path);self.status.set('Saved: '+path)
            except Exception as exc:messagebox.showerror('Save error',str(exc))
    def edit(self,event):
        if not self.results or self.busy:return
        x=(event.x-self.offset[0])/self.scale;y=(event.y-self.offset[1])/self.scale
        r=min(self.results,key=lambda r:(r['x']-x)**2+(r['y']-y)**2)
        if abs(r['x']-x)>45*self.im.width/2048 or abs(r['y']-y)>48*self.im.width/2048:return
        self.editing=True
        popup=tk.Toplevel(self.root);
        def closed(event):
            if event.widget is popup:self.editing=False
        popup.bind('<Destroy>',closed)
        popup.title('Check ability');popup.geometry('460x440');popup.transient(self.root)
        ttk.Label(popup,text='Guess: '+r['name'],padding=8).pack()
        var=tk.StringVar();entry=ttk.Entry(popup,textvariable=var);entry.pack(fill='x',padx=12);entry.focus()
        listing=tk.Listbox(popup);listing.pack(fill='both',expand=True,padx=12,pady=8)
        rows=self.engine.groups[r['hero']][0];shown=[]
        def refresh(*args):
            shown[:]=sorted([row for row in rows if var.get().lower() in row['name'].lower()],key=lambda row:row['name']);listing.delete(0,'end')
            for row in shown:listing.insert('end',f"{row['name']} — {row['winrate']*100:.1f}%")
        def choose():
            if not listing.curselection():return
            row=shown[listing.curselection()[0]]
            try:self.engine.learn(self.im,r,row['abilityId'])
            except Exception as exc:
                messagebox.showerror('Could not save correction',str(exc),parent=popup);return
            r.update(name=row['name'],abilityId=row['abilityId'],winrate=row['winrate'],accepted=True,manual=True);popup.destroy();self.done(self.results)
        def clear():r.update(accepted=False,manual=True);popup.destroy();self.done(self.results)
        var.trace_add('write',refresh);refresh();listing.bind('<Double-1>',lambda e:choose())
        ttk.Button(popup,text='Choose and save',command=choose).pack(side='left',padx=12,pady=8);ttk.Button(popup,text='Keep ?',command=clear).pack(side='right',padx=12,pady=8)

if __name__=='__main__':
    import sys
    instance=Instance(ROOT/'state')
    if len(sys.argv)>1:instance.send(sys.argv[1])
    if not instance.acquire():sys.exit(0)
    root=tk.Tk();app=App(root,instance)
    root.mainloop()
