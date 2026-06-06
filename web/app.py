import os
import sys
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

# Add root directory to python path for config and db_manager
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config

app = Flask(__name__)
# Generate a random secret key for session if not set
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

DB_PATH = config.DB_FILE

# Get login credentials from environment/dotenv
# Priority: 1. WEB_VIEWER_USER/PWD, 2. KKYX_USER/PWD, 3. admin/admin_kkyx
AUTH_USER = os.getenv("WEB_VIEWER_USER") or os.getenv("KKYX_USER") or "admin"
AUTH_PWD = os.getenv("WEB_VIEWER_PASSWORD") or os.getenv("KKYX_PWD") or "admin_kkyx"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Helper to check if logged in
def is_logged_in():
    return session.get('logged_in') is True

@app.before_request
def require_login():
    # Endpoints that do not require auth
    allowed_routes = ['login', 'static', 'serve_storage']
    if not is_logged_in():
        # Check if the requested endpoint is allowed
        if request.endpoint and request.endpoint not in allowed_routes:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
        
    error = None
    if request.method == 'POST':
        # Support JSON or form submit
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            
        if username == AUTH_USER and password == AUTH_PWD:
            session['logged_in'] = True
            if request.is_json:
                return jsonify({'success': True})
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid username or password"
            if request.is_json:
                return jsonify({'error': error}), 401
                
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    return render_template('index.html', user=AUTH_USER)

# Serve storage files (images)
@app.route('/data/storage/<path:filename>')
def serve_storage(filename):
    # Resolves to .data/storage/ inside PROJECT_ROOT
    storage_dir = os.path.join(PROJECT_ROOT, '.data', 'storage')
    return send_from_directory(storage_dir, filename)

# API: Stats
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        if db_size_bytes < 1024:
            db_size_str = f"{db_size_bytes} B"
        elif db_size_bytes < 1024 * 1024:
            db_size_str = f"{db_size_bytes / 1024:.2f} KB"
        else:
            db_size_str = f"{db_size_bytes / (1024 * 1024):.2f} MB"
            
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Count by status
            # Status: 0=pending, 1=completed, 2=needs_update, 3=dead_letter
            cur.execute("SELECT crawl_status, COUNT(*) FROM games GROUP BY crawl_status")
            status_rows = cur.fetchall()
            status_counts = {0: 0, 1: 0, 2: 0, 3: 0}
            for row in status_rows:
                status_counts[row[0]] = row[1]
                
            total_games = sum(status_counts.values())
            
            # Assets count
            cur.execute("SELECT COUNT(*) FROM game_assets")
            assets_count = cur.fetchone()[0]
            
            # WordPress synced count
            cur.execute("SELECT COUNT(*) FROM wp_sync_log WHERE sync_status = 1")
            synced_count = cur.fetchone()[0]
            
        return jsonify({
            'total_games': total_games,
            'status_counts': {
                'pending': status_counts[0],
                'completed': status_counts[1],
                'needs_update': status_counts[2],
                'dead_letter': status_counts[3]
            },
            'assets_count': assets_count,
            'wp_synced_count': synced_count,
            'db_size': db_size_str,
            'db_last_modified': datetime.fromtimestamp(os.path.getmtime(DB_PATH)).isoformat() if os.path.exists(DB_PATH) else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Games List (Paginated, Searchable)
@app.route('/api/games', methods=['GET'])
def get_games():
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '').strip()
        sync_status = request.args.get('sync_status', '').strip()
        
        offset = (page - 1) * per_page
        
        query = """
            SELECT g.*, (w.wp_post_id IS NOT NULL) as is_synced, w.wp_post_id 
            FROM games g
            LEFT JOIN wp_sync_log w ON g.id = w.game_id
            WHERE 1=1
        """
        count_query = """
            SELECT COUNT(*) 
            FROM games g
            LEFT JOIN wp_sync_log w ON g.id = w.game_id
            WHERE 1=1
        """
        
        params = []
        count_params = []
        
        if search:
            search_clause = " AND (g.title LIKE ? OR g.source_url LIKE ?)"
            query += search_clause
            count_query += search_clause
            like_val = f"%{search}%"
            params.extend([like_val, like_val])
            count_params.extend([like_val, like_val])
            
        if status != '':
            status_clause = " AND g.crawl_status = ?"
            query += status_clause
            count_query += status_clause
            status_val = int(status)
            params.append(status_val)
            count_params.append(status_val)
            
        if sync_status == 'synced':
            sync_clause = " AND w.wp_post_id IS NOT NULL"
            query += sync_clause
            count_query += sync_clause
        elif sync_status == 'unsynced':
            sync_clause = " AND w.wp_post_id IS NULL"
            query += sync_clause
            count_query += sync_clause
            
        # Add sorting - showing newest first
        query += " ORDER BY g.id DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Get total matching records
            cur.execute(count_query, count_params)
            total_records = cur.fetchone()[0]
            
            # Get games list
            cur.execute(query, params)
            rows = cur.fetchall()
            
            games_list = []
            for r in rows:
                d = dict(r)
                # Decode download links safely
                try:
                    if d['download_links']:
                        d['download_links'] = json.loads(d['download_links'])
                except Exception:
                    pass
                games_list.append(d)
                
        total_pages = (total_records + per_page - 1) // per_page
        
        return jsonify({
            'games': games_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_records': total_records,
                'total_pages': total_pages
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Single Game Details
@app.route('/api/games/<int:game_id>', methods=['GET'])
def get_game_details(game_id):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Fetch game
            cur.execute("""
                SELECT g.*, w.wp_post_id, w.synced_at, w.sync_status as wp_sync_status
                FROM games g
                LEFT JOIN wp_sync_log w ON g.id = w.game_id
                WHERE g.id = ?
            """, (game_id,))
            row = cur.fetchone()
            
            if not row:
                return jsonify({'error': 'Game not found'}), 404
                
            game_details = dict(row)
            try:
                if game_details['download_links']:
                    game_details['download_links'] = json.loads(game_details['download_links'])
            except Exception:
                pass
                
            # Fetch assets
            cur.execute("SELECT * FROM game_assets WHERE game_id = ?", (game_id,))
            assets = [dict(r) for r in cur.fetchall()]
            game_details['assets'] = assets
            
        return jsonify(game_details)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Update Game Status or details
@app.route('/api/games/<int:game_id>/status', methods=['POST'])
def update_game_status(game_id):
    try:
        data = request.get_json()
        new_status = data.get('crawl_status')
        new_retry = data.get('retry_count')
        
        if new_status is None:
            return jsonify({'error': 'Missing crawl_status'}), 400
            
        with get_db_connection() as conn:
            cur = conn.cursor()
            # Verify if game exists
            cur.execute("SELECT id FROM games WHERE id = ?", (game_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Game not found'}), 404
                
            # Perform update
            if new_retry is not None:
                cur.execute("""
                    UPDATE games 
                    SET crawl_status = ?, retry_count = ? 
                    WHERE id = ?
                """, (int(new_status), int(new_retry), game_id))
            else:
                cur.execute("""
                    UPDATE games 
                    SET crawl_status = ? 
                    WHERE id = ?
                """, (int(new_status), game_id))
                
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Game status updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Run the app
if __name__ == '__main__':
    host = os.getenv("WEB_VIEWER_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_VIEWER_PORT", 8050))
    print(f"Starting Database Web Viewer Server on http://{host}:{port} ...")
    app.run(host=host, port=port, debug=config.DEBUG_MODE)
