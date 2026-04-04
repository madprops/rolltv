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
          version = "1.0.0";
          pyproject = true;

          src = ./.;

          build-system = [
            pythonPackages.setuptools
          ];

          # This hook ensures the Python app can find Qt platform plugins at runtime
          nativeBuildInputs = [
            pkgs.qt6.wrapQtAppsHook
          ];

          # The Nix build sandbox prevents writing to ~/.local.
          # We set HOME to a temporary directory so your setup.py post-install doesn't crash.
          preBuild = ''
            export HOME=$(mktemp -d)
          '';

          # PyPI dependencies mapped to Nixpkgs python packages
          propagatedBuildInputs = with pythonPackages; [
            mpv
            pywebview
            qtpy
            pyqt6
            pyqt6-webengine
          ];

          # Install desktop file and icon properly into the Nix store ($out).
          postInstall = ''
            APP_NAME=$(${pkgs.python3}/bin/python -c 'from src.info import info; print(info.name)')
            APP_FULL_NAME=$(${pkgs.python3}/bin/python -c 'from src.info import info; print(info.full_name)')

            # Install the icon to the standard XDG directory in the Nix store
            install -Dm644 src/icon.png $out/share/icons/hicolor/256x256/apps/$APP_NAME.png

            # Create the desktop file pointing to the Nix store executable
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
      in {
        default = pkgs.mkShell {
          packages = [
            pkgs.python3
            pkgs.python3Packages.pip
            pkgs.python3Packages.virtualenv
          ];
        };
      });
  };
}