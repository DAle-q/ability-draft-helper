"""Local desktop screenshot annotator. No uploads or network calls."""
import json
import threading
import queue
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk
from recognizer import Recognizer,annotate,ROOT

class App:
    def __init__(self,root):
        self.root=root;root.title('Ability Draft — проценты на скриншоте');root.geometry('1280x820')
        self.im=None;self.results=[];self.busy=False;self.messages=queue.Queue()
        root.after(100,self.poll)
        bar=ttk.Frame(root,padding=12);bar.pack(fill='x')
        self.openbutton=ttk.Button(bar,text='Открыть скриншот…',command=self.open);self.openbutton.pack(side='left')
        self.savebutton=ttk.Button(bar,text='Сохранить PNG…',command=self.save,state='disabled');self.savebutton.pack(side='left',padx=10)
        ttk.Label(bar,text='Windrun · 7.41d · общий винрейт').pack(side='right')
        self.status=tk.StringVar(value='Открой полный скриншот драфта. Нажми на иконку, чтобы проверить или исправить название.')
        ttk.Label(root,textvariable=self.status,padding=8).pack(fill='x')
        self.canvas=tk.Canvas(root,bg='#121923',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.render());self.canvas.bind('<Button-1>',self.edit)
        ttk.Label(root,text='Обработка на компьютере. «?» — совпадение не подтверждено. Поддерживается расположение сетки как на тестовом скриншоте.',padding=8).pack(fill='x')
        self.engine=Recognizer()
    def open(self):
        path=filedialog.askopenfilename(filetypes=[('Изображения','*.png *.jpg *.jpeg *.webp')])
        if path:self.load(path)
    def load(self,path):
        if self.busy:return
        try:
            im=Image.open(path);im.load();self.im=im.convert('RGB')
        except Exception as exc:messagebox.showerror('Не удалось открыть',str(exc));return
        self.results=[];self.render();self.busy=True;self.openbutton.config(state='disabled');self.savebutton.config(state='disabled');self.status.set('Распознаю иконки…')
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
        self.root.after(100,self.poll)
    def failed(self,error):
        self.busy=False;self.openbutton.config(state='normal');self.status.set(error)
    def done(self,results):
        self.results=results;self.busy=False;self.openbutton.config(state='normal');self.savebutton.config(state='normal');self.render()
        n=sum(r['accepted'] for r in results);self.status.set(f'Подписано {n} из {len(results)} позиций. Нажми на иконку для проверки или исправления.')
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
            try:annotate(self.im,self.results).save(path);self.status.set('Сохранено: '+path)
            except Exception as exc:messagebox.showerror('Ошибка сохранения',str(exc))
    def edit(self,event):
        if not self.results or self.busy:return
        x=(event.x-self.offset[0])/self.scale;y=(event.y-self.offset[1])/self.scale
        r=min(self.results,key=lambda r:(r['x']-x)**2+(r['y']-y)**2)
        if abs(r['x']-x)>45*self.im.width/2048 or abs(r['y']-y)>48*self.im.width/2048:return
        popup=tk.Toplevel(self.root);popup.title('Проверить способность');popup.geometry('460x440');popup.transient(self.root)
        ttk.Label(popup,text='Предположение: '+r['name'],padding=8).pack()
        var=tk.StringVar();entry=ttk.Entry(popup,textvariable=var);entry.pack(fill='x',padx=12);entry.focus()
        listing=tk.Listbox(popup);listing.pack(fill='both',expand=True,padx=12,pady=8)
        rows=self.engine.groups[r['hero']][0];shown=[]
        def refresh(*args):
            shown[:]=sorted([row for row in rows if var.get().lower() in row['name'].lower()],key=lambda row:row['name']);listing.delete(0,'end')
            for row in shown:listing.insert('end',f"{row['name']} — {row['winrate']*100:.1f}%")
        def choose():
            if not listing.curselection():return
            row=shown[listing.curselection()[0]];r.update(name=row['name'],abilityId=row['abilityId'],winrate=row['winrate'],accepted=True,manual=True);popup.destroy();self.done(self.results)
        def clear():r.update(accepted=False,manual=True);popup.destroy();self.done(self.results)
        var.trace_add('write',refresh);refresh();listing.bind('<Double-1>',lambda e:choose())
        ttk.Button(popup,text='Выбрать',command=choose).pack(side='left',padx=12,pady=8);ttk.Button(popup,text='Оставить «?»',command=clear).pack(side='right',padx=12,pady=8)

if __name__=='__main__':
    import sys
    root=tk.Tk();app=App(root)
    if len(sys.argv)>1:root.after(100,lambda:app.load(sys.argv[1]))
    root.mainloop()
