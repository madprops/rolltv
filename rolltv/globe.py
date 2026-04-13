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
    try:
        for line in sys.stdin:
            try:
                line = line.strip()

                if line.startswith("COUNTRY:"):
                    parts = line.split(":", 1)
                    code = parts[1] if len(parts) > 1 else ""
                    window.evaluate_js(
                        f"if (window.setCountry) window.setCountry('{code}');"
                    )
                else:
                    parts = line.split(",")

                    if len(parts) == 4:
                        x, y, w, h = map(int, parts)
                        window.resize(w, h)
                        window.move(x, y)
            except Exception:
                pass
    except Exception:
        pass

    try:
        window.destroy()
    except Exception:
        pass


html = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        body { margin: 0; padding: 0; background-color: #1A1B26; overflow: hidden; }
        #hover-tooltip { position: absolute; top: 10px; right: 15px; color: white; font-family: sans-serif; pointer-events: none; z-index: 10; font-size: 20px }
    </style>

    <script>
        console.warn = function() {};
        console.log = function() {};
        console.info = function() {};
    </script>

    <script src="https://unpkg.com/globe.gl"></script>
    <script src="https://unpkg.com/d3"></script>
</head>

<body>
    <div id="hover-tooltip"></div>
    <div id="globeViz"></div>

    <script>
        let activeCountryCode = null;
        let countriesData = null;
        let activeCountryName = "";
        let currentHover = null;

        window.setCountry = function(code) {
            activeCountryCode = code ? code.toUpperCase() : null;
            activeCountryName = "";
            if (window.worldInstance) {
                window.worldInstance.polygonCapColor(d => isMatch(d) ? "lightgreen" : "#33467C");

                if (activeCountryCode && countriesData) {
                    const matched = countriesData.find(isMatch);
                    if (matched) {
                        activeCountryName = matched.properties.ADMIN;
                        if (typeof d3 !== 'undefined') {
                            const centroid = d3.geoCentroid(matched);
                            const currentPov = window.worldInstance.pointOfView();
                            window.worldInstance.pointOfView({ lat: centroid[1], lng: centroid[0], altitude: currentPov.altitude }, 1000);
                        }
                    }
                }

                if (!currentHover) {
                    const tooltip = document.getElementById("hover-tooltip");
                    tooltip.innerText = activeCountryName;
                }
            }
        };

        function isMatch(d) {
            if (!activeCountryCode) return false;
            return d.properties.ISO_A2 === activeCountryCode ||
                   d.properties.ISO_A2_EH === activeCountryCode ||
                   d.properties.WB_A2 === activeCountryCode;
        }

        fetch("https://raw.githubusercontent.com/vasturiano/globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson")
            .then(res => res.json())
            .then(countries => {
                countriesData = countries.features;
                const world = Globe()
                    (document.getElementById("globeViz"))
                    .backgroundColor("#1A1B26")
                    .showAtmosphere(true)
                    .atmosphereColor("#7AA2F7")
                    .globeImageUrl("https://unpkg.com/three-globe/example/img/earth-dark.jpg")
                    .polygonsData(countries.features)
                    .polygonAltitude(0.01)
                    .polygonCapColor(d => isMatch(d) ? "lightgreen" : "#33467C")
                    .polygonSideColor(() => "#1F2335")
                    .polygonStrokeColor(() => "#7AA2F7")

                    .onPolygonHover(hoverD => {
                        currentHover = hoverD;
                        world.polygonCapColor(d => isMatch(d) ? "lightgreen" : (d === hoverD ? "#7AA2F7" : "#33467C"));
                        const tooltip = document.getElementById("hover-tooltip");
                        tooltip.innerText = hoverD ? hoverD.properties.ADMIN : activeCountryName;
                    })

                    .onPolygonClick(clickedPoly => {
                        if (window.pywebview) {
                            window.pywebview.api.select_country(clickedPoly.properties.ADMIN);
                        }
                    })

                    .polygonsTransitionDuration(300);

                world.controls().autoRotate = false;
                world.controls().autoRotateSpeed = 1.0;
                window.worldInstance = world;

                world.width(window.innerWidth);
                world.height(window.innerHeight);

                window.addEventListener("resize", () => {
                    world.width(window.innerWidth);
                    world.height(window.innerHeight);
                });
            });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    # Silence pywebview logger and GTK import warnings
    logging.getLogger("pywebview").setLevel(logging.CRITICAL)
    os.environ["QT_QPA_PLATFORM"] = "wayland"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging"
    os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"
    os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"
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
    elif len(sys.argv) == 2:
        app_name = sys.argv[1]

    api = Api(app_name)

    window = webview.create_window(
        "World",
        html=html,
        js_api=api,
        width=w,
        height=h,
        x=x,
        y=y,
        frameless=True,
        easy_drag=False,
        on_top=True,
        background_color="#1A1B26",
    )

    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "icon.png")
    threading.Thread(target=stdin_listener, args=(window,), daemon=True).start()

    if os.path.exists(icon_path):
        webview.start(icon=icon_path)
    else:
        webview.start()

    os._exit(0)
