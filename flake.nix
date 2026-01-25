{
  description = "Rustfava - web interface for rustledger";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay.url = "github:oxalica/rust-overlay";
    rust-overlay.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, rust-overlay }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ rust-overlay.overlays.default ];
        };

        # Rust toolchain with WASM target
        rustToolchain = pkgs.rust-bin.stable.latest.default.override {
          targets = [ "wasm32-wasip1" ];
        };

        # Python with Rustfava dependencies
        pythonEnv = pkgs.python313.withPackages (ps: with ps; [
          # Rustfava core dependencies
          flask
          flask-babel
          jinja2
          markdown2
          ply  # Used for filter syntax parsing
          watchfiles
          werkzeug
          click
          markupsafe
          cheroot  # WSGI server for rustfava CLI

          # Beancount (optional - for legacy plugin support)
          beancount
          beangulp

          # Dev/test dependencies
          pytest
          pytest-cov

          # Build dependencies
          setuptools
          wheel
          build
        ]);

        # Rustfava runner script - installs via uv on first run (stable from PyPI)
        rustfava = pkgs.writeShellApplication {
          name = "rustfava";
          runtimeInputs = [ pkgs.python313 pkgs.uv pkgs.wasmtime ];
          text = ''
            RUSTFAVA_HOME="''${XDG_DATA_HOME:-$HOME/.local/share}/rustfava"
            VENV="$RUSTFAVA_HOME/venv"

            if [ ! -f "$VENV/bin/rustfava" ]; then
              echo "Installing rustfava..."
              mkdir -p "$RUSTFAVA_HOME"
              uv venv "$VENV" --python ${pkgs.python313}/bin/python
              uv pip install --python "$VENV/bin/python" rustfava
            fi

            exec "$VENV/bin/rustfava" "$@"
          '';
        };

        # Nightly runner - installs from git main branch
        # Requires bun for frontend compilation when building from source
        rustfava-nightly = pkgs.writeShellApplication {
          name = "rustfava";
          runtimeInputs = [ pkgs.python313 pkgs.uv pkgs.wasmtime pkgs.git pkgs.bun ];
          text = ''
            RUSTFAVA_HOME="''${XDG_DATA_HOME:-$HOME/.local/share}/rustfava-nightly"
            VENV="$RUSTFAVA_HOME/venv"

            if [ ! -f "$VENV/bin/rustfava" ]; then
              echo "Installing rustfava (nightly from main branch)..."
              mkdir -p "$RUSTFAVA_HOME"
              uv venv "$VENV" --python ${pkgs.python313}/bin/python
              # Install build dependencies first (needed for --no-build-isolation)
              uv pip install --python "$VENV/bin/python" setuptools setuptools_scm Babel wheel
              # --no-build-isolation ensures bun is available during frontend compilation
              uv pip install --python "$VENV/bin/python" --no-build-isolation "git+https://github.com/rustledger/rustfava.git"
            fi

            exec "$VENV/bin/rustfava" "$@"
          '';
        };

        # Desktop app runner for NixOS
        # Downloads AppImage from releases and wraps with rustfava in PATH
        mkDesktopApp = { name, rustfavaPkg }: pkgs.writeShellApplication {
          inherit name;
          runtimeInputs = [ rustfavaPkg pkgs.appimage-run pkgs.curl pkgs.jq ];
          text = ''
            RUSTFAVA_HOME="''${XDG_DATA_HOME:-$HOME/.local/share}/rustfava"
            APPIMAGE="$RUSTFAVA_HOME/rustfava-desktop.AppImage"

            # Check for updates and download AppImage if needed
            if [ ! -f "$APPIMAGE" ]; then
              echo "Downloading rustfava desktop app..."
              mkdir -p "$RUSTFAVA_HOME"

              # Get latest release AppImage URL
              RELEASE_URL=$(curl -s https://api.github.com/repos/rustledger/rustfava/releases/latest \
                | jq -r '.assets[] | select(.name | endswith(".AppImage")) | .browser_download_url')

              if [ -z "$RELEASE_URL" ] || [ "$RELEASE_URL" = "null" ]; then
                echo "Error: No AppImage found in latest release."
                echo "The desktop app may not be released yet. Try running 'nix run .#default' for the CLI."
                exit 1
              fi

              curl -L -o "$APPIMAGE" "$RELEASE_URL"
              chmod +x "$APPIMAGE"
            fi

            # Run the AppImage with rustfava in PATH (for PATH fallback feature)
            exec appimage-run "$APPIMAGE" "$@"
          '';
        };

        rustfava-desktop = mkDesktopApp { name = "rustfava-desktop"; rustfavaPkg = rustfava; };
        rustfava-desktop-nightly = mkDesktopApp { name = "rustfava-desktop"; rustfavaPkg = rustfava-nightly; };

      in {
        packages = {
          default = rustfava;
          nightly = rustfava-nightly;
          desktop = rustfava-desktop;
          desktop-nightly = rustfava-desktop-nightly;
        };

        apps = {
          default = {
            type = "app";
            program = "${rustfava}/bin/rustfava";
          };
          nightly = {
            type = "app";
            program = "${rustfava-nightly}/bin/rustfava";
          };
          desktop = {
            type = "app";
            program = "${rustfava-desktop}/bin/rustfava-desktop";
          };
          desktop-nightly = {
            type = "app";
            program = "${rustfava-desktop-nightly}/bin/rustfava-desktop";
          };
        };

        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv

            # WASM runtime for rustledger
            pkgs.wasmtime

            # Dev tools
            pkgs.just
            pkgs.jq
            pkgs.fd
            pkgs.ripgrep
            pkgs.uv  # Fast Python package manager

            # Bun for frontend build
            pkgs.bun

            # Node.js 23+ for frontend tests (required for registerHooks API)
            pkgs.nodejs_latest

            # Rust toolchain with WASM target for Tauri desktop app
            rustToolchain

            # Tauri system dependencies
            pkgs.pkg-config
            pkgs.openssl
            pkgs.webkitgtk_4_1
            pkgs.libsoup_3
            pkgs.glib-networking
            pkgs.librsvg
            pkgs.gsettings-desktop-schemas
            pkgs.gtk3

          ];

          shellHook = ''
            echo "🦀 Rustfava development environment"
            echo ""
            echo "Python: $(python --version)"
            echo "Bun: $(bun --version)"
            echo "wasmtime: $(wasmtime --version)"
            echo ""
            echo "WASM file: src/rustfava/rustledger/rustledger-wasi.wasm"
            echo ""

            # GTK/GSettings environment for Tauri
            export XDG_DATA_DIRS="${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:${pkgs.gtk3}/share/gsettings-schemas/${pkgs.gtk3.name}:$XDG_DATA_DIRS"
            export GIO_MODULE_DIR="${pkgs.glib-networking}/lib/gio/modules"

            # Create/activate venv for additional packages not in nixpkgs
            if [ ! -d ".venv" ]; then
              echo "Creating virtual environment..."
              uv venv .venv --system-site-packages
            fi
            source .venv/bin/activate

            # Install additional Python packages not in nixpkgs via uv
            if [ ! -f ".venv/.uv-installed" ]; then
              echo "Installing additional Python packages via uv..."
              uv pip install pyexcel pyexcel-ods3 pyexcel-xlsx
              # Install rustfava in editable mode for package metadata (version, etc.)
              uv pip install -e . --no-deps
              touch .venv/.uv-installed
            fi

            # Add src to PYTHONPATH for development
            export PYTHONPATH="$PWD/src:$PYTHONPATH"

            # Create a wrapper script for the rustfava CLI so tests can find it
            mkdir -p "$PWD/.dev-bin"
            cat > "$PWD/.dev-bin/rustfava" << 'WRAPPER'
#!/usr/bin/env bash
exec python -m rustfava.cli "$@"
WRAPPER
            chmod +x "$PWD/.dev-bin/rustfava"
            export PATH="$PWD/.dev-bin:$PATH"
          '';
        };
      }
    );
}
