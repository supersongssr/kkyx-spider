#!/bin/bash

# Always run from the project root regardless of where this script is invoked.
# This script lives in the project root. cd to its directory regardless of CWD.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Define Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ASCII Art Header
show_header() {
    clear
    echo -e "${CYAN}${BOLD}"
    echo "=================================================="
    echo "    KKYX RESOURCE ACQUISITION ENGINE MANAGER      "
    echo "=================================================="
    echo -e "${NC}"
}

# Database status query
check_db_status() {
    echo -e "\n${BLUE}[+] 查询 SQLite 本地数据库状态...${NC}"
    if [ ! -f ".data/db/kkyx_spider.db" ]; then
        echo -e "${YELLOW}[!] 数据库尚未初始化。运行流水线将自动创建并初始化数据库。${NC}"
        return
    fi
    uv run python3 -c "
import sqlite3
conn = sqlite3.connect('.data/db/kkyx_spider.db')
c = conn.cursor()
tables = [t[0] for t in c.execute(\"select name from sqlite_master where type='table'\").fetchall()]
print('\n📊 数据表记录统计:')
for t in tables:
    count = c.execute(f'select count(*) from {t}').fetchone()[0]
    print(f' ┣━ {t}: {count} 条记录')

if 'games' in tables:
    print('\n🎮 游戏采集状态分布:')
    statuses = {0: '待处理 (PENDING)', 1: '已完成 (COMPLETED)', 2: '需更新 (NEEDS_UPDATE)', 3: '死信 (DEAD_LETTER)'}
    for status_val, status_name in statuses.items():
        count = c.execute('select count(*) from games where crawl_status = ?', (status_val,)).fetchone()[0]
        print(f' ┣━ {status_name}: {count} 个')
"
}

# Read current credentials from .config.toml (robust via shlex-quoted eval)
read_current_creds() {
    eval "$(uv run python3 -c '
import tomllib, shlex
try:
    d = tomllib.load(open(".config.toml", "rb"))
except Exception:
    d = {}
k = d.get("kkyx", {})
w = d.get("wordpress", {})
c = d.get("cdn", {})
def q(v):
    return shlex.quote(str(v) if v is not None else "")
print("current_user=" + q(k.get("username", "")))
print("current_pwd=" + q(k.get("password", "")))
print("current_wp_url=" + q(w.get("base_url", "")))
print("current_wp_user=" + q(w.get("username", "")))
print("current_wp_pwd=" + q(w.get("app_password", "")))
print("current_cdn_url=" + q(c.get("base_url", "")))
' 2>/dev/null)"
}

# Deep-merge credential values into .config.toml, preserving other sections.
# Values are passed via environment variables to avoid quoting issues.
write_creds() {
    NEW_KKYX_USER="$new_user" \
    NEW_KKYX_PWD="$new_pwd" \
    NEW_WP_URL="$new_wp_url" \
    NEW_WP_USER="$new_wp_user" \
    NEW_WP_PWD="$new_wp_pwd" \
    NEW_CDN_URL="$new_cdn_url" \
    uv run python3 -c '
import os, tomllib
from pathlib import Path

p = Path(".config.toml")
data = {}
if p.exists():
    with open(p, "rb") as f:
        data = tomllib.load(f)

new = {
    "kkyx": {"username": os.environ["NEW_KKYX_USER"], "password": os.environ["NEW_KKYX_PWD"]},
    "wordpress": {"base_url": os.environ["NEW_WP_URL"], "username": os.environ["NEW_WP_USER"], "app_password": os.environ["NEW_WP_PWD"]},
    "cdn": {"base_url": os.environ["NEW_CDN_URL"]},
}

def merge(a, b):
    for k, v in b.items():
        if k in a and isinstance(a[k], dict) and isinstance(v, dict):
            merge(a[k], v)
        else:
            a[k] = v

merge(data, new)

def _fmt(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, int): return str(v)
    if isinstance(v, float): return repr(v)
    if isinstance(v, str): return "\"" + v.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    if isinstance(v, list): return "[" + ", ".join(_fmt(x) for x in v) + "]"
    raise ValueError(f"unsupported type {type(v)}")

def _emit(prefix, table, out):
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    subs    = {k: v for k, v in table.items() if isinstance(v, dict)}
    if scalars:
        if prefix: out.append(f"[{prefix}]")
        for k, v in scalars.items(): out.append(f"{k} = {_fmt(v)}")
        out.append("")
    for name, sub in subs.items():
        _emit(f"{prefix}.{name}" if prefix else name, sub, out)

def dumps(d):
    out = []
    _emit("", d, out)
    return "\n".join(out).rstrip() + "\n"

p.write_text(dumps(data), encoding="utf-8")
'
}

# Configuration prompt
configure_credentials() {
    echo -e "\n${BLUE}[+] 交互式配置 .config.toml 凭据...${NC}"

    # Defaults
    current_user=""
    current_pwd=""
    current_wp_url=""
    current_wp_user=""
    current_wp_pwd=""
    current_cdn_url=""

    # Read current values from .config.toml if it exists
    if [ -f ".config.toml" ]; then
        read_current_creds
    fi

    echo -e "${YELLOW}直接按回车将保留当前值。${NC}"

    read -p "请输入 KKYX 用户名 [$current_user]: " new_user
    new_user=${new_user:-$current_user}

    read -s -p "请输入 KKYX 密码 [$current_pwd]: " new_pwd
    new_pwd=${new_pwd:-$current_pwd}
    echo "" # newline after silent read

    read -p "请输入 WordPress 网址 (如 http://example.com) [$current_wp_url]: " new_wp_url
    new_wp_url=${new_wp_url:-$current_wp_url}

    read -p "请输入 WordPress 用户名 [$current_wp_user]: " new_wp_user
    new_wp_user=${new_wp_user:-$current_wp_user}

    read -s -p "请输入 WordPress 应用密码 [$current_wp_pwd]: " new_wp_pwd
    new_wp_pwd=${new_wp_pwd:-$current_wp_pwd}
    echo "" # newline after silent read

    read -p "请输入 CDN 资源根网址 [$current_cdn_url]: " new_cdn_url
    new_cdn_url=${new_cdn_url:-$current_cdn_url}

    write_creds
    echo -e "${GREEN}[✔] .config.toml 凭据已成功写入并更新！${NC}"
}

# Clear cache and logs
clear_cache() {
    echo -e "\n${RED}[!] 警告: 即将删除本地缓存、截图和日志文件。这不会清空数据库。${NC}"
    read -p "您确定要继续吗？(y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}[+] 清理中...${NC}"
        rm -rf .debug/screenshots/* .debug/html/* .debug/network/* 2>/dev/null
        rm -rf .screenshots/* 2>/dev/null
        rm -rf .screenshot/* 2>/dev/null
        echo -e "${GREEN}[✔] 缓存和截图目录已成功清理！${NC}"
    else
        echo -e "${YELLOW}[-] 已取消清理。${NC}"
    fi
}

# Main Loop
while true; do
    show_header
    echo -e "${BOLD}请选择操作:${NC}"
    echo -e "  ${GREEN}1.${NC} 🚀 ${BOLD}一键启动采集与同步流水线 (main.py)${NC}"
    echo -e "  ${GREEN}2.${NC} 🔑 强制执行自动登录刷新会话 (auto_login.py)"
    echo -e "  ${GREEN}3.${NC} 📊 查看本地数据库状态统计"
    echo -e "  ${GREEN}4.${NC} ⚙️  交互式修改并更新凭据 (.config.toml)"
    echo -e "  ${GREEN}5.${NC} 🧹 清除缓存、历史调试 HTML 与系统截图"
    echo -e "  ${GREEN}6.${NC} 🌐 启动 Web 数据库监控控制台 (Flask)"
    echo -e "  ${RED}7.${NC} ❌ 退出脚本"
    echo -e "${CYAN}==================================================${NC}"

    read -p "请输入选项标号 [1-7]: " choice

    case $choice in
        1) uv run python3 main.py ;;
        2) uv run python3 .auth/auto_login.py ;;
        3) check_db_status ;;
        4) configure_credentials ;;
        5) clear_cache ;;
        6) uv run python3 web/app.py ;;
        7)
            echo -e "\n${GREEN}感谢使用，再见！${NC}"
            exit 0
            ;;
        *)
            echo -e "\n${RED}[!] 无效的选项，请重新输入 1 到 7 的数字。${NC}"
            sleep 2
            continue
            ;;
    esac
    # 选项执行完毕后直接退出，让被调用脚本的输出原样保留在终端，
    # 不再返回菜单（避免清屏覆盖错误日志）。
    exit $?
done
