import json
import logging
import os
import sqlite3

from core.config import CARDS_FOLDER, DEFAULT_DB_PATH
from core.data.ui_store import load_ui_data
from core.utils.image import extract_card_info
from core.utils.source_revision import build_file_source_revision


logger = logging.getLogger(__name__)


def connect_index_db(db_path=None):
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    return conn


def build_cards_generation(conn, generation: int):
    ui_data = load_ui_data()
    rows = conn.execute(
        'SELECT id, char_name, tags, category, last_modified, token_count, is_favorite FROM card_metadata'
    ).fetchall()

    for row in rows:
        entity_id = f"card::{row['id']}"
        tags = json.loads(row['tags'] or '[]') if row['tags'] else []
        summary = str((ui_data.get(row['id']) or {}).get('summary', ''))
        source_path = os.path.join(CARDS_FOLDER, row['id'].replace('/', os.sep))
        conn.execute(
            '''
            INSERT OR REPLACE INTO index_entities_v2(
                generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                display_category, physical_category, category_mode, favorite, summary_preview,
                updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                generation,
                entity_id,
                'card',
                source_path,
                '',
                row['char_name'] or '',
                str(row['id']).split('/')[-1],
                row['category'] or '',
                row['category'] or '',
                'physical',
                int(row['is_favorite'] or 0),
                summary,
                float(row['last_modified'] or 0),
                0,
                int(row['token_count'] or 0),
                str(row['char_name'] or '').lower(),
                float(row['last_modified'] or 0),
                '',
                build_file_source_revision(source_path),
            ),
        )

        for tag in tags:
            normalized_tag = str(tag).strip()
            if not normalized_tag:
                continue
            conn.execute(
                'INSERT OR REPLACE INTO index_entity_tags_v2(generation, entity_id, tag) VALUES (?, ?, ?)',
                (generation, entity_id, normalized_tag),
            )

        content = ' '.join([
            str(row['char_name'] or ''),
            str(row['id']).split('/')[-1],
            str(row['category'] or ''),
            summary,
            ' '.join(str(tag) for tag in tags),
        ]).strip()
        conn.execute(
            'INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (?, ?, ?)',
            (generation, entity_id, content),
        )
        conn.execute(
            'INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (?, ?, ?)',
            (generation, entity_id, content),
        )

    conn.commit()
    return len(rows)


def build_worldinfo_generation(conn, generation: int, inspected_books=None):
    rows = conn.execute(
        '''
        SELECT id, char_name, category, character_book_name, last_modified, has_character_book
        FROM card_metadata
        WHERE has_character_book = 1
        '''
    ).fetchall()
    inspected_books = inspected_books or {}

    items_written = 0
    for row in rows:
        card_id = str(row['id'])
        card_path = os.path.join(CARDS_FOLDER, card_id.replace('/', os.sep))
        book = inspected_books.get(card_id)
        if book is None:
            info = extract_card_info(card_path)
            if not info:
                continue

            data = info.get('data', {}) if isinstance(info, dict) and 'data' in info else info
            book = data.get('character_book') if isinstance(data, dict) else None
        if not isinstance(book, dict):
            continue

        name = str(book.get('name') or row['character_book_name'] or f"{row['char_name']}'s WI").strip()
        entity_id = f'world::embedded::{card_id}'
        owner_entity_id = f'card::{card_id}'
        category = str(row['category'] or '')

        conn.execute(
            '''
            INSERT OR REPLACE INTO index_entities_v2(
                generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                display_category, physical_category, category_mode, favorite, summary_preview,
                updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                generation,
                entity_id,
                'world_embedded',
                card_path,
                owner_entity_id,
                name,
                os.path.basename(card_path),
                category,
                '',
                'inherited',
                0,
                '',
                float(row['last_modified'] or 0),
                0,
                0,
                name.lower(),
                float(row['last_modified'] or 0),
                '',
                build_file_source_revision(card_path),
            ),
        )
        conn.execute(
            'INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (?, ?, ?)',
            (generation, entity_id, ' '.join(filter(None, [name, category, str(row['char_name'] or '')]))),
        )
        conn.execute(
            'INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (?, ?, ?)',
            (generation, entity_id, ' '.join(filter(None, [name, category, str(row['char_name'] or '')]))),
        )
        items_written += 1

    return items_written
