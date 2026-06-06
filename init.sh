#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
# but let us handle individual failures gracefully where needed.
set -e

# Define Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Helper functions for printing status
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS] [✔]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN] [!]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR] [✘]${NC} $1"
}

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
log_info "1/6. 检测/安装 Python 包管理器: uv..."

# Add local bin to path just in case uv was installed recently
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

UV_PATH=$(command -v uv 2>/dev/null || true)

if [ -n "$UV_PATH" ]; then
    log_success "检测到 uv 已经安装在: $UV_PATH (版本: $(uv --version))"
else
    log_warn "未检测到 uv。正在尝试为您自动安装 Astral uv..."
    if which curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Reload path
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
log_info "2/6. 正在同步 Python 虚拟环境与依赖项..."
if [ -f "pyproject.toml" ]; then
    # uv sync will create the virtual environment and sync dependencies
    uv sync
    log_success "Python 虚拟环境配置并同步成功！(.venv)"
else
    log_error "未找到 pyproject.toml 文件。请确保在项目根目录运行此脚本。"
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 4: Install Playwright Browsers
# ------------------------------------------------------------------------------
log_info "3/6. 正在安装 Playwright 浏览器内核 (Chrome/Chromium/etc.)..."
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
# Step 5: Configure Environment Variables (.env)
# ------------------------------------------------------------------------------
log_info "4/6. 正在配置环境变量 (.env)..."

setup_env_interactive() {
    # Read current if exists
    current_user=""
    current_pwd=""
    current_wp_url="http://localhost:8080"
    current_wp_user="test-kkyx"
    current_wp_pwd=""
    current_cdn_url="https://test-img-cdn.freessr.bid:8443/kkyx"
    current_config_path="config.json"
    
    if [ -f ".env" ]; then
        current_user=$(grep "^KKYX_USER=" .env | cut -d'=' -f2-)
        current_pwd=$(grep "^KKYX_PWD=" .env | cut -d'=' -f2-)
        current_wp_url=$(grep "^WP_BASE_URL=" .env | cut -d'=' -f2- || echo "http://localhost:8080")
        current_wp_user=$(grep "^WP_USERNAME=" .env | cut -d'=' -f2- || echo "test-kkyx")
        current_wp_pwd=$(grep "^TEST_KKYX_WP_APP_PASSWORD=" .env | cut -d'=' -f2-)
        current_cdn_url=$(grep "^CDN_BASE_URL=" .env | cut -d'=' -f2- || echo "https://test-img-cdn.freessr.bid:8443/kkyx")
        current_config_path=$(grep "^CONFIG_PATH=" .env | cut -d'=' -f2- || echo "config.json")
    fi

    echo -e "${YELLOW}>>> 开始交互式配置环境变量 (直接回车保留括号内的默认/当前值):${NC}"
    
    read -p "请输入 KKYX 用户名 [$current_user]: " new_user
    new_user=${new_user:-$current_user}
    
    read -s -p "请输入 KKYX 密码 (输入时不会显示) [$current_pwd]: " new_pwd
    new_pwd=${new_pwd:-$current_pwd}
    echo "" # newline after hidden input
    
    read -p "请输入 WordPress 网址 [$current_wp_url]: " new_wp_url
    new_wp_url=${new_wp_url:-$current_wp_url}
    
    read -p "请输入 WordPress 用户名 [$current_wp_user]: " new_wp_user
    new_wp_user=${new_wp_user:-$current_wp_user}
    
    read -s -p "请输入 WordPress 应用密码 (输入时不会显示) [$current_wp_pwd]: " new_wp_pwd
    new_wp_pwd=${new_wp_pwd:-$current_wp_pwd}
    echo "" # newline
    
    read -p "请输入 CDN 资源根网址 [$current_cdn_url]: " new_cdn_url
    new_cdn_url=${new_cdn_url:-$current_cdn_url}

    read -p "请输入复杂配置文件路径 (JSON) [$current_config_path]: " new_config_path
    new_config_path=${new_config_path:-$current_config_path}

    # Write variables to .env
    cat <<EOF > .env
# ==============================================================================
# KKYX Spider Environment Configuration
# Generated by init.sh on $(date)
# ==============================================================================

# 1. KKYX Target Site Credentials
KKYX_USER=$new_user
KKYX_PWD=$new_pwd

# 2. WordPress Sync Configuration (Optional)
WP_BASE_URL=$new_wp_url
WP_USERNAME=$new_wp_user
TEST_KKYX_WP_APP_PASSWORD=$new_wp_pwd

# 3. CDN Configuration (Optional)
CDN_BASE_URL=$new_cdn_url

# 4. Complex Configurations Path
CONFIG_PATH=$new_config_path
EOF
    log_success ".env 配置文件已更新完成！"
}

if [ "$NON_INTERACTIVE" = true ]; then
    if [ ! -f ".env" ]; then
        cat <<EOF > .env
# ==============================================================================
# KKYX Spider Environment Configuration (Default Placeholder)
# ==============================================================================

# 1. KKYX Target Site Credentials
KKYX_USER=your_username_here
KKYX_PWD=your_password_here

# 2. WordPress Sync Configuration (Optional)
WP_BASE_URL=http://localhost:8080
WP_USERNAME=test-kkyx
TEST_KKYX_WP_APP_PASSWORD=

# 3. CDN Configuration (Optional)
CDN_BASE_URL=https://test-img-cdn.freessr.bid:8443/kkyx

# 4. Complex Configurations Path
CONFIG_PATH=config.json
EOF
        log_warn "在非交互模式下生成了默认 .env 配置文件。请在运行项目前编辑 .env 填写正确的凭据。"
    else
        log_info "检测到已存在 .env 配置文件，非交互模式下跳过覆盖。"
    fi
else
    if [ -f ".env" ]; then
        echo -e "${YELLOW}检测到已经存在 .env 配置文件。您要重新配置吗？${NC}"
        read -p "是否重新配置环境变量？(y/N): " reconfig
        if [[ "$reconfig" =~ ^[Yy]$ ]]; then
            setup_env_interactive
        else
            log_info "保留现有的 .env 配置文件。"
        fi
    else
        setup_env_interactive
    fi
fi

# ------------------------------------------------------------------------------
# Step 6: Create Required Directories & Check DB
# ------------------------------------------------------------------------------
log_info "5/6. 初始化本地数据与运行目录..."

mkdir -p .data/db
mkdir -p .screenshots
mkdir -p .debug/screenshots
mkdir -p .debug/html
mkdir -p .debug/network

log_success "目录初始化成功！"

# Check if SQLite DB should be created/validated
if [ -f "config.py" ]; then
    log_info "验证 SQLite 本地数据库初始化..."
    # Quick Python check to make sure DB can be opened and config loads
    if uv run python3 -c "import config; print('Database config verified:', config.DB_FILE)" >/dev/null 2>&1; then
        log_success "系统配置与数据库连接加载成功！"
    else
        log_warn "系统配置加载或数据库初始化测试异常，请检查配置参数。"
    fi
fi

# ------------------------------------------------------------------------------
# Step 7: Fix Execution Permissions
# ------------------------------------------------------------------------------
log_info "6/6. 设置脚本的可执行权限..."
chmod +x run.sh || true
chmod +x init.sh || true
log_success "脚本权限设置成功！"

# ------------------------------------------------------------------------------
# Final Initialization Status Summary
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}${BOLD}=========================================================="
echo "    [✔] KKYX RESOURCE ACQUISITION ENGINE 初始化完成!"
echo -e "==========================================================${NC}"
echo -e "\n接下来您可以运行以下命令启动管理台:"
echo -e "  ${CYAN}./run.sh${NC}\n"

exit 0
