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

### 設定額外 token（選用）

如果需要根據學生表現給予額外 token，可使用 `--bonus-tokens` 參數：

```bash
python3 /srv/cms-src/scripts/csie/add_users_to_contest.py <contest_id> \
    ~/students/contest.yaml \
    --bonus-tokens ~/bonus_tokens.csv \
    --base-tokens 10
```

CSV 格式（欄位名稱包含 "token" 或 "bonus" 即可）：
```csv
id,midterm_tokens
b12345678,5
b12345679,3
```

最終 token 數 = `base_tokens` + CSV 中的 bonus
- 範例：base=10, bonus=5 → 該學生獲得 15 個 token
- CSV 中未列出的學生使用 contest 預設值
- `--base-tokens` 預設為 10

**注意**：
- CSV 中有的學生：已在比賽中會更新 token，不在比賽中會新增
- CSV 中沒有的學生：已在比賽中會跳過，不在比賽中會新增
- 不使用 `--bonus-tokens` 時：所有已在比賽中的學生都會被跳過

## 匯出 token 使用統計

比賽結束後，如果想統計學生使用了多少額外 token，可使用：

```bash
python3 /srv/cms-src/scripts/csie/export_token_usage.py <contest_id> \
    ~/students/contest.yaml \
    --base-tokens 10 \
    --output token_usage.csv
```

輸出 CSV 格式：
```csv
id,bonus_tokens_used
b12345678,3
b12345679,0
```

統計邏輯：`bonus_tokens_used = max(0, 實際使用總數 - base_tokens)`

## 匯出 submission 資料

比賽結束後，如果想分析學生的 submission 和 token 使用習慣，可使用：

```bash
python3 /srv/cms-src/scripts/csie/export_submissions.py <contest_id> \
    --output submissions.csv
```

此腳本會匯出所有 official submission 的詳細資料：
```csv
submission_id,username,task_name,submission_timestamp,used_token,token_timestamp
123,b12345678,task1,2026-10-05T01:23:45,True,2026-10-05T01:23:50
124,b12345679,task2,2026-10-05T01:25:00,False,
```

注意：
- 只包含非 hidden、非 unrestricted participation 的學生
- 只包含 official submissions（不含 analysis mode 的提交）

## 腳本位置

| 腳本 | 路徑 |
|------|------|
| 產生帳密 | `/srv/cms-src/scripts/csie/generate_users.py` |
| 加入比賽 | `/srv/cms-src/scripts/csie/add_users_to_contest.py` |
| 匯出 token 統計 | `/srv/cms-src/scripts/csie/export_token_usage.py` |
| 匯出 submission 資料 | `/srv/cms-src/scripts/csie/export_submissions.py` |

## 重設密碼

若要批量更新所有學生密碼，重新執行上述「初次匯入」流程，並在 `cmsImportUser` 加上 `--update-password` 參數：

```bash
cmsImportUser -A --update-password ~/students/
```

已存在的使用者會更新密碼，新使用者則會被建立。

## 其他說明

- `contest.yaml` 和 `credentials.csv` 含敏感資料，已在 `.gitignore` 排除
