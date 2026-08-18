"""
Markdown Output Engine (Hugo-compatible)

Assembles completed games from the local SQLite database into standalone
Markdown files, following the assembly rules in plans/09-hugo-output-vision.md:

    1. Front matter: title / date / featured_image / categories / tags
    2. Download section: jump-engine links (md5 of the raw URL) with raw URL fallback
    3. Body: game description HTML with images mapped to CDN (or local storage)

File naming is stable and idempotent: {game_id:05d}-{safe_title}.md
Exported games are tracked in the md_export_log table, mirroring wp_sync_log.
"""

import os
import re
import json
import hashlib
from datetime import datetime
from core.log_formatter import logger
import config


def slugify_title(title):
    """Keep CJK/alphanumeric chars, drop filesystem-hostile ones, cap length."""
    safe = re.sub(r'[\\/:*?"<>|\s#`\'\[\]{}]+', '-', str(title)).strip('-.')
    safe = re.sub(r'-{2,}', '-', safe)
    return safe[:60].strip('-.')


class MDExporter:
    def __init__(self, db_manager):
        self.db = db_manager
        self.output_dir = config.MD_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    # ----------------------------------------------------------
    # Asset URL resolution (CDN preferred, local storage fallback)
    # ----------------------------------------------------------
    def asset_url(self, asset):
        filename = os.path.basename(asset['local_path'])
        if config.CDN_BASE_URL:
            return f"{config.CDN_BASE_URL.rstrip('/')}/{filename}"
        return asset['local_path']

    def build_url_mapping(self, game_id):
        """original_url -> resolved URL for every local asset of the game."""
        mapping = {}
        for asset in self.db.get_game_assets(game_id):
            mapping[asset['original_url']] = self.asset_url(asset)
        return mapping

    def replace_images(self, html_content, url_mapping):
        """Rewrite img src attributes to CDN/local URLs (same protocol as WPPublisher)."""
        if not html_content:
            return html_content or ""

        def cdn_replace(match):
            img_tag = match.group(0)
            src_match = re.search(r'src="([^"]*)"', img_tag)
            if src_match and src_match.group(1) in url_mapping:
                img_tag = img_tag.replace(
                    f'src="{src_match.group(1)}"',
                    f'src="{url_mapping[src_match.group(1)]}"'
                )
            return img_tag

        return re.sub(r'<img[^>]*>', cdn_replace, html_content)

    # ----------------------------------------------------------
    # Jump engine link construction (plans/09: md5-based jump, raw fallback)
    # ----------------------------------------------------------
    def build_jump_url(self, raw_url):
        if config.JUMP_BASE_URL:
            jump_id = hashlib.md5(raw_url.encode("utf-8")).hexdigest()
            return f"{config.JUMP_BASE_URL.rstrip('/')}/jump?id={jump_id}"
        return raw_url  # fallback: raw physical download address

    def build_download_section(self, game):
        lines = ["### 🚀 资源下载", ""]

        try:
            links = game.get('download_links') or []
            if isinstance(links, str):
                links = json.loads(links) if links.strip() else []
        except (ValueError, TypeError):
            links = []

        for link in links:
            platform = link.get('platform', '网盘')
            url = link.get('url', '')
            if not url:
                continue
            entry = f"- {platform}: [下载]({self.build_jump_url(url)})"
            password = link.get('password') or ''
            if password:
                entry += f" (密码: {password})"
            lines.append(entry)

        if not links:
            lines.append("- (暂无可用下载地址)")

        extract_password = game.get('extract_password') or ''
        if extract_password:
            lines.append(f"- 解压密码: `{extract_password}`")

        lines.append("")
        return lines

    # ----------------------------------------------------------
    # Front matter
    # ----------------------------------------------------------
    def resolve_tags(self, title):
        tags = list(config.WP_FIXED_TAGS or [])
        for kw in (config.WP_TAG_KEYWORDS or []):
            if kw in title and kw not in tags:
                tags.append(kw)
        return tags[:8]

    def resolve_featured_image(self, game_id, url_mapping):
        assets = self.db.get_game_assets(game_id)
        ordered = sorted(assets, key=lambda a: (a.get('asset_type') != 'cover', a.get('id', 0)))
        if not ordered:
            return ""
        return self.asset_url(ordered[0])

    def build_front_matter(self, game, featured_image):
        title = str(game['title']).replace('"', '\\"')
        date = game.get('publish_date') or datetime.now().strftime("%Y-%m-%d")
        tags = self.resolve_tags(game['title'])

        lines = [
            "---",
            f'title: "{title}"',
            f"date: {date}",
            "draft: false",
        ]
        if featured_image:
            lines.append(f'featured_image: "{featured_image}"')
        lines.append('categories: ["游戏"]')
        lines.append("tags: [" + ", ".join(f'"{t}"' for t in tags) + "]")
        lines.append("---")
        lines.append("")
        return lines

    # ----------------------------------------------------------
    # Single game assembly
    # ----------------------------------------------------------
    def export_game(self, game):
        game_id = game['id']
        url_mapping = self.build_url_mapping(game_id)
        featured_image = self.resolve_featured_image(game_id, url_mapping)
        body_html = self.replace_images(game.get('description') or "", url_mapping)

        parts = []
        parts.extend(self.build_front_matter(game, featured_image))
        parts.extend(self.build_download_section(game))
        parts.append("---")
        parts.append("")
        parts.append(body_html)
        parts.append("")

        filename = f"{game_id:05d}-{slugify_title(game['title']) or 'game'}.md"
        file_path = os.path.join(self.output_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))

        self.db.save_md_export_log(game_id, file_path)
        return file_path

    # ----------------------------------------------------------
    # Batch entry point
    # ----------------------------------------------------------
    def export_all(self, limit=None):
        """Export every not-yet-exported completed game.

        Returns (exported_count, total_pending, output_dir).
        """
        games = self.db.get_unexported_completed_games(limit)
        if not games:
            logger.info("[MD] No completed games pending Markdown export.")
            return 0, 0, self.output_dir

        logger.info(f"[MD] Exporting {len(games)} games to {self.output_dir} ...")
        count = 0
        for game in games:
            try:
                path = self.export_game(game)
                count += 1
                logger.info(f"[MD] Exported game ID {game['id']}: {path}")
            except Exception as e:
                logger.error(f"[MD] Failed to export game ID {game['id']} ({game['title']}): {e}")
        logger.info(f"[MD] Markdown export finished. {count}/{len(games)} games exported.")
        return count, len(games), self.output_dir
