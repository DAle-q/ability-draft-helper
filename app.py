"""Desktop draft board with persistent examples and a capture inbox."""
from pathlib import Path
import fcntl
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from recognizer import Recognizer, annotate, ROOT, BOARD, board_box, atomic_json, icon_crop, recommendations

STATE=ROOT/'state'


class App:
    def __init__(self, root, engine=None):
        self.root=root; root.title('Ability Draft — помощник драфта'); root.geometry('1000x940')
        self.im=None; self.original=None; self.results=[]; self.busy=False; self.messages=queue.Queue()
        self.engine=engine or Recognizer(); self.selecting=False; self.drag_start=None; self.seen=None; self.seen_error=None
        self.display=None; self.render_job=None; self.source_for_capture=False; self.editing=False
        STATE.mkdir(exist_ok=True)
        consumed=STATE/'last-capture.json'
        if consumed.exists():
            try:self.seen=json.loads(consumed.read_text()).get('id')
            except (OSError,ValueError):pass
        bar=ttk.Frame(root,padding=10); bar.pack(fill='x')
        self.openbutton=ttk.Button(bar,text='Открыть скриншот…',command=self.open); self.openbutton.pack(side='left')
        self.regionbutton=ttk.Button(bar,text='Выделить сетку',command=self.begin_selection,state='disabled'); self.regionbutton.pack(side='left',padx=8)
        self.savebutton=ttk.Button(bar,text='Сохранить PNG…',command=self.save,state='disabled'); self.savebutton.pack(side='left')
        ttk.Button(bar,text='Сбросить область захвата',command=self.reset_capture).pack(side='left',padx=8)
        ttk.Label(bar,text='7.41d · Meta+F8').pack(side='right')
        self.status=tk.StringVar(value='Открой скриншот или нажми Meta+F8 в Dota. Исправления иконок запоминаются.')
        ttk.Label(root,textvariable=self.status,padding=8,wraplength=950).pack(fill='x')
        self.summary=tk.StringVar(value='Золотая рамка — лучшая ульта. Голубые — три лучших обычных скилла.')
        ttk.Label(root,textvariable=self.summary,padding=8,wraplength=950).pack(fill='x')
        self.canvas=tk.Canvas(root,bg='#121923',highlightthickness=0); self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',self.schedule_render); self.canvas.bind('<ButtonPress-1>',self.mouse_down)
        self.canvas.bind('<B1-Motion>',self.mouse_move); self.canvas.bind('<ButtonRelease-1>',self.mouse_up)
        root.bind('<Escape>',lambda e:self.cancel_selection())
        ttk.Label(root,text='Рейтинг среди распознанных и доступных скиллов. «?» — проверьте вручную. Полные скриншоты в Git не сохраняются.',padding=8).pack(fill='x')
        root.after(100,self.poll)

    def reset_capture(self):
        path=STATE/'settings.json'
        settings=json.loads(path.read_text()) if path.exists() else {}
        settings.pop('captureRect',None);settings.pop('sourceAspect',None)
        atomic_json(path,settings)
        self.status.set('Область сброшена. Вернись в Dota и нажми Meta+F8, затем выдели всю сетку заново.')

    def open(self):
        path=filedialog.askopenfilename(filetypes=[('Изображения','*.png *.jpg *.jpeg *.webp')])
        if path:self.load(path)

    def load(self,path,mode='auto',from_capture=False):
        if self.busy or self.selecting or self.editing:return
        try:
            with Image.open(path) as im: self.original=im.convert('RGB')
        except Exception as exc:
            self.failed('Не удалось открыть: '+str(exc)); return
        self.source_for_capture=from_capture and mode=='calibrate'
        self.results=[]; self.regionbutton.config(state='normal')
        if mode=='auto':
            ratio=self.original.width/self.original.height
            mode='full' if abs(ratio-2048/1018)<.08 else ('board' if abs(ratio-800/699)<.035 else 'calibrate')
        if mode=='calibrate':
            self.im=self.original.copy(); self.begin_selection(); return
        self.im=self.original.crop(board_box(self.original.size)) if mode=='full' else self.original.copy()
        self.run_recognition()

    def run_recognition(self):
        self.busy=True; self.openbutton.config(state='disabled'); self.regionbutton.config(state='disabled'); self.savebutton.config(state='disabled')
        self.status.set('Распознаю иконки…'); self.display=self.im; self.render()
        image=self.im.copy()
        def work():
            try:self.messages.put(('done',self.engine.recognize(image,'board')))
            except Exception as exc:self.messages.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                self.done(value) if kind=='done' else self.failed(value)
        except queue.Empty:pass
        if not self.busy and not self.selecting and not self.editing:
            path=STATE/'incoming.json'
            try:
                if path.exists():
                    incoming=json.loads(path.read_text())
                    if incoming['id']!=self.seen:
                        filename=incoming['file']
                        if Path(filename).name!=filename or not filename.startswith('capture-'):
                            raise ValueError('Некорректное имя снимка')
                        self.seen=incoming['id']; self.load(STATE/filename,incoming['mode'],True)
                        atomic_json(STATE/'last-capture.json',{'id':self.seen})
                        # Pixels now live in memory. Delete this transient screenshot only.
                        (STATE/filename).unlink(missing_ok=True)
                error_file=STATE/'capture-error.json'
                if error_file.exists():
                    error=json.loads(error_file.read_text())
                    if error['id']!=self.seen_error:
                        self.seen_error=error['id']; self.status.set('Ошибка захвата: '+error['error'])
            except (OSError,ValueError,KeyError) as exc:self.status.set('Ошибка входящего снимка: '+str(exc))
        self.root.after(150,self.poll)

    def failed(self,error):
        self.busy=False; self.openbutton.config(state='normal'); self.regionbutton.config(state='normal' if self.original else 'disabled'); self.status.set(error)

    def done(self,results):
        self.results=results; self.busy=False; self.openbutton.config(state='normal'); self.regionbutton.config(state='normal'); self.savebutton.config(state='normal')
        self.display=annotate(self.im,results); self.render()
        n=sum(r['accepted'] for r in results)
        self.status.set(f'Подписано {n}/60 · Сохранено образцов: {len(self.engine.examples)}. Нажми на иконку, чтобы выбрать и запомнить название.')
        selected=recommendations(results)
        ult=[r for r in results if r['slot'] in selected and r['kind']=='ultimate']
        normal=sorted([r for r in results if r['slot'] in selected and r['kind']=='standard'],key=lambda r:selected[r['slot']])
        text=lambda r:f"{r['name']} {r['winrate']*100:.1f}%"
        self.summary.set('Ульта: '+(', '.join(map(text,ult)) or 'нет подтверждённых')+'\nСкиллы: '+(' · '.join(map(text,normal)) or 'нет подтверждённых'))

    def schedule_render(self,event=None):
        if self.render_job:self.root.after_cancel(self.render_job)
        self.render_job=self.root.after(60,self.render)

    def render(self):
        self.render_job=None
        if self.display is None:return
        out=self.display; w=max(1,self.canvas.winfo_width()); h=max(1,self.canvas.winfo_height()); self.scale=min(w/out.width,h/out.height)
        size=(max(1,int(out.width*self.scale)),max(1,int(out.height*self.scale)))
        self.photo=ImageTk.PhotoImage(out.resize(size,Image.Resampling.LANCZOS)); self.offset=((w-size[0])/2,(h-size[1])/2)
        self.canvas.delete('all'); self.canvas.create_image(*self.offset,anchor='nw',image=self.photo)

    def save(self):
        if not self.results or self.selecting:return
        path=filedialog.asksaveasfilename(defaultextension='.png',initialfile='ability-draft.png',filetypes=[('PNG','*.png')])
        if path:
            try:annotate(self.im,self.results).save(path); self.status.set('Сохранено: '+path)
            except Exception as exc:messagebox.showerror('Ошибка сохранения',str(exc))

    def begin_selection(self):
        if self.original is None or self.busy:return
        self.selecting=True; self.display=self.original; self.render(); self.savebutton.config(state='disabled'); self.openbutton.config(state='disabled')
        self.status.set('Обведи всю доску с иконками: по ширине — от левого до правого края нижних портретов; по высоте — от верха рамок ульт до низа рамок скиллов. Esc — отмена.')
        self.summary.set('Ориентир: прямоугольник от левого края нижних портретов до правого края нижних портретов; сверху начало рамок ульт, снизу конец рамок скиллов.')

    def cancel_selection(self):
        if not self.selecting:return
        self.selecting=False; self.openbutton.config(state='normal')
        if self.results:self.done(self.results)
        else:
            self.display=self.im;self.render();self.status.set('Выделение отменено. Открой другой снимок или нажми «Выделить сетку».')

    def image_point(self,event):
        return ((event.x-self.offset[0])/self.scale,(event.y-self.offset[1])/self.scale)

    def mouse_down(self,event):
        if self.busy:return
        if self.selecting:self.drag_start=self.image_point(event)
        else:self.edit(event)

    def mouse_move(self,event):
        if not self.selecting or self.drag_start is None:return
        x,y=self.drag_start; x2,y2=self.image_point(event)
        self.canvas.delete('selection');self.canvas.create_rectangle(x*self.scale+self.offset[0],y*self.scale+self.offset[1],x2*self.scale+self.offset[0],y2*self.scale+self.offset[1],outline='#ffe173',width=3,tags='selection')

    def mouse_up(self,event):
        if not self.selecting or self.drag_start is None:return
        x,y=self.drag_start; x2,y2=self.image_point(event); self.drag_start=None
        box=(max(0,round(min(x,x2))),max(0,round(min(y,y2))),min(self.original.width,round(max(x,x2))),min(self.original.height,round(max(y,y2))))
        if box[2]-box[0]<200 or box[3]-box[1]<200:
            self.status.set('Область слишком маленькая. Выдели всю сетку, включая портреты героев.'); return
        self.apply_selection(box)

    def apply_selection(self,box):
        self.im=self.original.crop(box);self.selecting=False
        if self.source_for_capture:
            path=STATE/'settings.json'; settings=json.loads(path.read_text()) if path.exists() else {}
            settings.update(captureRect=[v/(self.original.width if i%2==0 else self.original.height) for i,v in enumerate(box)],sourceAspect=self.original.width/self.original.height)
            atomic_json(path,settings)
        self.results=[];self.run_recognition()

    def edit(self,event):
        if not self.results or self.busy:return
        x,y=self.image_point(event);r=min(self.results,key=lambda r:(r['x']-x)**2+(r['y']-y)**2)
        if abs(r['x']-x)>40*r['sx'] or abs(r['y']-y)>45*r['sy']:return
        self.editing=True; self.openbutton.config(state='disabled'); self.regionbutton.config(state='disabled')
        popup=tk.Toplevel(self.root)
        def closed(event):
            if event.widget is popup:
                self.editing=False;self.openbutton.config(state='normal');self.regionbutton.config(state='normal')
        popup.bind('<Destroy>',closed)
        popup.title('Выбрать и запомнить иконку');popup.geometry('520x540');popup.transient(self.root)
        preview=ImageTk.PhotoImage(icon_crop(self.im,r).resize((96,96)));label=ttk.Label(popup,image=preview);label.image=preview;label.pack(pady=6)
        ttk.Label(popup,text='Предположение: '+r['name'],padding=6).pack()
        var=tk.StringVar();entry=ttk.Entry(popup,textvariable=var);entry.pack(fill='x',padx=12);entry.focus()
        listing=tk.Listbox(popup);listing.pack(fill='both',expand=True,padx=12,pady=8)
        rows=self.engine.choices(r['kind']);shown=[]
        def refresh(*args):
            shown[:]=sorted([row for row in rows if var.get().lower() in row['name'].lower()],key=lambda row:row['name']);listing.delete(0,'end')
            for row in shown:listing.insert('end',f"{row['name']} — {row['winrate']*100:.1f}%")
        def choose():
            if not listing.curselection():return
            row=shown[listing.curselection()[0]]
            try:self.engine.learn(self.im,r,row['abilityId'])
            except Exception as exc:messagebox.showerror('Не удалось запомнить',str(exc),parent=popup);return
            r.update(name=row['name'],abilityId=row['abilityId'],winrate=row['winrate'],accepted=True,manual=True,source='learned');popup.destroy();self.done(self.results)
        def forget():
            try:self.engine.forget(self.im,r)
            except Exception as exc:messagebox.showerror('Ошибка',str(exc),parent=popup);return
            r.update(accepted=False);popup.destroy();self.done(self.results)
        var.trace_add('write',refresh);refresh();listing.bind('<Double-1>',lambda e:choose())
        ttk.Button(popup,text='Выбрать и запомнить',command=choose).pack(side='left',padx=12,pady=8)
        ttk.Button(popup,text='Забыть этот образец',command=forget).pack(side='right',padx=12,pady=8)


if __name__=='__main__':
    import sys
    STATE.mkdir(exist_ok=True)
    lock=(STATE/'app.lock').open('w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:sys.exit(0)
    root=tk.Tk();app=App(root)
    if len(sys.argv)>1 and sys.argv[1]!='--inbox':root.after(100,lambda:app.load(sys.argv[1]))
    root.mainloop()
