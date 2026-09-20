# 使用者管理

管理學生帳號（User）與參賽記錄（Participation）。CMS 將兩者分開，同一批學生可重複用於多場考試。

**工作流程**：
1. 第一次：產生帳密（腳本）→ 匯入所有學生到資料庫（`cmsImportUser`）
2. 每次新考試：批量加入學生到比賽（腳本）

**說明**：CMS 的 `cmsImportUser -c` 只能指定一個比賽，`cmsAddParticipation` 一次只能加一位學生，因此使用腳本批量處理

## 初次匯入所有學生

### 1. 產生帳密

從 NTU Cool 下載學生名單（Excel），轉成 CSV，需包含欄位：`學號`、`姓名`、`信箱`

執行產生腳本：

```bash
python3 scripts/csie/generate_users.py student_list.csv
```

產生兩個檔案：
- `contest.yaml`：給 CMS 匯入
- `credentials.csv`：學生帳密清單，用於寄信通知

帳號：學號小寫（如 `b12345678`）
密碼：如 `cage-shiny-pasta-42`
First name：學號，Last name：中文姓名

### 2. 匯入到資料庫

在遠端伺服器上，以 cmsuser 身份執行：

```bash
sudo -u cmsuser -i
mkdir -p ~/students
cp contest.yaml ~/students/
cmsImportUser -A ~/students/
```

## 每次新考試加入學生

建立新比賽後，在遠端伺服器上以 cmsuser 身份執行：

```bash
sudo -u cmsuser -i
python3 /srv/cms-src/scripts/csie/add_users_to_contest.py <contest_id> ~/students/contest.yaml
```

腳本會自動跳過已在比賽中的學生。

## 腳本位置

| 腳本 | 路徑 |
|------|------|
| 產生帳密 | `/srv/cms-src/scripts/csie/generate_users.py` |
| 加入比賽 | `/srv/cms-src/scripts/csie/add_users_to_contest.py` |

## 其他說明

- `contest.yaml` 和 `credentials.csv` 含敏感資料，已在 `.gitignore` 排除
