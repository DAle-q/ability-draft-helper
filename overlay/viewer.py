"""Optional KDE/XWayland click-through percentages. No image editing UI."""
import os
os.environ['QT_QPA_PLATFORM']='xcb'
import sys,json,subprocess,tempfile,signal,fcntl
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer,QProcess,pyqtSlot,pyqtClassInfo,QRectF
from PyQt6.QtGui import QPainter,QColor,QFont,QPainterPath,QPen,QIcon,QAction
from PyQt6.QtWidgets import QApplication,QWidget,QSystemTrayIcon,QMenu
from PyQt6.QtDBus import QDBusConnection,QDBusAbstractAdaptor,QDBusInterface
ROOT=Path(__file__).resolve().parents[1]
SERVICE='io.github.dale.AbilityDraftOverlay'
from geometry import window_rect

@pyqtClassInfo('D-Bus Interface',SERVICE)
class Adapter(QDBusAbstractAdaptor):
    @pyqtSlot(str)
    def observe(self,value):self.parent().observe(json.loads(value))
    @pyqtSlot(result=str)
    def status(self):
        return json.dumps({'active':self.parent().current, 'busy':self.parent().busy, 'visible':self.parent().isVisible()})
    @pyqtSlot()
    def stop(self):QApplication.quit()

class Overlay(QWidget):
    def __init__(self,python):
        flags=(Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|
               Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowTransparentForInput|
               Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.X11BypassWindowManagerHint)
        super().__init__(None,flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowTitle('Ability Draft Overlay')
        self.python=python;self.current=None;self.snapshot=None;self.data=None
        self.busy=False;self.paused=False;self.capture_lock=None;self.stage='';self.proc=QProcess(self)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.process_error)
        self.temp=tempfile.TemporaryDirectory(prefix='ability-overlay-')
        self.file=str(Path(self.temp.name)/'capture.png')
        self.tray=QSystemTrayIcon(QIcon.fromTheme('applications-games'),self)
        menu=QMenu();pause=QAction('Pause overlay',menu);pause.setCheckable(True)
        pause.toggled.connect(self.pause);menu.addAction(pause)
        stop=QAction('Stop overlay',menu);stop.triggered.connect(QApplication.quit);menu.addAction(stop)
        self.menu=menu;self.tray.setContextMenu(menu);self.tray.show()
        self.status('Waiting for Dota draft (7 seconds)')
        self.timer=QTimer(self);self.timer.timeout.connect(self.capture);self.timer.start(7000)
        self.timeout=QTimer(self);self.timeout.setSingleShot(True);self.timeout.timeout.connect(self.expired)
        self.adaptor=Adapter(self)
        self.lifetime=QTimer(self);self.lifetime.setSingleShot(True)
        self.lifetime.timeout.connect(QApplication.quit);self.lifetime.start(385000)
    def status(self,text):
        self.tray.setToolTip('Ability Draft Overlay: '+text)
        (ROOT/'state/overlay-status.txt').write_text(text)
    def observe(self,data):
        new=data if data.get('active') else None
        if not new:self.status('Waiting for active Dota window')
        changed=new!=self.current
        if changed:
            self.current=new;self.data=None;self.hide()
        if changed and new and not self.busy and not self.paused:QTimer.singleShot(250,self.capture)
    def pause(self,value):
        self.paused=value;self.hide();self.data=None
        self.status('Paused' if value else 'Waiting for next capture')
    def capture(self):
        if self.busy or self.paused or not self.current:return
        self.capture_lock=(ROOT/'state/capture.lock').open('a')
        try:fcntl.flock(self.capture_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.capture_lock.close();self.capture_lock=None;return
        self.busy=True;self.snapshot=dict(self.current)
        # Active-window capture reads Dota, not this separate overlay surface.
        # Keep the last completed frame until a replacement is ready.
        QTimer.singleShot(120,self.take_capture)
    def take_capture(self):
        if self.snapshot!=self.current or self.paused:self.busy=False;self.release_capture();return
        self.stage='capture';self.timeout.start(30000)
        self.proc.setProcessEnvironment(self.native_environment())
        self.proc.start('spectacle',['--background','--activewindow','--no-decoration','--no-shadow','--nonotify','--output',self.file])
    def release_capture(self):
        if self.capture_lock:self.capture_lock.close();self.capture_lock=None
    def native_environment(self):
        from PyQt6.QtCore import QProcessEnvironment
        env=QProcessEnvironment.systemEnvironment();env.remove('QT_QPA_PLATFORM');return env
    def process_error(self,*args):
        if self.proc.state()==QProcess.ProcessState.NotRunning:
            self.timeout.stop();self.release_capture();self.busy=False;self.status('Could not start capture/recognition')
    def expired(self):
        self.proc.kill();self.status('Capture timed out')
    def finished(self,code,*args):
        self.timeout.stop();self.release_capture()
        if code or self.snapshot!=self.current or self.paused:
            self.busy=False
            if self.snapshot!=self.current or self.paused:self.hide()
            if code:self.status(self.proc.readAllStandardError().data().decode(errors='replace')[-240:] or 'Capture failed')
            return
        if self.stage=='capture':
            self.stage='recognize';self.timeout.start(30000)
            self.proc.start(self.python,[str(ROOT/'overlay/worker.py'),self.file]);return
        self.busy=False
        try:
            data=json.loads(bytes(self.proc.readAllStandardOutput()))
            self.status(data['status'])
            if not data['labels']:
                self.data=None;self.hide();return
            g=self.current
            if abs(data['width']/data['height']-g['width']/g['height'])>.02:
                self.status('Capture geometry mismatch');return
            screen=next((s for s in QApplication.screens() if s.name()==g['output']['name']),None)
            if screen is None:
                self.hide();self.status('Game monitor unavailable');return
            self.winId()
            self.windowHandle().setScreen(screen)
            origin=screen.geometry().topLeft()
            self.setGeometry(*window_rect(g,(origin.x(),origin.y())))
            self.data=data
            self.show();self.raise_();self.update()
        except Exception as exc:self.status(str(exc))
    def paintEvent(self,event):
        if not self.data:return
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sx=self.width()/self.data['width'];sy=self.height()/self.data['height']
        font=QFont('DejaVu Sans');font.setBold(True);font.setPixelSize(max(12,round(self.data['font']*sy)))
        for label in self.data['labels']:
            path=QPainterPath();path.addText(0,0,font,label['text']);bounds=path.boundingRect()
            p.save();p.translate(label['x']*sx-bounds.width()/2,label['y']*sy-bounds.top())
            p.strokePath(path,QPen(QColor('#101722'),3));p.fillPath(path,QColor(label['color']));p.restore()
    def cleanup(self):
        self.timer.stop();self.proc.kill();self.proc.waitForFinished(1500)
        self.release_capture();self.hide();self.tray.hide();self.temp.cleanup()

if __name__=='__main__':
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    bus=QDBusConnection.sessionBus()
    if '--stop' in sys.argv:
        QDBusInterface(SERVICE,'/Overlay',SERVICE,bus).call('stop');sys.exit()
    if not bus.registerService(SERVICE):
        if '--toggle' in sys.argv:QDBusInterface(SERVICE,'/Overlay',SERVICE,bus).call('stop')
        sys.exit()
    python=sys.argv[1];(ROOT/'state').mkdir(exist_ok=True)
    view=Overlay(python);bus.registerObject('/Overlay',view,QDBusConnection.RegisterOption.ExportAdaptors)
    name='ability-draft-overlay-observer'
    kwin=QDBusInterface('org.kde.KWin','/Scripting','org.kde.kwin.Scripting',bus)
    kwin.call('unloadScript',name)
    reply=kwin.call('loadScript',str(ROOT/'overlay/watch.js'),name)
    if reply.type()==reply.MessageType.ErrorMessage:
        view.status(reply.errorMessage());sys.exit(1)
    script_id=reply.arguments()[0]
    QDBusInterface('org.kde.KWin',f'/Scripting/Script{script_id}','org.kde.kwin.Script',bus).call('run')
    def cleanup():
        view.cleanup();kwin.call('unloadScript',name)
    app.aboutToQuit.connect(cleanup)
    signal.signal(signal.SIGTERM,lambda *_:app.quit());signal.signal(signal.SIGINT,lambda *_:app.quit())
    tick=QTimer();tick.start(300);tick.timeout.connect(lambda:None)
    app.exec()
