#!/bin/bash
# KKYX Spider 配置系统验证脚本
# 可从任意目录调用；会自动 cd 到项目根目录。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

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

check_pass() {
    echo -e "${GREEN}✅${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

check_fail() {
    echo -e "${RED}❌${NC} $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

echo "=== 1. 文件结构检查 ==="
echo ""

# 检查核心文件
[ -f "config/__init__.py" ] && check_pass "config/__init__.py 存在" || check_fail "config/__init__.py 缺失"
[ -f "config.default.toml" ] && check_pass "config.default.toml 存在" || check_fail "config.default.toml 缺失"
[ -f "main.py" ] && check_pass "main.py 存在" || check_fail "main.py 缺失"
[ -f ".gitignore" ] && check_pass ".gitignore 存在" || check_fail ".gitignore 缺失"

# 检查文档
[ -f "docs/CONFIGURATION.md" ] && check_pass "docs/CONFIGURATION.md 存在" || check_warn "docs/CONFIGURATION.md 缺失"

# 检查脚本
[ -f "run.sh" ] && check_pass "run.sh 存在" || check_fail "run.sh 缺失"
[ -f "init.sh" ] && check_pass "init.sh 存在" || check_fail "init.sh 缺失"

# 检查可选文件
[ -f ".config.toml" ] && check_pass ".config.toml 存在 (本地配置)" || check_warn ".config.toml 不存在"

echo ""
echo "=== 2. 旧文件清理检查 ==="
echo ""

[ ! -f ".env" ] && check_pass ".env 已移除" || check_fail ".env 仍存在"
[ ! -f "config.py" ] && check_pass "根目录 config.py 已迁移至 config/" || check_fail "根目录 config.py 仍存在"
[ ! -f "config/default.toml" ] && check_pass "config/default.toml 不存在于 config/ (已放回根目录)" || check_warn "config/default.toml 仍存在于 config/ 文件夹"
[ ! -f "config.json" ] && check_pass "config.json 已删除" || check_fail "config.json 仍存在"
[ ! -f "config.test.json" ] && check_pass "config.test.json 已删除" || check_fail "config.test.json 仍存在"

echo ""
echo "=== 3. .gitignore 检查 ==="
echo ""

grep -q "\.config\.toml" .gitignore && check_pass ".config.toml 在 .gitignore 中" || check_fail ".config.toml 不在 .gitignore 中"
grep -q "\.data/" .gitignore && check_pass ".data/ 在 .gitignore 中" || check_fail ".data/ 不在 .gitignore 中"
grep -q "\.screenshot/" .gitignore && check_pass ".screenshot/ 在 .gitignore 中" || check_fail ".screenshot/ 不在 .gitignore 中"
grep -q "\.auth/" .gitignore && check_pass ".auth/ 在 .gitignore 中" || check_fail ".auth/ 不在 .gitignore 中"

echo ""
echo "=== 4. 目录结构检查 ==="
echo ""

[ -d ".data" ] && check_pass ".data/ 目录存在" || check_warn ".data/ 目录不存在（首次运行时创建）"
[ -d ".data/storage" ] && check_pass ".data/storage/ 目录存在" || check_warn ".data/storage/ 目录不存在（首次运行时创建）"
[ -d ".screenshot" ] && check_pass ".screenshot/ 目录存在" || check_warn ".screenshot/ 目录不存在（首次运行时创建）"

echo ""
echo "=== 5. 配置文件内容检查 ==="
echo ""

# 检查 config.default.toml 内容
grep -q "\[kkyx\]" config.default.toml && check_pass "config.default.toml 包含 [kkyx]" || check_fail "config.default.toml 缺少 [kkyx]"
grep -q "\[wordpress\]" config.default.toml && check_pass "config.default.toml 包含 [wordpress]" || check_fail "config.default.toml 缺少 [wordpress]"
grep -q "\[cdn\]" config.default.toml && check_pass "config.default.toml 包含 [cdn]" || check_fail "config.default.toml 缺少 [cdn]"
grep -q "\[safety\]" config.default.toml && check_pass "config.default.toml 包含 [safety]" || check_fail "config.default.toml 缺少 [safety]"

# 凭据在 config.default.toml 中应留空
! grep -q '^username = "[^"]' config.default.toml && check_pass "config.default.toml 中 kkyx 凭据留空" || check_warn "config.default.toml 中存在非空 username（建议留空）"

# 检查 .config.toml 凭据（若存在）
if [ -f ".config.toml" ]; then
    grep -q "username" .config.toml && check_pass ".config.toml 包含 kkyx.username" || check_fail ".config.toml 缺少 kkyx.username"
    grep -q "password" .config.toml && check_pass ".config.toml 包含 kkyx.password" || check_fail ".config.toml 缺少 kkyx.password"
fi

echo ""
echo "=== 6. 代码路径更新检查 ==="
echo ""

# 检查 web/app.py 不再依赖 KKYX_USER 环境变量
grep -q 'config.USERNAME' web/app.py && check_pass "web/app.py 通过 config 读取凭据" || check_warn "web/app.py 未使用 config.USERNAME"
! grep -q 'os.getenv("KKYX_USER")' web/app.py && check_pass "web/app.py 不再读取 KKYX_USER 环境变量" || check_warn "web/app.py 仍读取 KKYX_USER 环境变量"

echo ""
echo "=== 7. 语法检查 ==="
echo ""

# Python 语法
python3 -m py_compile config/__init__.py 2>/dev/null && check_pass "config/__init__.py 语法正确" || check_fail "config/__init__.py 语法错误"

# TOML 语法
python3 -c "import tomllib; tomllib.load(open('config.default.toml','rb'))" 2>/dev/null && check_pass "config.default.toml 语法正确" || check_fail "config.default.toml 语法错误"
if [ -f ".config.toml" ]; then
    python3 -c "import tomllib; tomllib.load(open('.config.toml','rb'))" 2>/dev/null && check_pass ".config.toml 语法正确" || check_fail ".config.toml 语法错误"
fi

echo ""
echo "=== 8. 配置加载集成检查 ==="
echo ""

if uv run python3 -c "import config; assert config.USERNAME; assert config.PASSWORD; print('OK')" >/dev/null 2>&1; then
    check_pass "config 包加载成功且必填凭据已配置"
else
    check_fail "config 包加载失败或缺少必填凭据 (kkyx.username / kkyx.password)"
fi

echo ""
echo "=========================================="
echo "  验证结果汇总"
echo "=========================================="
echo -e "${GREEN}通过: $PASS_COUNT${NC}"
echo -e "${RED}失败: $FAIL_COUNT${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}🎉 所有检查通过！配置系统正常。${NC}"
    exit 0
else
    echo -e "${RED}⚠️  发现 $FAIL_COUNT 个问题，请检查上述失败项。${NC}"
    exit 1
fi
