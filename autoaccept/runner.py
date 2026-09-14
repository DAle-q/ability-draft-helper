"""Opt-in Meta+F10 session: accept retries, then hand over to the overlay."""
import os,sys,json,time,tempfile,fcntl,signal,subprocess
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='xcb'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from autoaccept.input import XInput
from PyQt6.QtCore import QObject,QTimer,QProcess,QProcessEnvironment,pyqtSlot,pyqtClassInfo
from PyQt6.QtGui import QIcon,QAction
from PyQt6.QtWidgets import QApplication,QSystemTrayIcon,QMenu
from PyQt6.QtDBus import QDBusConnection,QDBusInterface,QDBusAbstractAdaptor
SERVICE='io.github.dale.AbilityDraftAutoAccept'

@pyqtClassInfo('D-Bus Interface',SERVICE)
class Adapter(QDBusAbstractAdaptor):
    @pyqtSlot(str)
    def observe(self,value):self.parent().observe(json.loads(value))
    @pyqtSlot()
    def stop(self):QApplication.quit()
    @pyqtSlot(result=str)
    def status(self):
        p=self.parent();return json.dumps({'status':p.message,'busy':p.busy,'active':p.current,'clicks':p.clicks})

class Session(QObject):
    def __init__(self,python):
        super().__init__();self.python=python;self.current=None;self.snapshot=None
        self.busy=False;self.lock=None;self.stage='';self.draft_frames=0;self.clicks=0
        self.input=XInput();self.temp=tempfile.TemporaryDirectory(prefix='ability-accept-')
        self.file=str(Path(self.temp.name)/'capture.png')
        self.proc=QProcess(self);self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.error)
        self.tray=QSystemTrayIcon(QIcon.fromTheme('applications-games'),self)
        self.menu=QMenu();a=QAction('Stop auto accept',self.menu);a.triggered.connect(QApplication.quit)
        self.menu.addAction(a);self.tray.setContextMenu(self.menu);self.tray.show()
        self.adaptor=Adapter(self)
        self.timer=QTimer(self);self.timer.timeout.connect(self.capture);self.timer.start(5000)
        self.timeout=QTimer(self);self.timeout.setSingleShot(True);self.timeout.timeout.connect(self.proc.kill)
        self.status('Enabled — keep Dota active; checks every 5 seconds')
        self.tray.showMessage('Ability Draft Auto Accept',self.message)
    def status(self,message):
        self.message=message;self.tray.setToolTip('Auto Accept: '+message)
        (ROOT/'state/autoaccept-status.txt').write_text(message)
    def observe(self,data):
        new=data if data.get('active') else None
        if new!=self.current:
            self.current=new;self.draft_frames=0
            if new:QTimer.singleShot(250,self.capture)
            else:self.status('Waiting for active Dota window')
    def release(self):
        if self.lock:self.lock.close();self.lock=None
    def capture(self):
        if self.busy or not self.current:return
        target=self.input.focused()
        if not target:return
        self.lock=(ROOT/'state/capture.lock').open('a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.release();return
        self.busy=True;self.snapshot=dict(self.current);self.target=target;self.started=time.monotonic()
        self.stage='capture';self.timeout.start(20000)
        env=QProcessEnvironment.systemEnvironment();env.remove('QT_QPA_PLATFORM');self.proc.setProcessEnvironment(env)
        self.proc.start('spectacle',['--background','--activewindow','--no-decoration','--no-shadow','--nonotify','--output',self.file])
    def error(self,*_):
        if self.proc.state()==QProcess.ProcessState.NotRunning:
            self.busy=False;self.timeout.stop();self.release();self.draft_frames=0
            self.status('Capture/recognition unavailable; no Enter sent')
    def finished(self,code,*_):
        self.timeout.stop()
        if code or self.current!=self.snapshot or self.input.focused()!=self.target:
            self.busy=False;self.release();self.draft_frames=0
            if code:self.status('Scan failed; retrying next tick')
            return
        if self.stage=='capture':
            self.release();self.stage='scan';self.timeout.start(15000)
            self.proc.start(self.python,[str(ROOT/'autoaccept/worker.py'),self.file]);return
        self.busy=False
        try:
            result=json.loads(bytes(self.proc.readAllStandardOutput()))
            kind=result['kind']
            if kind=='draft':
                self.draft_frames+=1
                if self.draft_frames>=2:self.start_overlay()
                else:self.status('Draft detected; confirming next frame')
                return
            self.draft_frames=0
            if kind=='accept' and time.monotonic()-self.started<6:
                if self.input.press_enter(self.target):
                    self.clicks+=1;self.status('Accepted — waiting for players or another match')
                else:self.status('Window changed; no Enter sent')
            else:self.status('Waiting for ACCEPT or Ability Draft')
        except Exception as exc:self.status('Scan error: '+str(exc));self.draft_frames=0
    def start_overlay(self):
        self.timer.stop()
        interface=QDBusInterface('io.github.dale.AbilityDraftOverlay','/Overlay','io.github.dale.AbilityDraftOverlay',QDBusConnection.sessionBus())
        if interface.isValid():
            reply=interface.call('beginDraft')
            if reply.type()==reply.MessageType.ErrorMessage:
                self.status('Overlay already running; auto accept stopped');QApplication.quit();return
        else:
            with (ROOT/'state/overlay.log').open('a') as log:
                subprocess.Popen(['/usr/bin/python3',str(ROOT/'overlay/viewer.py'),self.python],stdout=log,stderr=log,start_new_session=True)
        self.status('Draft started — overlay enabled; auto accept stopped')
        QApplication.quit()
    def cleanup(self):
        self.timer.stop();self.timeout.stop();self.proc.kill();self.proc.waitForFinished(1000)
        self.release();self.input.close();self.tray.hide();self.temp.cleanup()

if __name__=='__main__':
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    bus=QDBusConnection.sessionBus()
    if not bus.registerService(SERVICE):
        QDBusInterface(SERVICE,'/Overlay',SERVICE,bus).call('stop');sys.exit()
    (ROOT/'state').mkdir(exist_ok=True)
    session=Session(sys.argv[1]);bus.registerObject('/Overlay',session,QDBusConnection.RegisterOption.ExportAdaptors)
    name='ability-draft-autoaccept-observer';kwin=QDBusInterface('org.kde.KWin','/Scripting','org.kde.kwin.Scripting',bus)
    kwin.call('unloadScript',name)
    reply=kwin.call('loadScript',str(ROOT/'autoaccept/watch.js'),name)
    if reply.type()==reply.MessageType.ErrorMessage:raise RuntimeError(reply.errorMessage())
    run=QDBusInterface('org.kde.KWin',f'/Scripting/Script{reply.arguments()[0]}','org.kde.kwin.Script',bus).call('run')
    if run.type()==run.MessageType.ErrorMessage:raise RuntimeError(run.errorMessage())
    def cleanup():session.cleanup();kwin.call('unloadScript',name)
    app.aboutToQuit.connect(cleanup)
    signal.signal(signal.SIGTERM,lambda *_:app.quit());signal.signal(signal.SIGINT,lambda *_:app.quit())
    tick=QTimer();tick.start(300);tick.timeout.connect(lambda:None)
    app.exec()
