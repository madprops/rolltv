import sys
import webview
import socket
import tempfile
import hashlib
import os
import threading
import logging


class Api:
    def __init__(self, app_name):
        self.app_name = app_name

    def select_country(self, name):
        try:
            if os.name == "posix":
                socket_path = os.path.join(
                    tempfile.gettempdir(), f"{self.app_name}_ipc.sock"
                )

                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.connect(socket_path)
            else:
                port = (
                    50000
                    + int(hashlib.md5(self.app_name.encode()).hexdigest(), 16) % 10000
                )

                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.connect(("127.0.0.1", port))

            client.sendall(f"COUNTRY:{name}".encode("utf-8"))
            client.close()
        except Exception:
            pass


def stdin_listener(window):
    for line in sys.stdin:
        try:
            parts = line.strip().split(",")

            if len(parts) == 4:
                x, y, w, h = map(int, parts)
                window.resize(w, h)
                window.move(x, y)
        except Exception:
            pass


html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style> body { margin: 0; padding: 0; background-color: #1A1B26; overflow: hidden; } </style>
    <script>
        const originalWarn = console.warn;
        console.warn = function(...args) {
            if (args[0] && typeof args[0] === 'string' && args[0].includes('THREE.Clock')) return;
            originalWarn.apply(console, args);
        };
    </script>
    <script src="https://unpkg.com/globe.gl"></script>
</head>
<body>
    <div id="globeViz"></div>
    <script>
        fetch('https://raw.githubusercontent.com/vasturiano/globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson')
            .then(res => res.json())
            .then(countries => {
                let clickedD = null;

                const world = Globe()
                    (document.getElementById('globeViz'))
                    .backgroundColor('#1A1B26')
                    .showAtmosphere(true)
                    .atmosphereColor('#7AA2F7')
                    .globeImageUrl('https://unpkg.com/three-globe/example/img/earth-dark.jpg')
                    .polygonsData(countries.features)
                    .polygonAltitude(0.01)
                    .polygonCapColor(d => d === clickedD ? 'lightgreen' : '#33467C')
                    .polygonSideColor(() => '#1F2335')
                    .polygonStrokeColor(() => '#7AA2F7')
                    .onPolygonHover(hoverD => {
                        world.polygonAltitude(d => d === hoverD ? 0.12 : 0.01)
                             .polygonCapColor(d => d === hoverD ? '#7AA2F7' : (d === clickedD ? 'lightgreen' : '#33467C'));
                    })
                    .onPolygonClick(clickedPoly => {
                        clickedD = clickedPoly;
                        world.polygonCapColor(d => d === clickedPoly ? '#7AA2F7' : (d === clickedD ? 'lightgreen' : '#33467C'));

                        if (window.pywebview) {
                            window.pywebview.api.select_country(clickedPoly.properties.ADMIN);
                        }
                    })
                    .polygonsTransitionDuration(300);

                world.controls().autoRotate = false;
                world.controls().autoRotateSpeed = 1.0;

                window.addEventListener('resize', (event) => {
                    world.width([event.target.innerWidth]);
                    world.height([event.target.innerHeight]);
                });
            });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    # Silence pywebview logger and GTK import warnings
    logging.getLogger("pywebview").setLevel(logging.CRITICAL)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging"
    x, y, w, h = 0, 0, 800, 600
    app_name = "rolltv"

    if len(sys.argv) >= 6:
        x, y, w, h = (
            int(sys.argv[1]),
            int(sys.argv[2]),
            int(sys.argv[3]),
            int(sys.argv[4]),
        )

        app_name = sys.argv[5]

    api = Api(app_name)

    window = webview.create_window(
        "World",
        html=html,
        js_api=api,
        width=w,
        height=h,
        x=x,
        y=y,
        frameless=False,
        on_top=False,
        background_color="#1A1B26",
    )

    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "icon.png")
    threading.Thread(target=stdin_listener, args=(window,), daemon=True).start()
    webview.start(icon=icon_path)
