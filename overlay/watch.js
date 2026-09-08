// Temporary read-only KWin observer. No window settings are modified.
function report() {
    const w = workspace.activeWindow;
    let data = {active:false};
    if (w) {
        const cls = String(w.resourceClass).toLowerCase();
        if (cls === 'dota2' || cls === 'steam_app_570') {
            const g = w.clientGeometry;
            const o = w.output; const og = o.geometry;
            data = {active:true, id:String(w.internalId), x:g.x, y:g.y,
                    width:g.width, height:g.height,
                    output:{name:o.name,x:og.x,y:og.y,width:og.width,height:og.height}};
        }
    }
    callDBus('io.github.dale.AbilityDraftOverlay', '/Overlay',
             'io.github.dale.AbilityDraftOverlay', 'observe', JSON.stringify(data));
}
function watch(w) {
    w.frameGeometryChanged.connect(report);
    w.minimizedChanged.connect(report);
}
workspace.windowList().forEach(watch);
workspace.windowAdded.connect(watch);
workspace.windowActivated.connect(report);
workspace.windowRemoved.connect(report);
workspace.currentDesktopChanged.connect(report);
report();
