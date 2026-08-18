#!/usr/bin/env python3
"""
KKYX Spider 统一 CLI 入口 (plans/run-menu.md)

每个操作都有独立且唯一的 CLI 命令，TUI 菜单 (./run) 只是对这些
命令的图形化包装，任何命令都可以脱离菜单单独执行：

    uv run python3 cli.py init      # 初始化环境 (uv / 依赖 / Playwright / 凭据)
    uv run python3 cli.py run       # 自动化运行全流程 (登录 + 索引 + 详情 + WP 同步)
    uv run python3 cli.py index     # 单进程: 索引采集
    uv run python3 cli.py post      # 单进程: 详情采集
    uv run python3 cli.py md        # 单操作: Markdown 输出
    uv run python3 cli.py wp        # 单操作: WordPress 输出
    uv run python3 cli.py history   # 查看自动运行历史
    uv run python3 cli.py status    # 本地数据库状态统计
    uv run python3 cli.py web       # 启动 Web 监控控制台
    uv run python3 cli.py clean     # 清理缓存 / 调试 HTML / 截图

run/index/post/md/wp 五个核心命令的每次执行都会记录到 run_history 表，
可通过 `cli.py history` 查看。
"""

import os
import sys
import glob
import shutil
import argparse
import sqlite3
import tomllib
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Colors
GREEN, YELLOW, RED, CYAN, BOLD, NC = "\033[0;32m", "\033[1;33m", "\033[0;31m", "\033[0;36m", "\033[1m", "\033[0m"

# Commands whose executions are recorded into run_history
HISTORY_COMMANDS = ("run", "index", "post", "md", "wp")


def info(msg):    print(f"{CYAN}[INFO]{NC} {msg}")
def ok(msg):      print(f"{GREEN}[OK]{NC} {msg}")
def warn(msg):    print(f"{YELLOW}[WARN]{NC} {msg}")
def fail(msg):    print(f"{RED}[ERROR]{NC} {msg}")


# ============================================================================
# Helpers
# ============================================================================

def load_core_modules():
    """Import config + core modules. Fails fast with a friendly message when
    the environment is not initialized (credentials missing)."""
    try:
        import config  # noqa: F401
    except (ValueError, FileNotFoundError) as e:
        fail("配置加载失败，项目尚未初始化。请先运行: uv run python3 cli.py init")
        fail(f"原因: {e}")
        sys.exit(1)
    from core.db_manager import DBManager
    return DBManager


def raw_db_path():
    """Resolve DB path directly from TOML without triggering credential
    validation (so history/status work on an uninitialized environment)."""
    data = {}
    for name in ("config.default.toml", ".config.toml"):
        p = PROJECT_ROOT / name
        if p.exists():
            try:
                with open(p, "rb") as f:
                    loaded = tomllib.load(f)
                for k, v in loaded.get("database", {}).items():
                    data.setdefault(k, v)
            except (tomllib.TOMLDecodeError, OSError):
                pass
    return data.get("db_file", ".data/db/kkyx_spider.db")


def raw_connect():
    path = raw_db_path()
    if not os.path.exists(path):
        return None, path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn, path


def summary_delta(before, after):
    """Human-readable delta between two get_status_summary() snapshots.
    run_history is excluded: it would always show +1 for the record itself."""
    parts = []
    for table, count in after.get("tables", {}).items():
        if table == "run_history":
            continue
        delta = count - before.get("tables", {}).get(table, count)
        if delta:
            parts.append(f"{table}{delta:+d}")
    for status, count in after.get("statuses", {}).items():
        delta = count - before.get("statuses", {}).get(status, count)
        if delta:
            parts.append(f"{status}{delta:+d}")
    return ", ".join(parts) if parts else "无状态变化"


class RunRecorder:
    """Context manager that records an execution into run_history."""

    def __init__(self, command, db=None):
        self.command = command
        self.db = db
        self.run_id = None
        self.before = None

    def __enter__(self):
        if self.db:
            try:
                self.before = self.db.get_status_summary()
                self.run_id = self.db.start_run_history(self.command)
            except Exception as e:
                warn(f"无法写入运行历史: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.run_id:
            return False
        try:
            if exc_type is KeyboardInterrupt:
                status, summary = "interrupted", "用户中断"
            elif exc_type is None:
                status, summary = "success", summary_delta(self.before, self.db.get_status_summary())
            else:
                status, summary = "failed", f"{exc_type.__name__}: {exc_val}"[:300]
            self.db.finish_run_history(self.run_id, status, summary)
        except Exception:
            pass
        return False


def ensure_login():
    """Auto-login when .auth/state.json is missing (same contract as main.py)."""
    state_path = os.path.join(".auth", "state.json")
    if os.path.exists(state_path):
        return
    warn("未发现活动会话 (.auth/state.json)，正在执行自动登录...")
    res = subprocess.run([sys.executable, ".auth/auto_login.py"])
    if res.returncode != 0:
        fail("自动登录失败，中止本次运行。")
        sys.exit(1)


# ============================================================================
# Command implementations (one unique CLI command per operation)
# ============================================================================

def cmd_init(args):
    """init: 初始化环境 (委托给 init.sh: uv / 依赖 / Playwright / 凭据)"""
    info("初始化环境 (init.sh)...")
    res = subprocess.run(["bash", "init.sh"] + (["--non-interactive"] if args.yes else []))
    sys.exit(res.returncode)


def cmd_run(args):
    """run: 自动化运行全流程 (登录 + 索引发现 + 详情采集 + WP 同步)"""
    DBManager = load_core_modules()
    from core.parallel_scheduler import ParallelScheduler

    ensure_login()

    db = DBManager()
    with RunRecorder("run", db):
        scheduler = ParallelScheduler()
        scheduler.run_pipeline()
    ok("全流程运行结束。")


def cmd_index(args):
    """index: 单进程运行索引发现 (Stage 1)"""
    DBManager = load_core_modules()
    from core.browser_handler import BrowserHandler
    from core.producer_consumer import IndexProducer

    db = DBManager()
    with RunRecorder("index", db):
        bh = BrowserHandler(os.path.join(".auth", "state.json"))
        try:
            info("启动索引采集 (Index Producer)...")
            IndexProducer(bh, db).run()
        finally:
            bh.close()
    ok("索引采集结束。")


def cmd_post(args):
    """post: 单进程运行详情采集 (Stage 2, 需要有效登录会话)"""
    DBManager = load_core_modules()
    from core.browser_handler import BrowserHandler
    from core.auth import verify_session_via_user_center, AUTH_DEAD
    from core.producer_consumer import PostConsumer

    ensure_login()

    db = DBManager()
    with RunRecorder("post", db):
        bh = BrowserHandler(os.path.join(".auth", "state.json"))
        try:
            auth = verify_session_via_user_center(bh.context)
            if auth == AUTH_DEAD:
                fail("会话已失效 (DEAD)。请先运行: uv run python3 .auth/auto_login.py")
                sys.exit(1)
            info("启动详情采集 (Post Consumer)...")
            PostConsumer(bh, db).run()
        finally:
            bh.close()
    ok("详情采集结束。")


def cmd_md(args):
    """md: 将已完成的游戏导出为 Hugo 兼容 Markdown"""
    DBManager = load_core_modules()
    from core.md_exporter import MDExporter

    db = DBManager()
    with RunRecorder("md", db):
        count, total, output_dir = MDExporter(db).export_all(limit=args.limit)
        if total and count == 0:
            raise RuntimeError(f"{total} 篇待导出但全部失败（请检查输出目录权限: {output_dir}）")
    ok(f"Markdown 输出完成: {count}/{total} 篇 -> {output_dir}")


def cmd_wp(args):
    """wp: 将已完成的游戏同步发布到 WordPress"""
    DBManager = load_core_modules()
    from core.wp_publisher import WPPublisher
    import config as cfg

    if not (cfg.WP_BASE_URL and cfg.WP_USERNAME and cfg.WP_APP_PASSWORD):
        fail("WordPress 凭据未配置。请在 .config.toml 中填写 [wordpress] 配置。")
        sys.exit(1)

    db = DBManager()
    with RunRecorder("wp", db):
        info("启动 WordPress 同步 (WPPublisher)...")
        WPPublisher(db).sync_completed_games()
    ok("WordPress 同步结束。")


def cmd_history(args):
    """history: 查看自动运行历史 (run_history 表)"""
    conn, path = raw_connect()
    if conn is None:
        warn(f"数据库尚未创建 ({path})。运行流水线后将自动创建。")
        return

    with conn:
        try:
            rows = conn.execute(
                "SELECT * FROM run_history ORDER BY id DESC LIMIT ?;", (args.limit,)
            ).fetchall()
        except sqlite3.OperationalError:
            warn("run_history 表尚未创建 (旧数据库)。执行任意核心命令后将自动创建。")
            return

    if not rows:
        info("暂无运行历史。")
        return

    print(f"\n{BOLD}📜 最近 {len(rows)} 条自动运行历史:{NC}")
    print(f"{CYAN}{'ID':>4}  {'命令':<8}{'状态':<6}  {'开始时间':<20}  {'耗时':>8}  摘要{NC}")
    print("-" * 100)
    plain = {"success": "✔ 成功", "failed": "✘ 失败",
             "interrupted": "⚠ 中断", "running": "… 运行中"}
    colors = {"success": GREEN, "failed": RED, "interrupted": YELLOW, "running": YELLOW}
    for r in rows:
        label = plain.get(r["status"], str(r["status"]))
        color = colors.get(r["status"], "")
        duration = f"{r['duration_sec']}s" if r["duration_sec"] is not None else "-"
        print(f"{r['id']:>4}  {r['command']:<8}{color}{label:<6}{NC}  {str(r['started_at']):<20}  {duration:>8}  {r['summary'] or '-'}")
    print("")


def cmd_status(args):
    """status: 本地数据库状态统计 (不依赖凭据，可直接在未初始化环境查看)"""
    conn, path = raw_connect()
    if conn is None:
        warn(f"数据库尚未创建 ({path})。运行流水线后将自动创建。")
        return

    with conn:
        tables = [t[0] for t in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()]

        print(f"\n{BOLD}📊 数据表记录统计:{NC}")
        for t in tables:
            count = conn.execute(f"SELECT count(*) FROM {t};").fetchone()[0]
            print(f" ┣━ {t}: {count} 条记录")

        if "games" in tables:
            print(f"\n{BOLD}🎮 游戏采集状态分布:{NC}")
            statuses = {0: "待处理 PENDING", 1: "已完成 COMPLETED", 2: "需更新 NEEDS_UPDATE", 3: "死信 DEAD_LETTER"}
            for code, name in statuses.items():
                count = conn.execute(
                    "SELECT count(*) FROM games WHERE crawl_status = ?;", (code,)
                ).fetchone()[0]
                print(f" ┣━ {name}: {count} 个")
    print("")


def cmd_web(args):
    """web: 启动 Web 数据库监控控制台"""
    info("启动 Web 监控控制台...")
    res = subprocess.run([sys.executable, "web/app.py"])
    sys.exit(res.returncode)


def cmd_clean(args):
    """clean: 清理缓存、调试 HTML 与截图 (不影响数据库)"""
    targets = []
    for pattern in (".debug/screenshots/*", ".debug/html/*", ".debug/network/*",
                    ".screenshots/*", ".screenshot/*"):
        targets.extend(glob.glob(pattern))

    if not targets:
        info("没有需要清理的缓存文件。")
        return

    if not args.yes:
        confirm = input(f"将删除 {len(targets)} 个缓存/截图文件 (不影响数据库)，继续吗？(y/N): ")
        if confirm.strip().lower() != "y":
            warn("已取消清理。")
            return

    for pattern in (".debug/screenshots", ".debug/html", ".debug/network",
                    ".screenshots", ".screenshot"):
        shutil.rmtree(pattern, ignore_errors=True)

    # Recreate empty dirs expected by the pipeline
    for d in (".debug/screenshots", ".debug/html", ".debug/network", ".screenshot"):
        os.makedirs(d, exist_ok=True)

    ok(f"已清理 {len(targets)} 个文件，缓存目录已重置。")


# ============================================================================
# Parser
# ============================================================================

def build_parser():
    parser = argparse.ArgumentParser(
        prog="kkyx",
        description="KKYX 资源采集引擎统一 CLI (每个操作一个独立命令)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="初始化环境 (uv / 依赖 / Playwright / 凭据)")
    p.add_argument("-y", "--yes", action="store_true", help="非交互模式")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("run", help="自动化运行全流程 (登录+索引+详情+WP)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("index", help="单进程: 索引采集 (Index Producer)")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("post", help="单进程: 详情采集 (Post Consumer)")
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("md", help="单操作: Markdown 输出 (Hugo 兼容)")
    p.add_argument("--limit", type=int, default=None, help="本次最多导出条数")
    p.set_defaults(func=cmd_md)

    p = sub.add_parser("wp", help="单操作: WordPress 同步发布")
    p.set_defaults(func=cmd_wp)

    p = sub.add_parser("history", help="查看自动运行历史")
    p.add_argument("--limit", type=int, default=20, help="显示条数 (默认 20)")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("status", help="查看本地数据库状态统计")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("web", help="启动 Web 数据库监控控制台 (Flask)")
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("clean", help="清理缓存、调试 HTML 与截图")
    p.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    p.set_defaults(func=cmd_clean)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command in HISTORY_COMMANDS:
        info(f"执行命令: {args.command}")

    try:
        args.func(args)
    except KeyboardInterrupt:
        warn(f"命令 {args.command} 已被用户中断。")
        sys.exit(130)


if __name__ == "__main__":
    main()
