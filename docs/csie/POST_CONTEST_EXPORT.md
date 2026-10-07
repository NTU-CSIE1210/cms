# 賽後資料匯出

比賽結束後，可使用以下腳本匯出各種資料進行分析。

**注意**：所有匯出腳本都會自動跳過 hidden 和 unrestricted participation（如管理員測試帳號），且只匯出 official submissions（不含 analysis mode 的提交）。

## 匯出 token 使用統計

統計學生使用了多少額外 token：

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

## 匯出 submission 詳細資料（CSV）

匯出所有 submission 的 metadata，包含時間戳、是否使用 token 等資訊：

```bash
python3 /srv/cms-src/scripts/csie/export_submissions_csv.py <contest_id> \
    --output submissions.csv
```

輸出 CSV 格式：
```csv
submission_id,username,task_name,submission_timestamp,used_token,token_timestamp
123,b12345678,task1,2026-10-05T01:23:45,True,2026-10-05T01:23:50
124,b12345679,task2,2026-10-05T01:25:00,False,
```

## 匯出 submission 原始碼

匯出所有 submission 的原始碼檔案，便於進行程式碼分析：

```bash
python3 /srv/cms-src/scripts/csie/export_submissions_code.py <contest_id> \
    --output-dir submissions_code
```

檔名格式：`{submission_id}_{username}_{task}_{timestamp}_{Y/N}.{ext}`

範例輸出：
```
123_b12345678_task1_20261005_142330_Y.cpp  # 用了 token
124_b12345678_task2_20261005_143000_N.c    # 沒用 token
125_b12345679_task1_20261005_143500_N.cpp
```

**注意**：檔案 mtime 設為 submission timestamp，可用 `ls -t` 按提交時間排序。

常用分析方式：

```bash
# 按時間排序所有提交
ls -lt

# 找特定 submission ID
ls 123_*

# 某學生的所有提交
ls b12345678_*

# 所有人的 task1 提交
ls *_task1_*

# 所有用過 token 的提交
ls *_Y.*

# 所有沒用 token 的 C++ 程式
ls *_N.cpp

# 在所有 task1 中搜尋特定關鍵字
grep "malloc" *_task1_*

# 統計每個學生的提交次數
ls *.cpp | cut -d_ -f2 | sort | uniq -c
```

## 腳本位置

| 腳本 | 路徑 |
|------|------|
| 匯出 token 統計 | `/srv/cms-src/scripts/csie/export_token_usage.py` |
| 匯出 submission CSV | `/srv/cms-src/scripts/csie/export_submissions_csv.py` |
| 匯出 submission 原始碼 | `/srv/cms-src/scripts/csie/export_submissions_code.py` |
