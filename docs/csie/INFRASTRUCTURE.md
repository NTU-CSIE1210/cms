# CMS 基礎設施部署紀錄

記錄 `cprog.csie.org` 主機從零架起 CMS（cms-dev/cms）服務的完整過程，給日後重建主機或想搞懂架構的人參考。跟 [`DEPLOY.md`](./DEPLOY.md) 是互補文件：這份講怎麼架起來，`DEPLOY.md` 講架好之後怎麼開發。

## 主機資訊

| 項目 | 內容 |
|---|---|
| 網域 | cprog.csie.org |
| 公開 IP | 140.112.31.223 |
| 作業系統 | Ubuntu 26.04（resolute） |
| 硬體 | 144 核 CPU、751 GiB 記憶體、98 GiB 磁碟 |
| 部署日期 | 2026-09-13 |

## 架構

```
Internet
   │  HTTPS :443（Let's Encrypt TLS）
   ▼
 nginx  ──────────────────────── 直連 :8888 / :8889 → 由 ufw 阻擋
   │ proxy_pass /            │ proxy_pass /aws/
   ▼                         ▼
 ContestWebServer :8888    AdminWebServer :8889
        （均僅綁定 127.0.0.1）
   └────────────┬────────────┘
                │ 由 systemd --user 監督啟動
                ▼
   cmsResourceService（cms@ALL.service）
        ├─ EvaluationService
        ├─ ScoringService
        └─ Worker × 16 ── isolate（cgroup v2）沙盒 ── 執行選手提交之程式
                │
                ▼
          PostgreSQL（cmsdb）
```

nginx 是對外唯一入口，ufw 是第二道防線，擋掉所有直連 8888／8889 的連線。CMS 各服務都由 `cmsResourceService` 統一啟動監督，它本身則由 systemd 使用者服務 `cms@ALL.service` 拉起。

## 安裝流程

安裝過程需要大量特權操作，而主機原本沒有免密碼 sudo，所以期間用 `visudo` 檢查語法的方式建立了範圍限定的 `/etc/sudoers.d/temp-cms-setup`，裝完立刻移除並用 `sudo -n true` 驗證確實失效。

### 系統套件與 isolate 沙盒

主機一開始沒有 PostgreSQL、nginx、評測沙盒。系統內建 Python 3.14 太新，CMS 依賴的套件（Tornado 4.5.3、gevent 等）不保證相容，所以沒用系統 Python，另外裝了獨立版本（見下方「安裝 CMS 本體」）。

```bash
sudo apt install -y build-essential openjdk-11-jdk-headless fp-compiler \
    postgresql postgresql-client libpq-dev libyaml-dev libffi-dev \
    shared-mime-info cppreference-doc-en-html zip curl \
    nginx-full certbot python3-certbot-nginx ufw
```

比賽只收 C/C++，`build-essential` 內建的 gcc/g++ 就夠了；這裡裝的 Java、Free Pascal 是依官方建議清單裝的，實際上沒用到，因為磁碟空間充裕（98 GiB 只用 13 GiB）就留著沒移除。建 contest 時記得後台「Allowed languages」要手動改成只有 C11/gcc 和 C++17 或 C++20/g++。

`isolate`（cgroup v2 沙盒，用來隔離選手程式的執行）不在 Ubuntu 官方套件庫，要另外加維護者的 apt repo：

```bash
sudo install -d /etc/apt/keyrings
curl -fsSL https://www.ucw.cz/isolate/debian/signing-key.asc \
    | sudo tee /etc/apt/keyrings/isolate.asc >/dev/null
echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc] \
    http://www.ucw.cz/isolate/debian/ noble-isolate main' \
    | sudo tee /etc/apt/sources.list.d/isolate.list
sudo apt update
sudo apt install -y isolate   # 2.7（CMS 要求 ≥ 2.0）
```

**備註：** 該 repo 原本有對應 Ubuntu 26.04 的 `resolute-isolate`，但當時還沒發布完整的 `Release` 檔（只有空目錄），改用 `noble-isolate`（24.04）。isolate 依賴極少，跨版本相容沒問題。

### 建立 cmsuser 服務帳號

CMS 用獨立的系統帳號執行，不是給人登入用的。

```bash
sudo useradd --user-group --create-home --comment CMS cmsuser
sudo usermod -a -G isolate cmsuser
sudo loginctl enable-linger cmsuser
```

`enable-linger` 是必要設定，不然 `cmsuser` 的 systemd 使用者服務會在沒人登入該帳號時被砍掉。

### 安裝 CMS 本體

以下都以 `cmsuser` 身份執行。用 `uv` 裝一個獨立的 Python 3.12（不用系統套件），再用 CMS 官方的 `install.py` 建 venv：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
. "$HOME/.local/bin/env"
uv python install 3.12   # 3.12.14

git clone https://github.com/cms-dev/cms.git ~/cms-src
cd ~/cms-src
PY312=~/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12
"$PY312" install.py --dir="$HOME/cms" cms
```

裝完後 `~/cms/bin/python` 就是 3.12.14，`cms*` 系列指令都能用；`isolate-check-environment` 用來確認沙盒能跑，它同時會建議關閉 CPU turbo boost、ASLR、transparent hugepages 等機器層級設定以求評測時間穩定——這些是給嚴格計時競賽（如 IOI）用的公平性要求，這裡是程式設計考試不卡緊時限，套用的代價（全機 ASLR 變弱、犧牲其他負載效能）不划算，所以沒做。cgroup 加 isolate 原有的記憶體／CPU 時間／行程數限制已經足夠公平正確。

> **後續變更：** 為了讓多人協作開發，原始碼目錄 `~/cms-src` 之後搬到 `/srv/cms-src`，改成 `hyper:cmsdev` 擁有——`cmsdev` 是新建的共用群組（成員：`hyper`、`cmsuser`、`qwe1rt1yuiop1`、`tmt514`），目錄設 `g+rwX` 並套 setgid，讓成員能直接用自己帳號開發，不用登入 `cmsuser`。`cmsuser` 的 venv 也重新用 `pip install -e /srv/cms-src` 裝成 editable install，改程式碼不用重裝、重啟服務就生效。GitHub remote 也調整過：`origin` 改指向團隊自己的 `NTU-CSIE1210/cms`，原本的 `cms-dev/cms` 改名成 `upstream` 方便合併官方更新。日常開發與部署流程見 [`DEPLOY.md`](./DEPLOY.md)。

### PostgreSQL 設定

依 CMS 官方文件建專用 role 和資料庫，並補兩個容易漏掉但必要的授權（沒給會導致無法正常寫入大型物件）：

```bash
sudo -u postgres createuser --username=postgres cmsuser
sudo -u postgres psql -c "ALTER ROLE cmsuser WITH PASSWORD '<隨機產生>';"
sudo -u postgres createdb --username=postgres --owner=cmsuser cmsdb
sudo -u postgres psql --dbname=cmsdb --command='ALTER SCHEMA public OWNER TO cmsuser'
sudo -u postgres psql --dbname=cmsdb --command='GRANT SELECT ON pg_largeobject TO cmsuser'
```

資料庫密碼用 `openssl rand -base64 24` 產生，存在 `/home/cmsuser/.cms_db_password`（權限 600，只有 `cmsuser` 可讀），不寫進任何文件。

### `cms.toml` 設定調整

CMS 的範例設定檔已經很完整，只改了三項：

| 設定項 | 改動 | 原因 |
|---|---|---|
| `[database] url` | 指向上面建的資料庫，含密碼 | 連正式資料庫 |
| `[web_server] secret_key` | 用 `cmscommon.crypto.get_hex_random_key()` 重新產生 | 範例金鑰是公開的，沿用會讓 session cookie 可被偽造 |
| `num_proxies_used` | `[contest_web_server]` 和 `[admin_web_server]` 都由 0 改成 1 | nginx 在前面，得告訴 CMS 信任來源 IP 標頭，不然記錄跟流量控管都會看到 nginx 的 IP |

`listen_address` 維持 `127.0.0.1`——這是後面 nginx 反代跟防火牆設計成立的前提。

### 資料庫初始化與後台帳號

```bash
~/cms/bin/cmsInitDB
~/cms/bin/cmsAddAdmin admin
```

`cmsAddAdmin` 只在執行當下印一次隨機密碼，沒有記錄下來，首次登入 `/aws/` 後應立即更改。

### systemd 使用者服務

CMS 沒有特殊權限地執行，所以用 systemd `--user` 服務（不是 `/etc/systemd/system/` 下的系統服務），靠前面的 `enable-linger` 維持常駐。

```bash
"$PY312" install.py --dir="$HOME/cms" systemd
```

| Unit | 內容 | 說明 |
|---|---|---|
| `cms-logging.service` | `cmsLogService` | 要最先啟動，其他服務都向它回報記錄 |
| `cms@ALL.service` | `cmsResourceService -a ALL` | 統一拉起 AdminWebServer、ContestWebServer、EvaluationService、ScoringService、16 個 Worker；`ALL` 代表一個 ContestWebServer 服務所有比賽，不用先建好比賽才能啟動服務 |

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u cmsuser)
sudo -u cmsuser systemctl --user enable --now cms-logging.service
sudo -u cmsuser systemctl --user enable --now cms@ALL.service
```

### nginx 與 TLS

依 CMS 官方命名慣例，`cws`（ContestWebServer）是選手端、`aws`（AdminWebServer）是管理端，前者服務 `/`，後者服務 `/aws/`。

```nginx
upstream cws {
    hash $remote_addr;      # 依 IP 分流：CMS 即時通知功能需求
    keepalive 500;
    server 127.0.0.1:8888;
}
upstream aws {
    keepalive 5;
    server 127.0.0.1:8889;
}

server {
    listen 80;
    server_name cprog.csie.org;

    location /aws/ {
        proxy_pass http://aws/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect / /aws/;
        client_max_body_size 100M;
    }

    location / {
        proxy_pass http://cws/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 100M;
    }
}
```

TLS 憑證由 certbot 的 nginx plugin 取得，並由它自動改寫上面這份設定檔（加上 443 埠的 `ssl_certificate` 區塊和 80 埠導向）：

```bash
sudo certbot --nginx -d cprog.csie.org --redirect
```

憑證到期日 2026-12-12，certbot 內建的 systemd timer 會自動更新。

**備註：** 團隊決議 `/aws/` 不在 nginx 層額外加 IP 白名單或 Basic Auth，只靠 CMS 自己的帳號登入。

### 防火牆

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

啟用前一定要先放行 SSH，不然會斷線鎖在外面。

### 驗證

| 檢查項目 | 預期結果 |
|---|---|
| `GET https://cprog.csie.org/` | 200 |
| `GET https://cprog.csie.org/aws/` | 302（導向登入頁） |
| `GET http://cprog.csie.org/` | 301（導向 HTTPS） |
| `ss -tlnp \| grep -E ":8888\|:8889"` | 僅綁定 127.0.0.1 |
| `systemctl --user status cms@ALL.service` | active，AWS／CWS／EvaluationService／ScoringService／16 個 Worker 都在跑 |

## 檔案位置與埠號

| 項目 | 路徑 |
|---|---|
| CMS 安裝根目錄 | `/home/cmsuser/cms/` |
| 設定檔 | `/home/cmsuser/cms/etc/cms.toml` |
| 記錄檔 | `/home/cmsuser/cms/log/` |
| systemd unit | `/home/cmsuser/.config/systemd/user/` |
| nginx site 設定 | `/etc/nginx/sites-available/cms` |
| TLS 憑證 | `/etc/letsencrypt/live/cprog.csie.org/` |
| 資料庫密碼 | `/home/cmsuser/.cms_db_password`（權限 600） |

| 埠號 | 服務 | 對外可達性 |
|---|---|---|
| 80 / 443 | nginx | 對外開放 |
| 8888 | ContestWebServer | 僅 localhost |
| 8889 | AdminWebServer | 僅 localhost |
| 5432 | PostgreSQL | 僅 localhost |
