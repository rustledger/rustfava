%global debug_package %{nil}

Name:           rustfava
Version:        0.1.0
Release:        1%{?dist}
Summary:        Web interface for rustledger double-entry accounting

License:        MIT
URL:            https://github.com/rustledger/rustfava
Source0:        %{pypi_source rustfava}

BuildArch:      noarch
BuildRequires:  python3-devel >= 3.13
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools >= 80
BuildRequires:  python3-setuptools_scm >= 8
BuildRequires:  python3-babel >= 2.7
BuildRequires:  python3-wheel

Requires:       python3 >= 3.13
Requires:       python3-flask >= 2.2
Requires:       python3-flask-babel >= 3
Requires:       python3-jinja2 >= 3
Requires:       python3-werkzeug >= 2.2
Requires:       python3-click >= 7
Requires:       python3-markdown2 >= 2.3
Requires:       python3-ply >= 3.11
Requires:       python3-pydantic >= 2.0
Requires:       python3-cheroot >= 8
Requires:       python3-watchfiles >= 0.20
Requires:       wasmtime

%description
rustfava is a web interface for viewing and exploring rustledger/beancount
accounting files. It provides reports, charts, and an interactive query
interface for double-entry bookkeeping.

Features:
- Income statement, balance sheet, and other standard reports
- Interactive charts and graphs
- BQL query interface
- Editor with syntax highlighting
- Multi-file ledger support

%prep
%autosetup -n rustfava-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files rustfava

%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/rustfava

%changelog
* Sat Jan 25 2026 rustfava <rustfava@users.noreply.github.com> - 0.1.0-1
- Initial package
