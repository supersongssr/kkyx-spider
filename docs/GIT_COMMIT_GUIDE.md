# Git 提交建议

## 推荐的提交方式

```bash
# 1. 查看当前状态
git status

# 2. 添加修改的文件
git add .gitignore
git add config.py
git add core/auth.py
git add core/html_image_processor.py
git add config.test.json  # 标记为删除

# 3. 添加新文件
git add docs/
git add verify_config.sh

# 4. 创建提交
git commit -m "refactor: 重构配置系统和存储路径

- 将图片存储从 data/storage/ 迁移到 .data/storage/
- 将截图存储从 .screenshots/ 迁移到 .screenshot/
- 移除 JSON 配置文件依赖（config.test.json, config.json）
- 实现 .config.py 本地配置覆盖机制
- 更新 .env 变量名（WP_APP_PASSWORD）
- 添加完整的配置文档和迁移指南
- 更新 .gitignore 保护敏感配置

新增文件：
- docs/CONFIGURATION.md (配置说明)
- docs/MIGRATION.md (迁移指南)
- docs/REFACTORING_REPORT.md (重构报告)
- docs/CONFIG_QUICK_REFERENCE.txt (快速参考)
- docs/GIT_COMMIT_GUIDE.md (Git 提交指南)
- docs/REFACTORING_COMPLETE.txt (完成总结)
- verify_config.sh (验证脚本)"

# 5. 查看提交内容
git show --stat

# 6. 推送到远程仓库
git push origin dev
```

## 提交前的检查清单

- [ ] 运行 `./verify_config.sh` 确保所有检查通过
- [ ] 确认 `.env` 和 `.config.py` 不在提交中
- [ ] 确认没有敏感信息被意外提交
- [ ] 测试基本功能是否正常工作

## 分支策略建议

```bash
# 如果在 dev 分支工作
git checkout -b refactor/config-system
# ... 进行修改 ...
git commit ...
git checkout dev
git merge refactor/config-system
git push origin dev

# 或者直接在 dev 分支提交
git commit ...
git push origin dev
```

## 回滚操作（如果需要）

```bash
# 如果需要回滚到重构前的状态
git reset --hard HEAD~1

# 或者创建回滚提交
git revert HEAD
```