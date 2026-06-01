# Hugo 静态分发与跳转转换引擎

> 这是项目的长期愿景：将采集数据通过 Hugo 静态站分发，实现"域名秒级切换"能力。

---

## 1. 核心概念

### 占位符协议 (Placeholder Protocol)
数据库中不允许出现具体的物理图片域名，必须使用统一占位符：
```
{{IMG_CDN_PREFIX}}/[图片MD5].webp
```

### 跳转引擎 (Jump Engine)
外部短链接路由系统，将下载地址与前台展示解耦：
```
xxx.com/jump?id=[原始地址MD5] → 302重定向 → 真实下载地址
```

## 2. 三阶段流水线

### 阶段一：采集与初洗 (Scrape & Normalize)

```
获取原始数据 (标题 + HTML简介 + 图片 + 下载地址)
    │
    ├─→ 下载所有图片，计算 MD5，去重存储
    ├─→ HTML 正文中所有 src 替换为 {{IMG_CDN_PREFIX}}/[MD5].webp
    └─→ 纯净 HTML + 原始下载地址写入数据库
```

### 阶段二：资产云端化 (Asset Cloudification)

```
本地 data/storage/{md5}.ext 文件
    │
    └─→ 后台自动同步至 CDN (test-img-cdn.freessr.bid/kkyx/)
```

### 阶段三：Hugo 动态装配 (Assemble & Publish)

```
触发条件: 数据库有新增已完成内容
    │
    ├─→ 下载地址 → 计算 MD5 → 构造跳转链接
    ├─→ HTML 正文 → 替换占位符为真实 CDN 路径
    └─→ 生成 Hugo Markdown 文件 (.md)
```

## 3. 页面装配规则

生成的 Markdown 严格遵循以下组装顺序：

```markdown
---
title: "游戏标题"
featured_image: "https://cdn.xxx.com/kkyx/a1b2c3.jpg"
date: 2025-01-10
categories: ["游戏"]
tags: ["RPG", "汉化"]
---

### 🚀 资源下载
- 百度云盘: [下载](xxx.com/jump?id=md5hash) (密码: abcd)
- 天翼云盘: [下载](xxx.com/jump?id=md5hash) (访问码: efgh)

---

(游戏正文 HTML，图片使用 CDN URL)
```

## 4. 异常处理

| 场景 | 处理方式 |
|------|----------|
| 图片去重合并 | 不同原图但 MD5 相同 → 合并为一个占位符 |
| 跳转链接构造失败 | 兜底展示原始物理下载地址 |
| CDN 同步延迟 | 先生成带预期路径的 .md，不阻塞流程 |
| 脏数据 (无下载地址+无正文) | 标记为无效，跳过生成 |

## 5. 域名迁移策略

**核心约束**: 全局域名在配置文件中维护，绝对禁止修改数据库历史数据。

迁移步骤：
1. 修改配置文件中的 CDN 域名和 Jump 域名
2. 重新触发 .md 构建
3. 或: `sed` 批量替换 .md 文件中的域名
