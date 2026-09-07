"""Register this project's launcher and an unused Meta+F8 in KDE (no packages)."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
COMPONENT='local.ability-draft-capture.desktop'
KEY=0x10000000|0x01000037
ACTION=[COMPONENT,'_launch','Ability Draft Capture','Capture draft']

def call(method,*args):
    return subprocess.check_output(['gdbus','call','--session','--dest','org.kde.kglobalaccel','--object-path','/kglobalaccel','--method','org.kde.KGlobalAccel.'+method,*args],text=True).strip()

def desktop(capture):
    executable=str(ROOT/'start.sh').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    return ('[Desktop Entry]\nType=Application\nName=Ability Draft'+(' Capture' if capture else ' Helper')+'\n'
            'Comment=Local Ability Draft screenshot helper\n'
            f'Exec="{executable}"'+(' --capture' if capture else '')+'\n'
            'Icon=applications-games\nTerminal=false\nStartupNotify=false\nCategories=Game;\n'
            +('NoDisplay=true\nX-KDE-GlobalAccel-CommandShortcut=true\nX-KDE-Shortcuts=Meta+F8\n' if capture else ''))

def main():
    existing=call('shortcut',repr(ACTION))
    free=call('isGlobalShortcutAvailable',str(KEY),'')
    if 'true' not in free and str(KEY) not in existing:
        raise SystemExit('Meta+F8 занято. Существующее сочетание не изменено.')
    home=Path.home()
    destinations=[(home/'.local/share/applications/local.ability-draft-helper.desktop',False),
                  (home/'.local/share/applications'/COMPONENT,True),
                  (home/'.local/share/kglobalaccel'/COMPONENT,True)]
    for path,capture in destinations:
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and path.read_text()!=desktop(capture):
            raise SystemExit(f'Существующий файл отличается, не перезаписываю: {path}')
    for path,capture in destinations:
        path.write_text(desktop(capture))
        subprocess.run(['desktop-file-validate',str(path)],check=True)
    call('doRegister',repr(ACTION))
    assigned=call('setShortcut',repr(ACTION),f'[{KEY}]','6')
    if str(KEY) not in assigned:raise SystemExit('KDE не подтвердил назначение: '+assigned)
    print('Meta+F8 registered:',call('shortcut',repr(ACTION)))

if __name__=='__main__':main()
