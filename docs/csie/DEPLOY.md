# CMS 部署與開發手冊

cmsdev 團隊在 `cprog.csie.org` 上開發、測試、部署這個 CMS fork 的標準流程。

## 環境

| 項目 | 位置 | 說明 |
|---|---|---|
| 原始碼（本 repo） | `/srv/cms-src` | 擁有者 `hyper`，`cmsdev` 群組可讀寫 |
| 執行環境（venv） | `/home/cmsuser/cms` | `cmsuser` 擁有，editable install 連結至本 repo |
| 設定檔 | `/home/cmsuser/cms/etc/cms.toml` | `cmsuser` 擁有 |
| 正式站 | https://cprog.csie.org/ | 選手端 |
| 後台 | https://cprog.csie.org/aws/ | 管理端 |
| GitHub | `origin` = NTU-CSIE1210/cms，`upstream` = cms-dev/cms | |

Editable install 代表 `/srv/cms-src` 目前 checkout 的內容，就是服務重啟後會執行的內容，沒有另外的 build 步驟。

## 加入權限

```bash
sudo usermod -aG cmsdev <username>
```

加入後開一個新的 shell（或 `newgrp cmsdev`），群組才會生效。

## 開發流程

**1. 開分支**——`main` 是會被部署的分支，不要直接改。
```bash
cd /srv/cms-src
git checkout main && git pull
git checkout -b <username>/<簡短描述>
```

**2. 改程式碼**——自己的帳號、自己的 editor，不需要 sudo。

**3. 在隔離環境測試**——用 `CMS_CONFIG` 指到另一份設定檔，跑一個不影響正式站的 CMS 實例：
```bash
cp /home/cmsuser/cms/etc/cms.toml /tmp/cms.test.toml
# 編輯 /tmp/cms.test.toml：
#   [database] url  → 指到 cmsdb_test
#   [services]      → 每個 port 都位移，避免撞到正式服務（例如全部 +1000）

CMS_CONFIG=/tmp/cms.test.toml /home/cmsuser/cms/bin/cmsInitDB   # 第一次才要
CMS_CONFIG=/tmp/cms.test.toml /home/cmsuser/cms/bin/cmsLogService &
CMS_CONFIG=/tmp/cms.test.toml /home/cmsuser/cms/bin/cmsResourceService -a ALL
```
只綁 localhost，不經過 nginx，選手看不到。用 `curl` 打對應 port，或 SSH tunnel 進去用瀏覽器測。測完 `Ctrl+C` 關掉。

**4. Merge 回 main**
```bash
git checkout main && git pull
git merge --no-ff <username>/<簡短描述>
git push
```

**5. 部署**——唯一需要 sudo 的步驟。重啟正式服務代表變更真的上線給選手，值得是個刻意、有記錄的動作。
```bash
sudo -u cmsuser XDG_RUNTIME_DIR=/run/user/$(id -u cmsuser) \
    systemctl --user restart cms@ALL.service
```
確認起來了：
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://cprog.csie.org/
```

## 注意事項

- **只有一份 working tree**：`/srv/cms-src` 只有一個 checkout，不是每人一份。改完沒 commit 就去忙別的，別人重啟服務會連你半成品的東西一起部署上去。
- **部署的是硬碟上當下的內容，不是特定 commit**：不是自己剛 merge 的話，部署前先 `git checkout main && git pull`。
- **不要對正式資料庫跑 `cmsDropDB`**：只有跨版本升級 schema 才需要，而且會清空比賽資料。真的要動 schema，先 `cmsDumpExporter` 備份並知會全隊。

## 指令參考

| 動作 | 指令 |
|---|---|
| 查現在部署的 commit | `git -C /srv/cms-src log -1 --oneline main` |
| 看即時 log | `sudo -u cmsuser journalctl --user -u cms@ALL.service -f` |
| 重啟 | `sudo -u cmsuser XDG_RUNTIME_DIR=/run/user/$(id -u cmsuser) systemctl --user restart cms@ALL.service` |
| reload nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| 備份比賽資料庫 | `sudo -u cmsuser /home/cmsuser/cms/bin/cmsDumpExporter` |
