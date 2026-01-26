{
  description = "Rustfava - web interface for rustledger";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # Read sources from JSON file (updated by CI)
        desktopSources = builtins.fromJSON (builtins.readFile ./desktop-sources.json);
        version = desktopSources.version;

        # Map Nix system to sources key
        systemKey =
          if system == "x86_64-linux" then "x86_64-linux"
          else if system == "aarch64-linux" then "aarch64-linux"
          else if system == "x86_64-darwin" then "x86_64-darwin"
          else if system == "aarch64-darwin" then "aarch64-darwin"
          else throw "Unsupported system: ${system}";

        # Target triple for the current platform (used in tarball name)
        targetTriple =
          if pkgs.stdenv.isLinux then
            if pkgs.stdenv.hostPlatform.isx86_64 then "x86_64-unknown-linux-gnu"
            else if pkgs.stdenv.hostPlatform.isAarch64 then "aarch64-unknown-linux-gnu"
            else throw "Unsupported Linux architecture"
          else if pkgs.stdenv.isDarwin then
            if pkgs.stdenv.hostPlatform.isAarch64 then "aarch64-apple-darwin"
            else "x86_64-apple-darwin"
          else throw "Unsupported platform";

        # Get source for this system (if available)
        hasDesktopSource = desktopSources ? ${systemKey};
        desktopSource = if hasDesktopSource then desktopSources.${systemKey} else null;

        # Download desktop tarball from GitHub releases
        desktopTarball = if hasDesktopSource then pkgs.fetchurl {
          url = desktopSource.url;
          hash = desktopSource.hash;
        } else null;

        # Desktop app from release tarball
        rustfava-desktop = if desktopTarball != null then pkgs.stdenv.mkDerivation {
          pname = "rustfava-desktop";
          inherit version;

          src = desktopTarball;
          sourceRoot = ".";

          nativeBuildInputs = with pkgs; [
            autoPatchelfHook
            makeWrapper
          ];

          buildInputs = with pkgs; [
            stdenv.cc.cc.lib
            openssl
          ] ++ lib.optionals stdenv.isLinux [
            webkitgtk_4_1
            libsoup_3
            glib-networking
            gtk3
            glib
            cairo
            pango
            gdk-pixbuf
            librsvg
          ];

          installPhase = ''
            mkdir -p $out
            cp -r bin lib $out/

            # Create symlinks without target triple suffix for PATH lookup
            # The desktop app falls back to these when sidecar lookup fails
            for bin in $out/bin/*-${targetTriple}*; do
              if [ -f "$bin" ]; then
                base=$(basename "$bin" | sed "s/-${targetTriple}//")
                ln -sf "$(basename "$bin")" "$out/bin/$base"
              fi
            done

            # Create rustfava -> rustfava-server symlink for backwards compatibility
            # Old releases look for 'rustfava' in PATH as fallback
            ln -sf "rustfava-server-${targetTriple}" "$out/bin/rustfava"

            # Wrap all binaries with wasmtime in PATH and GTK settings
            for bin in $out/bin/*; do
              if [ -f "$bin" ] && [ -x "$bin" ]; then
                wrapProgram "$bin" \
                  --prefix PATH : "${pkgs.wasmtime}/bin" \
                  --set GIO_MODULE_DIR "${pkgs.glib-networking}/lib/gio/modules" \
                  --prefix XDG_DATA_DIRS : "${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:${pkgs.gtk3}/share/gsettings-schemas/${pkgs.gtk3.name}"
              fi
            done
          '';

          meta = with pkgs.lib; {
            description = "Desktop app for rustfava - double-entry bookkeeping";
            homepage = "https://github.com/rustledger/rustfava";
            license = licenses.mit;
            platforms = platforms.linux;
            mainProgram = "rustfava-desktop";
          };
        } else null;

        # Python with Rustfava dependencies for dev shell
        pythonEnv = pkgs.python313.withPackages (ps: with ps; [
          flask flask-babel jinja2 markdown2 ply watchfiles werkzeug
          click markupsafe cheroot beancount beangulp
          pytest pytest-cov setuptools wheel build
        ]);

        # Rustfava CLI - installs via uv on first run from PyPI
        rustfava = pkgs.writeShellApplication {
          name = "rustfava";
          runtimeInputs = [ pkgs.python313 pkgs.uv pkgs.wasmtime ];
          text = ''
            RUSTFAVA_HOME="''${XDG_DATA_HOME:-$HOME/.local/share}/rustfava"
            VENV="$RUSTFAVA_HOME/venv"
            if [ ! -f "$VENV/bin/rustfava" ]; then
              echo "Installing rustfava from PyPI..."
              mkdir -p "$RUSTFAVA_HOME"
              uv venv "$VENV" --python ${pkgs.python313}/bin/python
              uv pip install --python "$VENV/bin/python" rustfava
            fi
            exec "$VENV/bin/rustfava" "$@"
          '';
        };

      in {
        packages = {
          default = rustfava;
        } // pkgs.lib.optionalAttrs (rustfava-desktop != null) {
          desktop = rustfava-desktop;
        };

        apps = {
          default = {
            type = "app";
            program = "${rustfava}/bin/rustfava";
          };
        } // pkgs.lib.optionalAttrs (rustfava-desktop != null) {
          desktop = {
            type = "app";
            program = "${rustfava-desktop}/bin/rustfava-desktop";
          };
        };

        # Dev shell for development
        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.wasmtime
            pkgs.just pkgs.jq pkgs.fd pkgs.ripgrep pkgs.uv
            pkgs.bun pkgs.nodejs_latest

            # Tauri/desktop development deps
            pkgs.cargo-tauri
            pkgs.rustc pkgs.cargo
            pkgs.pkg-config
            pkgs.openssl
          ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
            pkgs.webkitgtk_4_1
            pkgs.libsoup_3
            pkgs.glib-networking
            pkgs.gtk3
            pkgs.librsvg
            pkgs.gsettings-desktop-schemas
          ];

          shellHook = ''
            echo "Rustfava development environment"

            # GTK environment for Tauri
            export XDG_DATA_DIRS="${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:${pkgs.gtk3}/share/gsettings-schemas/${pkgs.gtk3.name}:$XDG_DATA_DIRS"
            export GIO_MODULE_DIR="${pkgs.glib-networking}/lib/gio/modules"

            if [ ! -d ".venv" ]; then
              uv venv .venv --system-site-packages
            fi
            source .venv/bin/activate
            if [ ! -f ".venv/.uv-installed" ]; then
              uv pip install pyexcel pyexcel-ods3 pyexcel-xlsx
              uv pip install -e . --no-deps
              touch .venv/.uv-installed
            fi
            export PYTHONPATH="$PWD/src:$PYTHONPATH"

            echo ""
            echo "For desktop development: cd desktop && bun install && bun run tauri:dev"
          '';
        };
      }
    );
}
