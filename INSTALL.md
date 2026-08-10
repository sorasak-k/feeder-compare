# Installation

Stat Cap Compare is a Streamlit app that compares vehicle stat-capacity logs from the feeder service against the
stat-cap service. It runs entirely locally — no database or network service is required, only CSV files you upload
through the browser.

Steps 1 and 2 apply everywhere. Then jump to the section for your OS:

- [Linux — Fedora / RHEL](#3a-linux--fedora--rhel)
- [Linux — Debian / Ubuntu](#3b-linux--debian--ubuntu)
- [macOS](#3c-macos)
- [Windows](#3d-windows)

## 1. Requirements

| Component | Version    | Notes                                                                                        |
|-----------|------------|----------------------------------------------------------------------------------------------|
| Python    | 3.14.4     | Pinned target; 3.10+ also works                                                              |
| Streamlit | 1.61.1     | Pinned in `requirements.txt`; needs ≥1.49 for `st.navigation`, `st.pills`, `width="stretch"` |
| pandas    | 3.0.5      | Pinned in `requirements.txt`; ≥2.0 also works                                                |
| Browser   | any modern | Chrome / Firefox / Edge / Safari                                                             |

The project targets **Python 3.14.4**, the version recorded at the top of
`requirements.txt`. Anything from 3.10 up will run the app, but match 3.14.4 if you want the exact environment the pins
were resolved against.

## 2. Get the project

The app lives in a plain directory — there is no git repository to clone. Copy the
`stat_cap_compare` folder wherever you want it.

Expected layout:

```
stat_cap_compare/
├── app.py                 # entry point — page navigation
├── common.py              # CSV loading, session filtering, comparison, SQL templates
├── requirements.txt
├── INSTALL.md
├── USAGE.md
├── pages/
│   ├── compare.py
│   ├── compare_with_session.py
│   ├── compare_outside_session.py
│   ├── session_filter.py
│   └── generate_sql.py
├── example_data/          # sample CSVs and the source SQL template
└── data/                  # your own exports (optional)
```

## 3A. Linux — Fedora / RHEL

**Install Python** (Fedora ships a recent Python; this is a no-op if it is already there):

```bash
sudo dnf install python3 python3-pip
python3 --version
```

**Set up and run:**

```bash
cd /path/to/stat_cap_compare
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Your prompt is prefixed with `(.venv)` while the environment is active. `deactivate`
leaves it.

## 3B. Linux — Debian / Ubuntu

**Install Python.** Debian and Ubuntu split `venv` into a separate package — without it
`python3 -m venv` fails with *"ensurepip is not available"*:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
python3 --version
```

If the distro Python is older than 3.10, add a newer one:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.14 python3.14-venv
```

Then substitute `python3.14` for `python3` in the next block.

**Set up and run:**

```bash
cd /path/to/stat_cap_compare
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## 3C. macOS

**Install Python.** The system Python is not suitable — install your own with
[Homebrew](https://brew.sh):

```bash
brew install python@3.14
python3 --version
```

Or download the installer from [python.org/downloads](https://www.python.org/downloads/)
and run it.

**Set up and run:**

```bash
cd /path/to/stat_cap_compare
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

If your shell is `zsh` (the default) or `bash`, the `source` line is the same. On `fish`, use
`source .venv/bin/activate.fish` instead.

## 3D. Windows

**Install Python** with winget:

```powershell
winget install Python.Python.3.14
py --version
```

Or use the [python.org installer](https://www.python.org/downloads/windows/) — tick **"Add python.exe to PATH"** on the
first screen.

**Set up and run** in PowerShell:

```powershell
cd C:\path\to\stat_cap_compare
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

If activation is blocked by *"running scripts is disabled on this system"*, allow it for the current session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

In **Command Prompt** (`cmd.exe`) rather than PowerShell, activate with:

```bat
.venv\Scripts\activate.bat
```

## 4. Verify the install

With the environment active, this should print exactly `1.61.1 3.0.5`:

```bash
python -c "import streamlit, pandas; print(streamlit.__version__, pandas.__version__)"
```

`requirements.txt` pins exact versions, so every machine gets the same releases:

```
# Python 3.14.4
streamlit==1.61.1
pandas==3.0.5
```

## 5. Open the app

Streamlit prints the URLs it is serving on and opens your default browser:

```
Local URL: http://localhost:8501
Network URL: http://192.168.1.240:8501
```

Open the Local URL if the browser does not launch on its own. Stop the server with
`Ctrl+C` in the terminal.

### Running without activating the environment

Call the interpreter inside the virtual environment directly.

```bash
# Linux / macOS
./.venv/bin/python -m streamlit run app.py
```

```powershell
# Windows
.venv\Scripts\python.exe -m streamlit run app.py
```

### Choosing a port

The default is 8501, the same on every OS:

```bash
streamlit run app.py --server.port 8765
```

### Making it reachable from other machines

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8765
```

Others on the network then open `http://<your-ip>:8765`. The app has no authentication, so only do this on a trusted
network. The port also has to be open:

```bash
# Fedora / RHEL — this session only
sudo firewall-cmd --add-port=8765/tcp
```

```bash
# Debian / Ubuntu, if ufw is enabled
sudo ufw allow 8765/tcp
```

macOS and Windows prompt you to allow incoming connections the first time instead — approve the dialog for Python.

### Uploading large CSVs

Streamlit rejects uploads over 200 MB by default. Raise the limit when your exports are bigger:

```bash
streamlit run app.py --server.maxUploadSize 500
```

## 6. Check it works with the sample data

1. Open the **Compare Stat Only** page.
2. Upload `example_data/feeder_data/feeder_vehicle_stat_cap_log.csv` as the feeder file.
3. Upload `example_data/stat_cap_data/vehicle_stat_cap_log.csv` as the stat-cap file.

A metrics row and a colour-coded comparison table should appear. If it does, the installation is complete — continue
with [USAGE.md](USAGE.md).

## Troubleshooting

**`streamlit: command not found` / `'streamlit' is not recognized`**
The environment is not active, or the install did not finish. Re-activate it and re-run
`pip install -r requirements.txt`, or invoke the interpreter directly as shown in
[Running without activating the environment](#running-without-activating-the-environment).

**`ensurepip is not available` when creating the venv (Debian / Ubuntu)**
Install the venv package: `sudo apt install python3-venv`.

**`.venv\Scripts\Activate.ps1 cannot be loaded ... running scripts is disabled` (Windows)**
Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, or use
`cmd.exe` with `.venv\Scripts\activate.bat`.

**`ModuleNotFoundError: No module named 'common'`**
The app was started from the wrong directory. Run it from the project root, not from inside `pages/`.

**`Port 8501 is already in use`**
Another Streamlit process is still running. Find and stop it, or pass `--server.port`
with a free port.

```bash
# Linux
ss -ltnp | grep 8501

# macOS
lsof -i :8501
```

```powershell
# Windows
netstat -ano | findstr 8501
taskkill /PID <pid> /F
```

**`AttributeError: module 'streamlit' has no attribute 'pills'` (or `navigation`)**
Streamlit is too old. `pip install -r requirements.txt` installs a version new enough.

**Widgets render oddly after upgrading Streamlit**
The browser cached the old front-end bundle. Hard-refresh the tab: `Ctrl+Shift+R`
(Linux / Windows) or `Cmd+Shift+R` (macOS).

**Browser shows a blank page or hangs on a huge file**
The table is styled row by row, which is slow for very large results. Filter down on the page (see USAGE.md) or split
the CSV before uploading.
