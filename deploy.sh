#!/bin/bash
# Deploy to the N95 stable-services LXC, same tier as comfy-hub and email-triage.
# rsync the code and build the venv here; the systemd unit and Tailscale Serve
# go in from the Proxmox host via pct exec, because the CT's jeremy has no sudo.
#
# The dataset and the Immich key are NOT deployed by this script. They are not
# in this repo and must never be: see the note in .gitignore. Push them once,
# by hand, to the paths the config names.
set -e

DEPLOY_USER=${DEPLOY_USER:-jeremy}
DEPLOY_HOST=${DEPLOY_HOST:-stable-services.tail259324.ts.net}
DEPLOY_DIR=${DEPLOY_DIR:-kiddo-growth-chart}
HOST_PORT=${HOST_PORT:-8101}
SERVE_PORT=${SERVE_PORT:-8461}
CTID=${CTID:-101}

echo "Deploying kiddo-growth-chart to $DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_DIR"
ssh "$DEPLOY_USER@$DEPLOY_HOST" "mkdir -p $DEPLOY_DIR"

rsync -av --delete \
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='venv/' --exclude='.pytest_cache' --exclude='*.egg-info' \
  --exclude='.growth-data' \
  . "$DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_DIR/"

ssh "$DEPLOY_USER@$DEPLOY_HOST" "
  cd $DEPLOY_DIR
  python3 -m venv venv
  venv/bin/pip install -q --upgrade pip
  venv/bin/pip install -q -e '.[serve]'
"

cat <<TXT

Code deployed and venv built. Finish from the Proxmox host (ssh jeremy@192.168.1.4, sudo; CTID $CTID):

  sudo pct exec $CTID -- bash -c '
    cp /home/$DEPLOY_USER/$DEPLOY_DIR/systemd/kiddo-growth-chart.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now kiddo-growth-chart.service'
  sudo pct exec $CTID -- tailscale serve --bg --https=$SERVE_PORT http://127.0.0.1:$HOST_PORT

Already installed? A restart is still required — gunicorn holds the app and the
compiled Jinja templates in the worker, so an rsync-only deploy leaves the old
page being served and reports success. A HUP is enough and needs no root:

  ssh $DEPLOY_USER@$DEPLOY_HOST "pkill -HUP -of '$DEPLOY_DIR/venv/bin/gunicorn'"

Then open:
  https://$DEPLOY_HOST:$SERVE_PORT/
TXT
