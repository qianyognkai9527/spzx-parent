#!/usr/bin/env bash
# 本机 MySQL 每日备份：db_spzx 全量 mysqldump + gzip 到 ~/Backups/spzx-db/。
# 由 LaunchAgent com.spzx.db-backup 每天 04:10 调用，也可以手动跑。
#
# 四条判据，改之前先读：
#  1) 备份不等于"文件生成了"。判据是 gzip -t 通过 + dump 里有 "Dump completed" 收尾行 +
#     dump 里的 CREATE TABLE 条数 == 库里 information_schema 的表数。
#     少一条就是这次备份不可信，退出码非 0。
#  2) 口令一律走 extra-file，绝不进命令行（ps 里能看见）。mysqldump 不认 cnf 里的
#     `database=` 键（实测 unknown variable），所以这里从现成的 cnf 现场生成一份
#     只留 host/port/user/password/charset 的 dump 专用文件，600 权限，用完删。
#  3) 备份落在仓库外（~/Backups）。仓库里塞 sql.gz 等于把数据提交进 git——
#     2026-10-03 那次 -A 吞了 741MB 图片就是这么来的。
#  4) --single-transaction：InnoDB 一致性快照，不锁表。这台机器 04:10 前后有别的采集在跑，
#     用 --lock-tables 会把它们卡在备份里。
set -uo pipefail

DB="${SPZX_BACKUP_DB:-db_spzx}"
DEST="${SPZX_BACKUP_DIR:-$HOME/Backups/spzx-db}"
KEEP_DAYS="${SPZX_BACKUP_KEEP_DAYS:-7}"
MYSQL=/usr/local/mysql/bin/mysql
MYSQLDUMP=/usr/local/mysql/bin/mysqldump
REPO="$HOME/ideaProject/spzx-parent"
LOG="$DEST/backup.log"

die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; echo "$(date '+%F %T') FAIL $*" >> "$LOG" 2>/dev/null || true; exit 1; }
note() { printf '%s\n' "$*"; echo "$(date '+%F %T') $*" >> "$LOG"; }

[ -x "$MYSQLDUMP" ] || die "找不到 $MYSQLDUMP"

# ── 凭据：复用仓库外那两份 600 文件，缺了就按既有约定重建 ──
CNF=""
for c in "${SPZX_MYSQL_CNF:-}" "$HOME/.spzx/db.cnf" "/tmp/spzx_my.cnf"; do
  [ -n "$c" ] && [ -f "$c" ] && CNF="$c" && break
done
if [ -z "$CNF" ]; then
  note "两份 cnf 都不在（/tmp 被清了？），用 scripts/mysql-cnf.py 重建"
  ( cd "$REPO" && python3 scripts/mysql-cnf.py >/dev/null 2>&1 ) || die "重建 cnf 失败"
  CNF="$HOME/.spzx/db.cnf"
fi

DUMPCNF="$(mktemp -t spzx_dump_cnf)"
chmod 600 "$DUMPCNF"
trap 'rm -f "$DUMPCNF"' EXIT
# 丢掉 database= 这行：mysqldump 带它会直接报错
grep -vE '^\s*database\s*=' "$CNF" > "$DUMPCNF"

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/${DB}_$STAMP.sql.gz"

# ── 库里到底该有多少张表（备份可信度的基准）──
EXPECT_TABLES="$("$MYSQL" --defaults-extra-file="$DUMPCNF" -N -s -e \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB' AND table_type='BASE TABLE';" 2>/dev/null)"
[[ "$EXPECT_TABLES" =~ ^[0-9]+$ ]] || die "查不到 $DB 的表数，连接或权限有问题（cnf=$CNF）"

note "开始备份 $DB（$EXPECT_TABLES 张表）→ $OUT"
# routines/triggers/events 都要带上：少了事件=少了每晚那批定时作业的定义，
# 真出事时恢复出来的库不会自己跑采集，那是个"看起来恢复了"的空壳。
#
# 故意不带 --databases：那份产物里会写 `DROP DATABASE IF EXISTS \`db_spzx\``。
# 这个机器上跑命令的不止人（还有各种 agent），一份"顺手管道进 mysql 就把生产库删了"的文件
# 不该当天顶备份。只导表体之后，恢复到哪个库由 mysql 命令自己指定（见 verify-restore.sh）。
if ! "$MYSQLDUMP" --defaults-extra-file="$DUMPCNF" \
      --single-transaction --routines --triggers --events \
      --default-character-set=utf8mb4 --set-gtid-purged=OFF \
      "$DB" 2>"$DEST/.last_err" | gzip -9 > "$OUT"; then
  note "mysqldump 非 0 退出：$(tail -3 "$DEST/.last_err" 2>/dev/null)"
  rm -f "$OUT"; die "mysqldump 失败，看 $DEST/.last_err"
fi
[ -s "$OUT" ] || { rm -f "$OUT"; die "dump 出来是空文件"; }

# ── 三条完整性判据 ──
gzip -t "$OUT" || die "gzip 校验不过：$OUT（写坏了或磁盘满）"
# 先解压再取尾巴：对 .gz 直接 tail -c 拿到的是半个压缩流，gunzip 必然失败
# （第一版就是这么写的，把一次完好的小备份判成了"中途被截断"）
gunzip -c "$OUT" | tail -c 2048 | grep -q "Dump completed" || die "dump 没有收尾行 → 中途被截断"
GOT_TABLES="$(gunzip -c "$OUT" | grep -c '^CREATE TABLE ')"
if [ "$GOT_TABLES" != "$EXPECT_TABLES" ]; then
  die "表数对不上：dump 里有 $GOT_TABLES 张 CREATE TABLE，库里有 $EXPECT_TABLES 张 → 这次备份不可用"
fi

SIZE="$(du -h "$OUT" | cut -f1 | tr -d ' ')"
note "完成：$OUT（$SIZE，$GOT_TABLES/$EXPECT_TABLES 张表）"

# ── 保留策略：只删本脚本命名规则的文件，且必须满 KEEP_DAYS 天 ──
DELETED=0
while IFS= read -r old; do
  rm -f "$old" && DELETED=$((DELETED + 1))
done < <(find "$DEST" -maxdepth 1 -name "${DB}_*.sql.gz" -mtime +"$KEEP_DAYS" -print)
[ "$DELETED" != 0 ] && note "按 ${KEEP_DAYS} 天保留策略清掉 $DELETED 份旧备份"
KEEP_WK="${SPZX_BACKUP_KEEP_WEEKS:-8}"
DELETED_WK=0
while IFS= read -r old; do
  rm -f "$old" && DELETED_WK=$((DELETED_WK + 1))
done < <(find "$DEST/weekly" -maxdepth 1 -name "${DB}_*.sql.gz" -mtime +"$((KEEP_WK * 7))" -print 2>/dev/null)
[ "$DELETED_WK" != 0 ] && note "周备份目录清掉 $DELETED_WK 份（保留 $KEEP_WK 周）"

# 每周留一份：每天一份只防"最近 N 天改坏了"，月度回看要靠周日那份
if [ ! -e "$DEST/weekly/${DB}_$(date +%Y-W%V).link" ]; then
  mkdir -p "$DEST/weekly"
  cp "$OUT" "$DEST/weekly/${DB}_$(date +%Y-W%V).sql.gz"
  : > "$DEST/weekly/${DB}_$(date +%Y-W%V).link"
  note "本周份已归档到 weekly/$(basename "$DEST")/${DB}_$(date +%Y-W%V).sql.gz"
fi

DISK_FREE="$(df -m "$DEST" | awk 'NR==2{print $4}')"
[ "$DISK_FREE" -lt 1024 ] && note "!! 磁盘剩余只有 ${DISK_FREE}MB，备份先续着，但这两天得清一次盘"
note "目录合计 $(du -sh "$DEST" | cut -f1 | tr -d ' ')，磁盘剩余 $((DISK_FREE / 1024))GB"
exit 0
