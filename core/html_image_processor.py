import os
import hashlib
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from core.log_formatter import logger
import config

DOWNLOAD_HEADERS = {
    'Referer': 'https://www.kkyx.net/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
}

def normalize_url(url, base_url=None):
    """Normalize URL by joining with base and removing query/fragments."""
    if base_url is None:
        base_url = config.BASE_URL
    full_url = urljoin(base_url, url)
    parsed = urlparse(full_url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean_url

def get_file_extension(url, content_type=None):
    """Get file extension from url path or content type."""
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
        return ext
    if content_type:
        if 'image/png' in content_type:
            return '.png'
        elif 'image/jpeg' in content_type:
            return '.jpg'
        elif 'image/gif' in content_type:
            return '.gif'
        elif 'image/webp' in content_type:
            return '.webp'
    return '.jpg'

def process_html_images(page, html_content, game_id, db_manager):
    """
    Process all images in the HTML description of a game.
    Downloads, deduplicates, saves them, and updates the HTML content.
    Returns: (updated_html, assets_list)
    """
    if not html_content:
        return html_content, []
        
    soup = BeautifulSoup(html_content, 'html.parser')
    imgs = soup.find_all('img')
    
    logger.info(f"[ImagePipeline] Found {len(imgs)} img tags in game ID {game_id} HTML.")
    
    storage_dir = config.STORAGE_DIR
    os.makedirs(storage_dir, exist_ok=True)
    
    assets_list = []
    
    for img in imgs:
        # Check lazy load attributes
        real_url = (
            img.get('data-src') or
            img.get('data-original') or
            img.get('data-lazy-src') or
            img.get('src')
        )
        
        if not real_url:
            continue
            
        normalized_url = normalize_url(real_url, config.BASE_URL)
        logger.debug(f"[ImagePipeline] Normalizing image url: {real_url} -> {normalized_url}")
        
        # Layer 1: URL Precheck (fast path)
        existing_asset = db_manager.get_asset_by_url(normalized_url)
        if existing_asset:
            logger.info(f"[ImagePipeline] Layer 1 Hit! URL already tracked: {normalized_url}")
            
            # Re-associate with current game
            db_manager.save_game_asset(
                game_id=game_id,
                asset_type='content',
                local_path=existing_asset['local_path'],
                original_url=normalized_url,
                md5_hash=existing_asset['md5_hash'],
                file_size=existing_asset['file_size'],
                width=existing_asset['width'],
                height=existing_asset['height']
            )
            
            # Clean lazy load attributes and set src to original normalized URL
            img['src'] = normalized_url
            for attr in ['data-src', 'data-original', 'data-lazy-src']:
                if img.has_attr(attr):
                    del img[attr]
            img['referrerpolicy'] = 'no-referrer'
            
            assets_list.append(existing_asset)
            continue
            
        # Download image
        logger.info(f"[ImagePipeline] Downloading image from {normalized_url}...")
        img_data = None
        content_type = None
        
        for attempt in range(3):
            try:
                response = page.request.get(
                    normalized_url,
                    headers=DOWNLOAD_HEADERS,
                    timeout=10000
                )
                if response.status == 200:
                    img_data = response.body()
                    content_type = response.headers.get('content-type', '')
                    break
                else:
                    logger.warning(f"Download failed with status {response.status} (attempt {attempt+1}/3)")
            except Exception as e:
                logger.warning(f"Download exception on attempt {attempt+1}/3: {e}")
                
        if img_data is None:
            logger.error(f"[ImagePipeline] Failed to download image from {normalized_url}. Graceful degradation applied.")
            img['src'] = normalized_url
            for attr in ['data-src', 'data-original', 'data-lazy-src']:
                if img.has_attr(attr):
                    del img[attr]
            img['referrerpolicy'] = 'no-referrer'
            continue
            
        # Layer 2: MD5 Physical Dedup (after download)
        md5_hash = hashlib.md5(img_data).hexdigest()
        ext = get_file_extension(normalized_url, content_type)
        filename = f"{md5_hash}{ext}"
        local_path = os.path.join(storage_dir, filename)
        file_size = len(img_data)
        
        existing_md5_asset = db_manager.get_asset_by_md5(md5_hash)
        if existing_md5_asset:
            logger.info(f"[ImagePipeline] Layer 2 Hit! MD5 {md5_hash} already exists physically at {existing_md5_asset['local_path']}.")
            
            # Link current game to the existing asset path
            db_manager.save_game_asset(
                game_id=game_id,
                asset_type='content',
                local_path=existing_md5_asset['local_path'],
                original_url=normalized_url,
                md5_hash=md5_hash,
                file_size=existing_md5_asset['file_size'],
                width=existing_md5_asset['width'],
                height=existing_md5_asset['height']
            )
            
            assets_list.append(existing_md5_asset)
        else:
            # Save new physical file
            try:
                with open(local_path, 'wb') as f:
                    f.write(img_data)
                logger.info(f"[ImagePipeline] Saved new image to {local_path}")
                
                # Dynamic width and height detection using Pillow
                width, height = None, None
                try:
                    from PIL import Image
                    import io
                    with Image.open(io.BytesIO(img_data)) as pillow_img:
                        width, height = pillow_img.size
                except Exception:
                    pass
                    
                db_manager.save_game_asset(
                    game_id=game_id,
                    asset_type='content',
                    local_path=local_path,
                    original_url=normalized_url,
                    md5_hash=md5_hash,
                    file_size=file_size,
                    width=width,
                    height=height
                )
                
                asset = {
                    'game_id': game_id,
                    'asset_type': 'content',
                    'local_path': local_path,
                    'original_url': normalized_url,
                    'md5_hash': md5_hash,
                    'file_size': file_size,
                    'width': width,
                    'height': height
                }
                assets_list.append(asset)
            except Exception as e:
                logger.error(f"[ImagePipeline] Error saving physical file {local_path}: {e}")
                img['src'] = normalized_url
                for attr in ['data-src', 'data-original', 'data-lazy-src']:
                    if img.has_attr(attr):
                        del img[attr]
                img['referrerpolicy'] = 'no-referrer'
                continue
                
        # Clean lazy-load attributes and update src
        img['src'] = normalized_url
        for attr in ['data-src', 'data-original', 'data-lazy-src']:
            if img.has_attr(attr):
                del img[attr]
        img['referrerpolicy'] = 'no-referrer'
        
    # Standardize all image elements to have referrerpolicy
    for img in soup.find_all('img'):
        img['referrerpolicy'] = 'no-referrer'
        
    return str(soup), assets_list
