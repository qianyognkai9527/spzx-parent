#!/usr/bin/env bash
# 备份能不能恢复——把最近的 dump 还原进一个临时库，数完就删。
# 手动跑：bash scripts/verify-restore.sh [dump 路径]
#
# 为什么必须有这一步：只生成文件的备份从来没被证明能恢复。真出事那天才发现
# dump 少表、字符集错位、存储过程没带上，代价是不可逆的。
#
# 三条红线：
#  1) 临时库名不许以 db_ 开头（这台机器上真库都长这样），且必须 != 源库。
#     脚本开头就把这两条钉死，任何一条不满足直接退出，不执行任何 SQL。
#  2) 只 DROP 本脚本这次亲手建起来的那个库：建之前先确认它不存在，
#     建失败就立刻退出，绝不留"顺手删个同名库"的余地。
#  3) 备份产物本身不含 CREATE/DROP DATABASE（backup-db.sh 故意不带 --databases），
#     所以恢复到哪个库完全由这里的 -D 决定，不存在"管道进 mysql 就把生产库删了"。
set -uo pipefail

SRC_DB="${SPZX_BACKUP_DB:-db_spzx}"
SCRATCH="${SPZX_RESTORE_SCRATCH:-spzx_restore_probe}"
DIR="${SPZX_BACKUP_DIR:-$HOME/Backups/spzx-db}"
MYSQL=/usr/local/mysql/bin/mysql
DUMP="${1:-}"

die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ── 红线先钉死，再碰任何 SQL ──
case "$SCRATCH" in
  db_*|mysql|information_schema|performance_schema|sys) die "临时库名 '$SCRATCH' 撞真库/系统库，拒绝执行" ;;
esac
[ "$SCRATCH" = "$SRC_DB" ] && die "临时库名和源库同名，拒绝执行"

[ -n "$DUMP" ] || DUMP="$(ls -t "$DIR"/${SRC_DB}_*.sql.gz 2>/dev/null | head -1)"
[ -n "$DUMP" ] && [ -f "$DUMP" ] || die "找不到要验的 dump（先跑 scripts/backup-db.sh）"
gzip -t "$DUMP" || die "这份 gzip 本身是坏的：$DUMP"

CNF=""
for c in "${SPZX_MYSQL_CNF:-}" "$HOME/.spzx/db.cnf" "/tmp/spzx_my.cnf"; do
  [ -n "$c" ] && [ -f "$c" ] && CNF="$c" && break
done
[ -n "$CNF" ] || die "没有可用的 cnf，先 python3 scripts/mysql-cnf.py"

# mysqldump/mysqld 不认 cnf 里的 database= 键（实测 unknown variable），现场剔掉
DUMPCNF="$(mktemp -t spzx_restore_cnf)"; chmod 600 "$DUMPCNF"
grep -vE '^\s*database\s*=' "$CNF" > "$DUMPCNF"
q() { "$MYSQL" --defaults-extra-file="$DUMPCNF" -N -s -e "$1" 2>/dev/null; }
# q 吞掉所有错误：表不存在时返回空串。判据必须把空串当失败，否则"表整个丢了"会显示成
# "dump 行，真库 18 行"这种半句话——2026-10-08 红灯自证就是这么溜过去的。
cell() { local v; v="$(q "$1")"; if [ -z "$v" ]; then echo "__MISSING__"; else echo "$v"; fi; }
num() { case "$1" in (''|*[!0-9]*) echo -1;; (*) echo "$1";; esac; }

EXISTS="$(q "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='$SCRATCH';")"
[ "$EXISTS" = 0 ] || die "临时库 $SCRATCH 已经存在（谁建的？先人工确认再重跑），本次不动它"

TABLES_IN_DUMP="$(gunzip -c "$DUMP" | grep -c '^CREATE TABLE ')"
ROUTINES_IN_DUMP="$(gunzip -c "$DUMP" | grep -cE '^CREATE (PROCEDURE|FUNCTION) ')"
EVENTS_IN_DUMP="$(gunzip -c "$DUMP" | grep -c '^CREATE EVENT ')"
echo "待验：$DUMP"
echo "  dump 里：$TABLES_IN_DUMP 张表、$ROUTINES_IN_DUMP 个存储过程/函数、$EVENTS_IN_DUMP 个事件"

echo "  建临时库 $SCRATCH 并还原…"
q "CREATE DATABASE \`$SCRATCH\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;" || die "建临时库失败"
CREATED=1
cleanup() {
  [ "${CREATED:-0}" = 1 ] || return 0
  q "DROP DATABASE \`$SCRATCH\`;" || echo "!! 临时库 $SCRATCH 没删掉，手工处理：DROP DATABASE \`$SCRATCH\`;"
}
trap cleanup EXIT

if ! gunzip -c "$DUMP" | "$MYSQL" --defaults-extra-file="$DUMPCNF" --default-character-set=utf8mb4 "$SCRATCH"; then
  die "还原过程报错——这份备份不能用"
fi

fail=0
# 参照物必须是**真库的表清单**，不是 dump 自己声明的条数。
# 上一版拿 dump 的 CREATE TABLE 数当基准，等于自己跟自己对账：
# 2026-10-08 用一份被删掉 41 张表的 dump 试，它照样报"表数一致 71/71，可以恢复"。
LIVE_TABLES="$(q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$SRC_DB' AND table_type='BASE TABLE';")"
GOT="$(q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$SCRATCH' AND table_type='BASE TABLE';")"
if [ "$GOT" != "$LIVE_TABLES" ]; then echo "  ✗ 表数不符：还原后 $GOT 张，真库有 $LIVE_TABLES 张"; fail=1
else echo "  ok 表数与真库一致：$GOT/$LIVE_TABLES"; fi

# 清单逐个比（数目相同也可能是少 A 多 B）
MISSING="$(q "SELECT GROUP_CONCAT(t.table_name) FROM information_schema.tables t
  WHERE t.table_schema='$SRC_DB' AND t.table_type='BASE TABLE'
    AND NOT EXISTS (SELECT 1 FROM information_schema.tables s
                    WHERE s.table_schema='$SCRATCH' AND s.table_name=t.table_name);")"
if [ -n "${MISSING:-}" ] && [ "$MISSING" != "NULL" ]; then
  echo "  ✗ 还原后缺这些表：$MISSING"; fail=1
fi
if [ "$GOT" != "$TABLES_IN_DUMP" ]; then
  echo "  ·  dump 里写了 $TABLES_IN_DUMP 条 CREATE TABLE，还原后 $GOT 张（有表被重建过，正常）"
fi

GOTR="$(q "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='$SCRATCH';")"
GOTE="$(q "SELECT COUNT(*) FROM information_schema.events WHERE event_schema='$SCRATCH';")"
if [ "$GOTR" != "$ROUTINES_IN_DUMP" ]; then echo "  ✗ 存储过程/函数：还原后 ${GOTR}，dump 声明 $ROUTINES_IN_DUMP"; fail=1
else echo "  ok 存储过程/函数：$GOTR 个"; fi
if [ "$GOTE" != "$EVENTS_IN_DUMP" ]; then echo "  ✗ 事件：还原后 ${GOTE}，dump 声明 ${EVENTS_IN_DUMP}（事件丢了，恢复出来的库不会自己跑定时作业）"; fail=1
else echo "  ok 事件：$GOTE 个"; fi

# 中文没二次编码才算真的能用（历史上栽过一次：dump 不带 utf8mb4 → 恢复出来全是问号）
CJK="$(q "SELECT COUNT(*) FROM \`$SCRATCH\`.ingest_dataset WHERE name LIKE '%采集%' OR name LIKE '%推广%';")"
[ "${CJK:-0}" != 0 ] && echo "  ok 中文可读：ingest_dataset 里按中文关键词命中 $CJK 行" \
  || { echo "  ✗ ingest_dataset 里查不到中文关键词 → 字符集或内容有问题"; fail=1; }

# 抽几张关键表跟真库当场比：差很多 = 没备全；差几行且真库更多 = 备份之后新写的，正常漂移
for t in platform_product ingest_batch ingest_dataset sync_alert promo_cost_daily promo_plan; do
  a="$(num "$(q "SELECT COUNT(*) FROM \`$SRC_DB\`.\`$t\`;")")"
  b="$(num "$(cell "SELECT COUNT(*) FROM \`$SCRATCH\`.\`$t\`;")")"
  if [ "$b" = "-1" ] || [ "$a" = "-1" ]; then
    echo "  ✗ $t 在两边不是都能查到（真库 $a / 还原 ${b}）——表丢了或改名了"; fail=1
  elif [ "$a" = "$b" ]; then echo "  ok ${t}：$b 行（与真库一致）"
  elif [ "$b" -gt "$a" ]; then echo "  ✗ ${t}：还原出 $b 行比真库 $a 行还多 → 还原过程或基准有问题"; fail=1
  else echo "  ·  ${t}：dump $b 行，真库现在 $a 行（差 $((a - b))，备份之后新写的）"; fi
done

[ "$fail" = 0 ] || die "还原校验有不合格项（上面打 ✗ 的）"
echo "结论：这份备份可以恢复。"
exit 0
