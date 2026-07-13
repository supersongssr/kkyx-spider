#!/bin/bash
# KKYX Spider 配置系统验证脚本

echo "=========================================="
echo "  KKYX Spider 配置系统验证"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# 检查函数
check_pass() {
    echo -e "${GREEN}✅${NC} $1"
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}❌${NC} $1"
    ((FAIL_COUNT++))
}

check_warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

echo "=== 1. 文件结构检查 ==="
echo ""

# 检查主要文件
[ -f "config.py" ] && check_pass "config.py 存在" || check_fail "config.py 缺失"
[ -f ".env" ] && check_pass ".env 存在" || check_fail ".env 缺失"
[ -f ".gitignore" ] && check_pass ".gitignore 存在" || check_fail ".gitignore 缺失"

# 检查文档文件
[ -f "docs/CONFIGURATION.md" ] && check_pass "docs/CONFIGURATION.md 存在" || check_warn "docs/CONFIGURATION.md 缺失"
[ -f "docs/MIGRATION.md" ] && check_pass "docs/MIGRATION.md 存在" || check_warn "docs/MIGRATION.md 缺失"
[ -f "docs/CONFIG_QUICK_REFERENCE.txt" ] && check_pass "快速参考卡存在" || check_warn "快速参考卡缺失"

# 检查可选文件
[ -f ".config.py" ] && check_pass ".config.py 存在 (本地配置)" || check_warn ".config.py 不存在"

echo ""
echo "=== 2. 旧文件清理检查 ==="
echo ""

# 检查旧配置文件是否已删除
[ ! -f "config.test.json" ] && check_pass "config.test.json 已删除" || check_fail "config.test.json 仍存在"
[ ! -f "config.json" ] && check_pass "config.json 已删除" || check_fail "config.json 仍存在"
[ ! -d "data" ] && check_pass "旧 data/ 目录已删除" || check_fail "旧 data/ 目录仍存在"

echo ""
echo "=== 3. .gitignore 检查 ==="
echo ""

# 检查重要条目是否在 .gitignore 中
grep -q "\.env" .gitignore && check_pass ".env 在 .gitignore 中" || check_fail ".env 不在 .gitignore 中"
grep -q "\.config\.py" .gitignore && check_pass ".config.py 在 .gitignore 中" || check_fail ".config.py 不在 .gitignore 中"
grep -q "\.data/" .gitignore && check_pass ".data/ 在 .gitignore 中" || check_fail ".data/ 不在 .gitignore 中"
grep -q "\.screenshot/" .gitignore && check_pass ".screenshot/ 在 .gitignore 中" || check_fail ".screenshot/ 不在 .gitignore 中"
grep -q "\.auth/" .gitignore && check_pass ".auth/ 在 .gitignore 中" || check_fail ".auth/ 不在 .gitignore 中"

echo ""
echo "=== 4. 目录结构检查 ==="
echo ""

# 检查新目录结构
[ -d ".data" ] && check_pass ".data/ 目录存在" || check_warn ".data/ 目录不存在（首次运行时创建）"
[ -d ".data/storage" ] && check_pass ".data/storage/ 目录存在" || check_warn ".data/storage/ 目录不存在（首次运行时创建）"
[ -d ".screenshot" ] && check_pass ".screenshot/ 目录存在" || check_warn ".screenshot/ 目录不存在（首次运行时创建）"

echo ""
echo "=== 5. 配置文件内容检查 ==="
echo ""

# 检查 .env 文件内容
grep -q "KKYX_USER=" .env && check_pass ".env 包含 KKYX_USER" || check_fail ".env 缺少 KKYX_USER"
grep -q "KKYX_PWD=" .env && check_pass ".env 包含 KKYX_PWD" || check_fail ".env 缺少 KKYX_PWD"
! grep -q "CONFIG_PATH=" .env && check_pass ".env 不包含 CONFIG_PATH" || check_fail ".env 仍包含 CONFIG_PATH"
grep -q "WP_APP_PASSWORD" .env && check_pass ".env 使用新的 WP_APP_PASSWORD" || check_warn ".env 可能仍使用旧的变量名"

# 检查 config.py 内容
grep -q "\.config\.py" config.py && check_pass "config.py 支持 .config.py" || check_fail "config.py 不支持 .config.py"
grep -q "STORAGE_DIR" config.py && check_pass "config.py 包含 STORAGE_DIR" || check_fail "config.py 缺少 STORAGE_DIR"

echo ""
echo "=== 6. 代码路径更新检查 ==="
echo ""

# 检查代码文件是否更新了路径引用
! grep -q "data/storage" core/html_image_processor.py && check_pass "html_image_processor.py 已更新路径" || check_fail "html_image_processor.py 仍有旧路径"
! grep -q "\.screenshots" core/auth.py || grep -q "screenshots" core/auth.py | grep -q "\.screenshots" && check_pass "auth.py 已更新路径" || check_warn "auth.py 可能有旧路径引用"

echo ""
echo "=== 7. Python 语法检查 ==="
echo ""

# 检查 Python 文件语法
python3 -m py_compile config.py 2>/dev/null && check_pass "config.py 语法正确" || check_fail "config.py 语法错误"
if [ -f ".config.py" ]; then
    python3 -m py_compile .config.py 2>/dev/null && check_pass ".config.py 语法正确" || check_fail ".config.py 语法错误"
fi

echo ""
echo "=========================================="
echo "  验证结果汇总"
echo "=========================================="
echo -e "${GREEN}通过: $PASS_COUNT${NC}"
echo -e "${RED}失败: $FAIL_COUNT${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}🎉 所有检查通过！配置系统重构成功。${NC}"
    exit 0
else
    echo -e "${RED}⚠️  发现 $FAIL_COUNT 个问题，请检查上述失败项。${NC}"
    exit 1
fi