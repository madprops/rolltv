{
  description = "Roll TV - IPTV Player";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = {self, nixpkgs}: let
    supportedSystems = [
      "x86_64-linux"
      "aarch64-linux"
    ];

    forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
  in {
    packages = forAllSystems (system:
      let
        pkgs = import nixpkgs {inherit system;};
        pythonPackages = pkgs.python3Packages;
      in {
        default = pythonPackages.buildPythonApplication {
          pname = "rolltv";
          version = "12.0.0";
          pyproject = true;

          src = ./.;

          build-system = [
            pythonPackages.setuptools
          ];

          # We need the Qt wrapper for PyQt6 to find Wayland/X11 plugins
          nativeBuildInputs = [
            pkgs.qt6.wrapQtAppsHook
          ];

          # The C-libraries required at runtime by the Python wrappers
          buildInputs = [
            pkgs.qt6.qtbase
            pkgs.qt6.qtwayland
            pkgs.mpv
          ];

          preBuild = ''
            export HOME=$(mktemp -d)

            # Fix PyPI to Nixpkgs naming mismatch to prevent dependency checker crash
            sed -i 's/python-mpv/mpv/g' requirements.txt
          '';

          # ALL required python packages, including tkinter for main.py
          propagatedBuildInputs = with pythonPackages; [
            tkinter
            mpv
            pywebview
            qtpy
            pyqt6
            pyqt6-webengine
          ];

          # Expose C libraries to Python's ctypes module at runtime
          makeWrapperArgs = [
            "--prefix LD_LIBRARY_PATH : ${pkgs.lib.makeLibraryPath [ pkgs.mpv pkgs.qt6.qtbase pkgs.qt6.qtwayland ]}"
          ];

          postInstall = ''
            APP_NAME=$(${pkgs.python3}/bin/python -c 'from rolltv.info import info; print(info.name)')
            APP_FULL_NAME=$(${pkgs.python3}/bin/python -c 'from rolltv.info import info; print(info.full_name)')

            install -Dm644 rolltv/icon.png $out/share/icons/hicolor/256x256/apps/$APP_NAME.png

            mkdir -p $out/share/applications
            cat > $out/share/applications/$APP_NAME.desktop <<EOF
            [Desktop Entry]
            Version=1.0
            Name=$APP_FULL_NAME
            Exec=$out/bin/$APP_NAME
            Icon=$APP_NAME
            Terminal=false
            Type=Application
            Categories=Utility;
            EOF
          '';
        };
      });

    devShells = forAllSystems (system:
      let
        pkgs = import nixpkgs {inherit system;};

        # Create the custom python environment that includes tkinter
        myPython = pkgs.python3.withPackages (ps: [
          ps.tkinter
          ps.mpv
          ps.pywebview
          ps.qtpy
          ps.pyqt6
          ps.pyqt6-webengine
        ]);

        # Create a custom ruby environment that includes the git gem
        myRuby = pkgs.ruby.withPackages (ps: [
          ps.git
        ]);

        # Standalone executable to initialize the venv
        venv_reqs = pkgs.writeShellScriptBin "venv_reqs" ''
          if [ ! -d "venv" ]; then
            echo "Creating virtual environment..."
            ${myPython}/bin/python -m venv --system-site-packages venv
          fi

          source venv/bin/activate

          if [ -f "requirements.txt" ]; then
            echo "Installing requirements..."
            pip install -r requirements.txt
          else
            echo "No requirements.txt found."
          fi
        '';

      in {
        default = pkgs.mkShell {
          packages = [
            myPython
            pkgs.python3Packages.pip
            pkgs.python3Packages.virtualenv
            pkgs.mpv
            pkgs.qt6.qtbase
            pkgs.qt6.qtwayland
            pkgs.ruff
            pkgs.mypy
            myRuby
            venv_reqs
          ];

          # Expose C libraries to Python's ctypes module
          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.mpv
            pkgs.qt6.qtbase
            pkgs.qt6.qtwayland
          ];
        };
      });
  };
}