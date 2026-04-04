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

          buildInputs = [
            pkgs.mpv
          ];

          # We set HOME to a temp directory so post-install doesn't crash.
          # We ALSO patch requirements.txt on the fly so the PyPI name "python-mpv"
          # matches the Nixpkgs name "mpv", bypassing the strict dependency checker crash.
          preBuild = ''
            export HOME=$(mktemp -d)
            sed -i 's/python-mpv/mpv/g' requirements.txt
          '';

          # PyPI dependencies mapped to Nixpkgs python packages
          # We include tkinter here to ensure the _tkinter C-extension is available
          propagatedBuildInputs = with pythonPackages; [
            tkinter
            mpv
            pywebview
          ];

          # Install desktop file and icon properly into the Nix store ($out).
          postInstall = ''
            APP_NAME=$(${pkgs.python3}/bin/python -c 'from src.info import info; print(info.name)')
            APP_FULL_NAME=$(${pkgs.python3}/bin/python -c 'from src.info import info; print(info.full_name)')

            install -Dm644 src/icon.png $out/share/icons/hicolor/256x256/apps/$APP_NAME.png

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