#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Always run from the project root regardless of where this script is invoked.
# This script lives in the project root. cd to its directory regardless of CWD.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Define Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Helper functions for printing status
log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS] [✔]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN] [!]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR] [✘]${NC} $1"; }

# ASCII Art Header
show_header() {
    clear 2>/dev/null || true
    echo -e "${CYAN}${BOLD}"
    echo "=========================================================="
    echo "    KKYX RESOURCE ACQUISITION ENGINE - INITIALIZATION     "
    echo "=========================================================="
    echo -e "${NC}"
}

show_header

# ------------------------------------------------------------------------------
# Step 1: Detect Non-Interactive Mode
# ------------------------------------------------------------------------------
NON_INTERACTIVE=false
for arg in "$@"; do
    if [ "$arg" == "--non-interactive" ] || [ "$arg" == "-y" ]; then
        NON_INTERACTIVE=true
    fi
done

if [ ! -t 0 ]; then
    NON_INTERACTIVE=true
fi

if [ "$NON_INTERACTIVE" = true ]; then
    log_info "运行在非交互模式下。脚本将使用默认设置自动配置项目。"
fi

# ------------------------------------------------------------------------------
# Step 2: Check / Install Astral uv
# ------------------------------------------------------------------------------
log_info "1/5. 检测/安装 Python 包管理器: uv..."

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

UV_PATH=$(command -v uv 2>/dev/null || true)

if [ -n "$UV_PATH" ]; then
    log_success "检测到 uv 已经安装在: $UV_PATH (版本: $(uv --version))"
else
    log_warn "未检测到 uv。正在尝试为您自动安装 Astral uv..."
    if which curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        if which uv >/dev/null 2>&1; then
            log_success "uv 安装成功！当前版本: $(uv --version)"
        else
            log_error "uv 安装脚本已运行，但 'uv' 命令仍不可用。请尝试手动安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
            exit 1
        fi
    elif which pip3 >/dev/null 2>&1; then
        log_info "未检测到 curl，正在尝试使用 pip3 安装 uv..."
        pip3 install --user uv || pip3 install uv --break-system-packages
        if which uv >/dev/null 2>&1; then
            log_success "uv 通过 pip3 安装成功！当前版本: $(uv --version)"
        else
            log_error "uv 安装失败，请手动安装后重试。"
            exit 1
        fi
    else
        log_error "未找到 curl 且未找到 pip3，无法自动安装 uv。请手动安装 uv 后重试。"
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# Step 3: Setup Virtual Environment & Sync Dependencies
# ------------------------------------------------------------------------------
log_info "2/5. 正在同步 Python 虚拟环境与依赖项..."
if [ -f "pyproject.toml" ]; then
    uv sync
    log_success "Python 虚拟环境配置并同步成功！(.venv)"
else
    log_error "未找到 pyproject.toml 文件。请确保在项目根目录运行此脚本。"
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 4: Install Playwright Browsers
# ------------------------------------------------------------------------------
log_info "3/5. 正在安装 Playwright 浏览器内核 (Chrome/Chromium/etc.)..."
if uv run playwright install chromium --with-deps; then
    log_success "Playwright Chromium 浏览器及系统依赖安装/验证成功！"
else
    log_warn "带有系统依赖的 Playwright 安装失败，尝试进行常规浏览器安装..."
    if uv run playwright install chromium; then
        log_success "Playwright Chromium 浏览器安装成功！"
    else
        log_error "Playwright 浏览器安装失败。您可以尝试手动运行: uv run playwright install"
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# Step 5: Configure credentials (.config.toml)
# ------------------------------------------------------------------------------
log_info "4/5. 正在配置本地凭据 (.config.toml)..."

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

setup_config_interactive() {
    current_user=""
    current_pwd=""
    current_wp_url=""
    current_wp_user=""
    current_wp_pwd=""
    current_cdn_url=""

    if [ -f ".config.toml" ]; then
        read_current_creds
    fi

    echo -e "${YELLOW}>>> 开始交互式配置凭据 (直接回车保留括号内的当前值):${NC}"

    read -p "请输入 KKYX 用户名 [$current_user]: " new_user
    new_user=${new_user:-$current_user}

    read -s -p "请输入 KKYX 密码 (输入时不会显示) [$current_pwd]: " new_pwd
    new_pwd=${new_pwd:-$current_pwd}
    echo ""

    read -p "请输入 WordPress 网址 [$current_wp_url]: " new_wp_url
    new_wp_url=${new_wp_url:-$current_wp_url}

    read -p "请输入 WordPress 用户名 [$current_wp_user]: " new_wp_user
    new_wp_user=${new_wp_user:-$current_wp_user}

    read -s -p "请输入 WordPress 应用密码 (输入时不会显示) [$new_wp_pwd]: " new_wp_pwd
    new_wp_pwd=${new_wp_pwd:-$current_wp_pwd}
    echo ""

    read -p "请输入 CDN 资源根网址 [$current_cdn_url]: " new_cdn_url
    new_cdn_url=${new_cdn_url:-$current_cdn_url}

    write_creds
    log_success ".config.toml 凭据已更新完成！"
}

if [ "$NON_INTERACTIVE" = true ]; then
    if [ ! -f ".config.toml" ]; then
        new_user="your_username_here"
        new_pwd="your_password_here"
        new_wp_url=""
        new_wp_user=""
        new_wp_pwd=""
        new_cdn_url=""
        write_creds
        log_warn "在非交互模式下生成了占位 .config.toml。请在运行项目前编辑 .config.toml 填写正确的凭据。"
    else
        log_info "检测到已存在 .config.toml，非交互模式下跳过覆盖。"
    fi
else
    if [ -f ".config.toml" ]; then
        echo -e "${YELLOW}检测到已经存在 .config.toml。您要重新配置吗？${NC}"
        read -p "是否重新配置凭据？(y/N): " reconfig
        if [[ "$reconfig" =~ ^[Yy]$ ]]; then
            setup_config_interactive
        else
            log_info "保留现有的 .config.toml。"
        fi
    else
        setup_config_interactive
    fi
fi

# ------------------------------------------------------------------------------
# Step 6: Create Required Directories & Check DB
# ------------------------------------------------------------------------------
log_info "5/5. 初始化本地数据与运行目录..."

mkdir -p .data/db
mkdir -p .screenshot
mkdir -p .debug/screenshots
mkdir -p .debug/html
mkdir -p .debug/network

log_success "目录初始化成功！"

# Validate config load + DB path
log_info "验证配置加载与数据库路径..."
if uv run python3 -c "import config; print('Database config verified:', config.DB_FILE)" >/dev/null 2>&1; then
    log_success "系统配置与数据库连接加载成功！"
else
    log_warn "系统配置加载异常，请检查 .config.toml 中的必填项 (kkyx.username / kkyx.password)。"
fi

# ------------------------------------------------------------------------------
# Step 7: Fix Execution Permissions
# ------------------------------------------------------------------------------
chmod +x run 2>/dev/null || true
chmod +x run.sh 2>/dev/null || true
chmod +x init.sh 2>/dev/null || true
chmod +x scripts/verify_config.sh 2>/dev/null || true

# ------------------------------------------------------------------------------
# Final Initialization Status Summary
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}${BOLD}=========================================================="
echo "    [✔] KKYX RESOURCE ACQUISITION ENGINE 初始化完成!"
echo -e "==========================================================${NC}"
echo -e "\n接下来您可以运行以下命令启动管理台:"
echo -e "  ${CYAN}./run${NC}          # TUI 管理菜单"
echo -e "  ${CYAN}./run 2${NC}        # 直达菜单项 2 (自动化全流程)\n"

exit 0
