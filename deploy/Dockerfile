# Dockerfile — single-container CMS (Contest Management System) on Ubuntu 24.04
# Includes: PostgreSQL server + CMS services inside one container.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    CMS_HOME=/opt/cms \
    CMS_USER=cmsuser \
    CMS_INSTALL_DIR=/opt/cms/install \
    PGDATA=/var/lib/postgresql/data \
    LANG=C.UTF-8


# 1) Base OS + dependencies (per official docs for Ubuntu 24.04)
#    Also add tools we need (git, curl), dumb-init, and supervisor.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git dumb-init supervisor sudo \
    build-essential openjdk-11-jdk-headless fp-compiler \
    postgresql postgresql-client postgresql-contrib \
    python3.12 python3.12-dev python3-pip python3-venv \
    libpq-dev libcups2-dev libyaml-dev libffi-dev \
    shared-mime-info cppreference-doc-en-html zip \
    nginx-full php-cli texlive-latex-base a2ps \
    ghc rustc mono-mcs pypy3 \
    && rm -rf /var/lib/apt/lists/*

ENV CMS_CONFIG_FILE=/etc/cms.conf

# 2) Install Isolate (official upstream repo for Ubuntu 24.04 - Noble)
RUN mkdir -p /etc/apt/keyrings && \
    bash -lc "echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc] http://www.ucw.cz/isolate/debian/ noble-isolate main' > /etc/apt/sources.list.d/isolate.list" && \
    curl -fsSL https://www.ucw.cz/isolate/debian/signing-key.asc -o /etc/apt/keyrings/isolate.asc && \
    apt-get update && apt-get install -y isolate && \
    rm -rf /var/lib/apt/lists/*

# 3) Create cmsuser (as recommended by CMS docs)
RUN useradd --user-group --create-home --comment CMS ${CMS_USER} && \
    usermod -a -G isolate ${CMS_USER}

# Create install dir and hand it to cmsuser
RUN mkdir -p /opt/cms && chown -R ${CMS_USER}:${CMS_USER} /opt/cms

# 4) Fetch CMS source at a fixed tag and install into a virtualenv
USER ${CMS_USER}
WORKDIR /home/${CMS_USER}

# Use git to ensure we get submodules if/when needed in the future.
RUN git clone --depth 1 --branch cprog https://github.com/NTU-CSIE1210/cms src

# Create target venv and install CMS from source (install.py may not exist on the tag)
RUN python3 -m venv ${CMS_INSTALL_DIR} && \
    . ${CMS_INSTALL_DIR}/bin/activate && \
    pip install --upgrade pip setuptools wheel && \
    ( [ -f src/requirements.txt ] && pip install -r src/requirements.txt || true ) && \
    pip install -e src

# Make venv convenient on login shells
RUN echo "source ${CMS_INSTALL_DIR}/bin/activate" >> /home/${CMS_USER}/.profile

# 5) Prepare default config directory and logs
RUN mkdir -p ${CMS_INSTALL_DIR}/etc ${CMS_INSTALL_DIR}/var/log

# Create log directory for CMS services and hand it to cmsuser
RUN mkdir -p /var/local/log && chown -R ${CMS_USER}:${CMS_USER} /var/local

# 6) Back to root for DB setup, supervisor & entrypoint wiring
USER root

# 6a) Prepare PostgreSQL data directory (owned by postgres)
RUN mkdir -p ${PGDATA} && chown -R postgres:postgres ${PGDATA}

# 6b) Supervisor config to run Postgres and CMS services
RUN mkdir -p /etc/supervisor/conf.d

# Supervisor program: PostgreSQL
RUN <<'EOF'
cat >/etc/supervisor/conf.d/postgres.conf <<'CFG'
[program:postgres]
command=/usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/data -c listen_addresses=localhost
user=postgres
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/postgres.out.log
stderr_logfile=/var/log/supervisor/postgres.err.log
stopsignal=QUIT
stopasgroup=true
killasgroup=true
CFG
EOF

# Supervisor program: cmsLogService
RUN <<'EOF'
cat >/etc/supervisor/conf.d/cms_log.conf <<'CFG'
[program:cms_log]
command=/opt/cms/install/bin/python /home/cmsuser/src/scripts/cmsLogService 0
user=cmsuser
directory=/home/cmsuser
environment=HOME="/home/cmsuser",USER="cmsuser",HOSTNAME="localhost",CMS_CONFIG_FILE="/etc/cms.conf",PATH="/opt/cms/install/bin:/usr/bin:/bin"
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/cms_log.out.log
stderr_logfile=/var/log/supervisor/cms_log.err.log
CFG
EOF

# Supervisor program: cmsResourceService
RUN <<'EOF'
cat >/etc/supervisor/conf.d/cms_resource.conf <<'CFG'
[program:cms_resource]
command=/opt/cms/install/bin/python /home/cmsuser/src/scripts/cmsResourceService -a 0
user=cmsuser
directory=/home/cmsuser
autostart=true
autorestart=true
environment=HOME="/home/cmsuser",USER="cmsuser",HOSTNAME="localhost",CMS_CONFIG_FILE="/etc/cms.conf",PATH="/opt/cms/install/bin:/usr/bin:/bin"
stdout_logfile=/var/log/supervisor/cms_resource.out.log
stderr_logfile=/var/log/supervisor/cms_resource.err.log
CFG
EOF

# 7) First-start script:
#    - Initialize Postgres if empty
#    - Create cms DB, role, and grants
#    - Create cms configs
#    - Initialize CMS schema
#    - Start services via supervisor
RUN <<'EOF'
cat >/usr/local/bin/start-cms <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

# DB settings (from env or defaults) and URL used below
CMS_DB_NAME="${CMS_DB_NAME:-cmsdb}"
CMS_DB_USER="${CMS_DB_USER:-cmsuser}"
CMS_DB_PASS="${CMS_DB_PASS:-cmspassword}"
CMS_DB_URL="postgresql://${CMS_DB_USER}:${CMS_DB_PASS}@localhost/${CMS_DB_NAME}"

# Fast path: if already initialized before, just start supervisord
CMS_INSTALL_DIR="${CMS_INSTALL_DIR:-/opt/cms/install}"
INIT_MARKER="${CMS_INSTALL_DIR}/.initialized"
if [ -f "${INIT_MARKER}" ]; then
  echo "[fast] CMS already initialized; starting supervisord only..."
  exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
fi

echo "[cfg] Installing CMS configs into /etc..."
# Copy sample configs (root-writable location CMS expects)
[ -f /etc/cms.conf ] || cp "${SRC_DIR}/config/cms.conf.sample" /etc/cms.conf
[ -f /etc/cms.ranking.conf ] || cp "${SRC_DIR}/config/cms.ranking.conf.sample" /etc/cms.ranking.conf
# Patch DB URL into /etc/cms.conf
sed -i "s|^[[:space:]]*database[[:space:]]*=.*$|database = \"${CMS_DB_URL}\"|" /etc/cms.conf

# Ensure Postgres is initialized (run as postgres)
if [ ! -s "${PGDATA}/PG_VERSION" ]; then
  echo "[init] Initializing PostgreSQL cluster..."
  runuser -u postgres -- /usr/lib/postgresql/16/bin/initdb -D "${PGDATA}"
fi

# Ensure Postgres, role, DB, and grants via helper script
echo "[db] Ensuring Postgres and CMS DB are ready..."
/usr/local/bin/setup-postgres

# for i in $(seq 1 60); do
#  if runuser -u postgres -- /usr/lib/postgresql/16/bin/pg_isready -q; then
#    break
#  fi
#  sleep 1
# done

# DB/user/grants are ensured by setup-postgres above

# Prepare CMS configuration if not present
CMS_INSTALL_DIR="${CMS_INSTALL_DIR:-/opt/cms/install}"
CMS_ETC="${CMS_INSTALL_DIR}/etc"
mkdir -p "${CMS_ETC}"

if [ ! -f "${CMS_ETC}/cms.toml" ]; then
  echo "[cfg] Writing ${CMS_ETC}/cms.toml..."
  cat > "${CMS_ETC}/cms.toml" <<CFG
# Minimal single-host config
[database]
database = "${CMS_DB_URL}"

[core_services]
# ResourceService -a will start all required services on this host.
CFG
fi

if [ ! -f "${CMS_ETC}/cms_ranking.toml" ]; then
  echo "[cfg] Writing ${CMS_ETC}/cms_ranking.toml..."
  cat > "${CMS_ETC}/cms_ranking.toml" <<CFG
[database]
database = "${CMS_DB_URL}"
CFG
fi

# Initialize CMS schema if needed
echo "[cms] Ensuring CMS schema exists..."
source "${CMS_INSTALL_DIR}/bin/activate"
if ! psql "${CMS_DB_URL}" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' LIMIT 1" | grep -q 1; then
  cmsInitDB
fi

echo ""
echo "Admin UI:    http://localhost:8889/  (create an admin with: cmsAddAdmin <name>)"
echo "Contest UI:  http://localhost:8888/"
echo ""

# Keep the container in the foreground by re-attaching to supervisord
# Run supervisord in the foreground so the container stays up
# Stop any temporary postgres instance started during setup to avoid port conflicts
runuser -u postgres -- /usr/lib/postgresql/16/bin/pg_ctl -D "${PGDATA}" -m fast -w stop || true
touch "${INIT_MARKER}"
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
SCRIPT
chmod +x /usr/local/bin/start-cms
EOF

# 8) Expose CMS web ports (ContestWebServer ~8888, AdminWebServer ~8889)
EXPOSE 8888 8889

# 9) Run as root (entrypoint uses runuser to drop privileges where needed)
USER root
COPY setup-postgres.sh /usr/local/bin/setup-postgres
RUN chmod +x /usr/local/bin/setup-postgres


# 10) Entrypoint
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/usr/local/bin/start-cms"]
