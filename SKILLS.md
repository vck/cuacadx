# CUACADX — Fresh Start & Deployment Guide

## Fresh Start on a New Machine (macOS or VPS)

Complete setup from bare OS to running services.

### 1. System Dependencies

```bash
# macOS
brew install python@3.12 tmux node

# Ubuntu/Debian VPS
sudo apt update && sudo apt install -y python3.12 python3.12-venv python3.12-dev tmux git nodejs npm
```

### 2. Clone & Virtual Env

```bash
git clone <repo-url> /opt/cuacadx   # or ~/cuacadx for dev
cd /opt/cuacadx
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install --upgrade pip
pip install torch torchvision torchaudio  # macOS: --index-url https://download.pytorch.org/whl/cpu
pip install earth2studio nvidia-physicsnemo
pip install numpy pandas xarray cfgrib netCDF4
pip install fastapi uvicorn pyarrow
pip install certifi pyproj scipy
pip install s3fs  # optional, for AWS data access
```

### 4. Download Model Weights

The FourCastNet model (~287MB) auto-downloads from HuggingFace on first run:

```bash
# Trigger download by importing the model
python3 -c "
from earth2studio.models.auto.package import Package
from earth2studio.models.px.fcn import FCN
pkg = Package('models/fourcastnet')
_ = FCN.load_model(pkg)
print('Model loaded OK')
"
```

This caches `fcn.mdlus`, `global_means.npy`, `global_stds.npy` under `models/fourcastnet/`.

### 5. Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 6. First Forecast Run

```bash
# Quick test: 4 steps (24h)
python run_fcn.py --steps 4

# Full 28-step (168h) forecast
python run_fcn.py --steps 28
```

Wait for downloads (~2 min for 26 GRIB files) + ~2 min for inference.
Output goes to `data/fcn/<date>/<cycle>/forecast.parquet`.

### 7. Launch Services (tmux)

```bash
# Kill any stale sessions
tmux kill-session -t cuacadx 2>/dev/null

# Create session with 3 windows: backend, frontend, forecast
tmux new-session -d -s cuacadx -n api
tmux send-keys -t cuacadx:api 'cd /opt/cuacadx && source .venv/bin/activate && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000' Enter

tmux new-window -t cuacadx -n frontend
tmux send-keys -t cuacadx:frontend 'cd /opt/cuacadx/frontend && npm run dev -- --host 0.0.0.0' Enter

tmux new-window -t cuacadx -n forecast
tmux send-keys -t cuacadx:forecast 'cd /opt/cuacadx && source .venv/bin/activate && python run_fcn.py --steps 28' Enter

# Attach to see all windows
tmux attach -t cuacadx
```

### 8. Verify

```
http://<vps-ip>:5173/     → Dashboard
http://<vps-ip>:8000/docs → FastAPI Swagger
```

List running sessions: `tmux ls`
Attach to session: `tmux attach -t cuacadx`

### 9. tmux Cheat Sheet (for VPS)

| Action | Key |
|---|---|
| Detach | `Ctrl-b d` |
| Switch window | `Ctrl-b n` / `Ctrl-b p` |
| Go to window N | `Ctrl-b N` (0-9) |
| Kill pane | `Ctrl-b x` (type `y`) |
| Scroll | `Ctrl-b [` then PgUp/PgDn, `q` to quit |
| Horizontal split | `Ctrl-b "` |
| Vertical split | `Ctrl-b %` |

### 10. Troubleshooting

- **Port 8000 in use**: `lsof -ti:8000 | xargs kill -9`
- **GFS download fails (HTTP 500)**: NOMADS rate-limits parallel requests. Pipeline
  uses sequential + 1-2s delays. Retry with `python run_fcn.py --steps 28`.
- **Model produces garbage**: Check dtype (must be float32) and HGT conversion
  (`z*9.80665` in `fourcastnet_pipeline.py:158`).
- **Frontend proxy errors**: Verify `frontend/vite.config.ts` points to the backend
  port (default `localhost:8000`).

---

## tmux Deployment (Original Reference)

## Why tmux
Keeps the backend alive on a headless VPS after SSH disconnect. Each service runs in its own
pane: FastAPI worker, forecast worker, frontend dev server, DB watcher.

## Basic Session

```bash
# Create session
tmux new-session -s cuacadx -d

# Split into panes: top = API, bottom = logs
tmux send-keys -t cuacadx 'source .venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8899' Enter
tmux split-window -h -t cuacadx
tmux send-keys -t cuacadx 'tail -f data/fcn/forecast.log' Enter

# Detach: Ctrl-b d
# Reattach: tmux attach -t cuacadx
```

## Multi-Window Layout

```
┌─────────────────────────────────┬──────────────────────────────┐
│  Window 0: API                  │  Window 1: Forecast Worker   │
│                                 │                              │
│  uvicorn backend.main:app       │  watch -n 3600 python3       │
│  --host 0.0.0.0 --port 8899    │    run_fcn.py                │
│                                 │                              │
├─────────────────────────────────┼──────────────────────────────┤
│  Window 2: Logs                 │  Window 3: Monitor           │
│                                 │                              │
│  multitail                     │  htop                        │
│    backend/access.log           │  nvidia-smi (if GPU)         │
│    backend/error.log            │  df -h                       │
└─────────────────────────────────┴──────────────────────────────┘
```

## Quick Commands

```bash
# Create full layout
tmux new-session -s cuacadx -d
tmux send-keys -t cuacadx 'cd /opt/cuacadx && source .venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8899 --reload' Enter

# New window for forecast runner
tmux new-window -t cuacadx -n forecast
tmux send-keys -t cuacadx:forecast 'cd /opt/cuacadx && source .venv/bin/activate && watch -n 3600 python3 run_fcn.py' Enter

# New window for logs
tmux new-window -t cuacadx -n logs
tmux send-keys -t cuacadx:logs 'cd /opt/cuacadx && tail -f data/fcn/*/forecast.parquet 2>/dev/null || echo waiting' Enter

# Attach
tmux attach -t cuacadx
```

## Session Management

```bash
tmux ls                         # list sessions
tmux attach -t cuacadx          # attach
tmux kill-session -t cuacadx    # kill entire session
tmux send-keys -t cuacadx C-c   # Ctrl+C to running process
```

## tmux Cheat Sheet (for VPS)

| Action | Key |
|---|---|
| Detach | `Ctrl-b d` |
| Switch window | `Ctrl-b n` / `Ctrl-b p` |
| Go to window N | `Ctrl-b N` (0-9) |
| Split vertical | `Ctrl-b %` |
| Split horizontal | `Ctrl-b "` |
| Kill pane | `Ctrl-b x` |
| Scroll | `Ctrl-b [` then PgUp/PgDn |

## VPS Setup (Ubuntu/Debian)

```bash
# Install tmux
sudo apt install tmux -y

# Install cuacadx
cd /opt
sudo git clone https://github.com/yourorg/cuacadx
cd cuacadx
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: persistent tmux config
echo "set -g mouse on" >> ~/.tmux.conf
echo "set -g history-limit 50000" >> ~/.tmux.conf
```
