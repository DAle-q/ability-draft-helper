"""Map KWin logical coordinates to Qt's XWayland screen coordinate islands."""
def window_rect(window, qt_origin):
    output = window['output']
    return (round(qt_origin[0] + window['x'] - output['x']),
            round(qt_origin[1] + window['y'] - output['y']),
            round(window['width']), round(window['height']))
