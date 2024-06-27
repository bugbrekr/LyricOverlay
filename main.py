import webview
import threading
import time

HTML_CONTENT = """
<html>
    <body>
        <h1>Hello, World!</h1>
    </body>
    <style>
        body {
            background-color: rgba(0, 255, 255, 0.5);
        }
    </style>
</html>
"""

win = webview.create_window('Embedded Web View', html=HTML_CONTENT, on_top=True, frameless=True, easy_drag=False, focus=False, transparent=True)

def test():
    time.sleep(1)
    win.move(win.x+100, win.y+10)
    print(win.dom.body)

threading.Thread(target=test).start()
webview.start()