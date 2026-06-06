#!/bin/bash

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

# Configuration prompt
configure_credentials() {
    echo -e "\n${BLUE}[+] 交互式配置 .env 环境变量凭据...${NC}"
    
    # Read current if exists
    current_user=""
    current_pwd=""
    current_wp_url=""
    current_wp_user=""
    current_wp_pwd=""
    current_cdn_url="https://test-img-cdn.freessr.bid:8443/kkyx"
    current_config_path="config.json"
    
    if [ -f ".env" ]; then
        current_user=$(grep "^KKYX_USER=" .env | cut -d'=' -f2-)
        current_pwd=$(grep "^KKYX_PWD=" .env | cut -d'=' -f2-)
        current_wp_url=$(grep "^WP_BASE_URL=" .env | cut -d'=' -f2-)
        current_wp_user=$(grep "^WP_USERNAME=" .env | cut -d'=' -f2-)
        current_wp_pwd=$(grep "^TEST_KKYX_WP_APP_PASSWORD=" .env | cut -d'=' -f2-)
        current_cdn_url=$(grep "^CDN_BASE_URL=" .env | cut -d'=' -f2- || echo "https://test-img-cdn.freessr.bid:8443/kkyx")
        current_config_path=$(grep "^CONFIG_PATH=" .env | cut -d'=' -f2- || echo "config.json")
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

    read -p "请输入复杂配置文件路径 (JSON) [$current_config_path]: " new_config_path
    new_config_path=${new_config_path:-$current_config_path}
    
    # Write to .env
    cat <<EOF > .env
# ========================================
# Authentication (Required)
# ========================================
KKYX_USER=$new_user
KKYX_PWD=$new_pwd

# ========================================
# WordPress Sync (Optional)
# ========================================
WP_BASE_URL=$new_wp_url
WP_USERNAME=$new_wp_user
TEST_KKYX_WP_APP_PASSWORD=$new_wp_pwd

# ========================================
# CDN Configuration (Optional)
# ========================================
CDN_BASE_URL=$new_cdn_url

# ========================================
# Complex Configurations Path
# ========================================
CONFIG_PATH=$new_config_path
EOF

    echo -e "${GREEN}[✔] .env 配置文件已成功写入并更新！${NC}"
}

# Clear cache and logs
clear_cache() {
    echo -e "\n${RED}[!] 警告: 即将删除本地缓存、截图和日志文件。这不会清空数据库。${NC}"
    read -p "您确定要继续吗？(y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}[+] 清理中...${NC}"
        rm -rf .debug/screenshots/* .debug/html/* .debug/network/* 2>/dev/null
        rm -rf .screenshots/* 2>/dev/null
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
    echo -e "  ${GREEN}4.${NC} ⚙️  交互式修改并更新环境变量凭据 (.env)"
    echo -e "  ${GREEN}5.${NC} 🧹 清除缓存、历史调试 HTML 与系统截图"
    echo -e "  ${GREEN}6.${NC} 🌐 启动 Web 数据库监控控制台 (Flask)"
    echo -e "  ${RED}7.${NC} ❌ 退出脚本"
    echo -e "${CYAN}==================================================${NC}"
    
    read -p "请输入选项标号 [1-7]: " choice
    
    case $choice in
        1)
            echo -e "\n${GREEN}[*] 正在启动采集引擎流水线...${NC}"
            uv run python3 main.py
            echo -e "\n${BLUE}按下任意键返回主菜单...${NC}"
            read -n 1
            ;;
        2)
            echo -e "\n${GREEN}[*] 正在触发 Playwright 强制自动登录...${NC}"
            uv run python3 .auth/auto_login.py
            echo -e "\n${BLUE}按下任意键返回主菜单...${NC}"
            read -n 1
            ;;
        3)
            check_db_status
            echo -e "\n${BLUE}按下任意键返回主菜单...${NC}"
            read -n 1
            ;;
        4)
            configure_credentials
            echo -e "\n${BLUE}按下任意键返回主菜单...${NC}"
            read -n 1
            ;;
        5)
            clear_cache
            echo -e "\n${BLUE}按下任意键返回主菜单...${NC}"
            read -n 1
            ;;
        6)
            echo -e "\n${GREEN}[*] 正在启动 Web 数据库监控控制台...${NC}"
            echo -e "${YELLOW}控制台运行在: http://0.0.0.0:8050${NC}"
            echo -e "${YELLOW}默认账号密码与 KKYX 凭据相同 (可设置 WEB_VIEWER_USER/WEB_VIEWER_PASSWORD 独立凭据)${NC}"
            echo -e "${BLUE}按 Ctrl+C 可以停止服务。${NC}"
            uv run python3 web/app.py
            echo -e "\n${BLUE}按下任意键返回主菜单...${NC}"
            read -n 1
            ;;
        7)
            echo -e "\n${GREEN}感谢使用，再见！${NC}"
            exit 0
            ;;
        *)
            echo -e "\n${RED}[!] 无效的选项，请重新输入 1 到 7 的数字。${NC}"
            sleep 2
            ;;
    esac
done
