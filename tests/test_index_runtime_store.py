import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.context import AppContext
from core.data.index_runtime_store import (
    activate_generation,
    allocate_build_generation,
    clear_generation_data,
    ensure_index_runtime_schema,
)


def test_allocate_build_generation_increments_from_active(tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "UPDATE index_build_state SET active_generation = 4 WHERE scope = 'cards'"
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        generation = allocate_build_generation(conn, 'cards')
        row = conn.execute(
            "SELECT active_generation, building_generation FROM index_build_state WHERE scope = 'cards'"
        ).fetchone()

    assert generation == 5
    assert row == (4, 5)


def test_activate_generation_promotes_building_generation(tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "UPDATE index_build_state SET active_generation = 2, building_generation = 3, state = 'running', phase = 'activate_generation' WHERE scope = 'cards'"
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        activate_generation(conn, 'cards', 3, items_written=12)
        row = conn.execute(
            "SELECT active_generation, building_generation, state, items_written FROM index_build_state WHERE scope = 'cards'"
        ).fetchone()

    assert row == (3, 0, 'ready', 12)


def test_activate_generation_rejects_stale_generation(tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "UPDATE index_build_state SET active_generation = 2, building_generation = 4, state = 'running', phase = 'activate_generation' WHERE scope = 'cards'"
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        activated = activate_generation(conn, 'cards', 3, items_written=12)
        row = conn.execute(
            "SELECT active_generation, building_generation, state, items_written FROM index_build_state WHERE scope = 'cards'"
        ).fetchone()

    assert activated is False
    assert row == (2, 4, 'running', 0)


def test_clear_generation_data_removes_only_target_generation(tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "INSERT INTO index_entities_v2(generation, entity_id, entity_type, source_path, name, filename) VALUES (1, 'card::old', 'card', 'old.png', 'Old', 'old.png')"
        )
        conn.execute(
            "INSERT INTO index_entities_v2(generation, entity_id, entity_type, source_path, name, filename) VALUES (2, 'card::new', 'card', 'new.png', 'New', 'new.png')"
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        clear_generation_data(conn, 'cards', 2)
        rows = conn.execute(
            "SELECT generation, entity_id FROM index_entities_v2 ORDER BY generation, entity_id"
        ).fetchall()

    assert rows == [(1, 'card::old')]


def test_clear_generation_data_preserves_other_scope_rows_for_same_generation(tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "INSERT INTO index_entities_v2(generation, entity_id, entity_type, source_path, name, filename) VALUES (2, 'card::same-gen', 'card', 'card.png', 'Card', 'card.png')"
        )
        conn.execute(
            "INSERT INTO index_entities_v2(generation, entity_id, entity_type, source_path, name, filename) VALUES (2, 'world::same-gen', 'world_entry', 'world.json', 'World', 'world.json')"
        )
        conn.execute(
            "INSERT INTO index_entity_tags_v2(generation, entity_id, tag) VALUES (2, 'card::same-gen', 'card-tag')"
        )
        conn.execute(
            "INSERT INTO index_entity_tags_v2(generation, entity_id, tag) VALUES (2, 'world::same-gen', 'world-tag')"
        )
        conn.execute(
            "INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (2, 'card::same-gen', 'card search')"
        )
        conn.execute(
            "INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (2, 'world::same-gen', 'world search')"
        )
        conn.execute(
            "INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (2, 'card::same-gen', 'card search full')"
        )
        conn.execute(
            "INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (2, 'world::same-gen', 'world search full')"
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        clear_generation_data(conn, 'cards', 2)
        entity_rows = conn.execute(
            "SELECT generation, entity_id FROM index_entities_v2 ORDER BY entity_id"
        ).fetchall()
        tag_rows = conn.execute(
            "SELECT generation, entity_id, tag FROM index_entity_tags_v2 ORDER BY entity_id"
        ).fetchall()
        fast_rows = conn.execute(
            "SELECT generation, entity_id, content FROM index_search_fast_v2 ORDER BY entity_id"
        ).fetchall()
        full_rows = conn.execute(
            "SELECT generation, entity_id, content FROM index_search_full_v2 ORDER BY entity_id"
        ).fetchall()

    assert entity_rows == [(2, 'world::same-gen')]
    assert tag_rows == [(2, 'world::same-gen', 'world-tag')]
    assert fast_rows == [(2, 'world::same-gen', 'world search')]
    assert full_rows == [(2, 'world::same-gen', 'world search full')]


def test_clear_generation_data_removes_scope_owned_orphan_aux_rows_only(tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "INSERT INTO index_entity_tags_v2(generation, entity_id, tag) VALUES (2, 'card::orphan', 'card-tag')"
        )
        conn.execute(
            "INSERT INTO index_entity_tags_v2(generation, entity_id, tag) VALUES (2, 'world::orphan', 'world-tag')"
        )
        conn.execute(
            "INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (2, 'card::orphan', 'card orphan search')"
        )
        conn.execute(
            "INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (2, 'world::orphan', 'world orphan search')"
        )
        conn.execute(
            "INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (2, 'card::orphan', 'card orphan search full')"
        )
        conn.execute(
            "INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (2, 'world::orphan', 'world orphan search full')"
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        clear_generation_data(conn, 'cards', 2)
        tag_rows = conn.execute(
            "SELECT generation, entity_id, tag FROM index_entity_tags_v2 ORDER BY entity_id"
        ).fetchall()
        fast_rows = conn.execute(
            "SELECT generation, entity_id, content FROM index_search_fast_v2 ORDER BY entity_id"
        ).fetchall()
        full_rows = conn.execute(
            "SELECT generation, entity_id, content FROM index_search_full_v2 ORDER BY entity_id"
        ).fetchall()

    assert tag_rows == [(2, 'world::orphan', 'world-tag')]
    assert fast_rows == [(2, 'world::orphan', 'world orphan search')]
    assert full_rows == [(2, 'world::orphan', 'world orphan search full')]


def test_clear_generation_data_clears_target_scope_stats(tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "INSERT INTO index_category_stats_v2(generation, scope, entity_type, category_path, direct_count, subtree_count) VALUES (2, 'cards', 'card', 'a', 1, 1)"
        )
        conn.execute(
            "INSERT INTO index_category_stats_v2(generation, scope, entity_type, category_path, direct_count, subtree_count) VALUES (2, 'worldinfo', 'world_entry', 'a', 1, 1)"
        )
        conn.execute(
            "INSERT INTO index_facet_stats_v2(generation, scope, entity_type, facet_name, facet_value, facet_count) VALUES (2, 'cards', 'card', 'tag', 'x', 1)"
        )
        conn.execute(
            "INSERT INTO index_facet_stats_v2(generation, scope, entity_type, facet_name, facet_value, facet_count) VALUES (2, 'worldinfo', 'world_entry', 'tag', 'x', 1)"
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        clear_generation_data(conn, 'cards', 2)
        category_rows = conn.execute(
            "SELECT generation, scope, entity_type, category_path FROM index_category_stats_v2 ORDER BY scope"
        ).fetchall()
        facet_rows = conn.execute(
            "SELECT generation, scope, entity_type, facet_name, facet_value FROM index_facet_stats_v2 ORDER BY scope"
        ).fetchall()

    assert category_rows == [(2, 'worldinfo', 'world_entry', 'a')]
    assert facet_rows == [(2, 'worldinfo', 'world_entry', 'tag', 'x')]


def test_app_context_exposes_richer_index_runtime_state():
    AppContext._instance = None
    ctx = AppContext()

    assert ctx.index_state['schema'] == {
        'db_version': 0,
        'index_runtime_version': 0,
        'state': 'empty',
        'message': '',
    }
    assert ctx.index_state['cards'] == {
        'state': 'empty',
        'phase': '',
        'active_generation': 0,
        'building_generation': 0,
        'items_written': 0,
        'last_error': '',
    }
    assert ctx.index_state['worldinfo'] == {
        'state': 'empty',
        'phase': '',
        'active_generation': 0,
        'building_generation': 0,
        'items_written': 0,
        'last_error': '',
    }
    assert ctx.index_state['jobs'] == {
        'pending_jobs': 0,
        'worker_state': 'idle',
    }
    assert ctx.index_state['state'] == 'empty'
    assert ctx.index_state['scope'] == 'cards'
    assert ctx.index_state['progress'] == 0
    assert ctx.index_state['message'] == ''
    assert ctx.index_state['pending_jobs'] == 0
    assert ctx.index_owner_token == ''
    assert ctx.index_wakeup.is_set() is False
    assert ctx.index_upgrade_active is False
    assert ctx.index_worker_started is False

    AppContext._instance = None


def test_app_context_index_state_update_preserves_legacy_flat_keys():
    AppContext._instance = None
    ctx = AppContext()

    ctx.index_state.update(
        state='building',
        scope='worldinfo',
        progress=7,
        message='queued rebuild',
        pending_jobs=3,
    )

    assert ctx.index_state['state'] == 'building'
    assert ctx.index_state['scope'] == 'worldinfo'
    assert ctx.index_state['progress'] == 7
    assert ctx.index_state['message'] == 'queued rebuild'
    assert ctx.index_state['pending_jobs'] == 3
    assert ctx.index_state['worldinfo']['state'] == 'building'
    assert ctx.index_state['jobs']['pending_jobs'] == 3

    snapshot = dict(ctx.index_state)
    assert snapshot['state'] == 'building'
    assert snapshot['scope'] == 'worldinfo'
    assert snapshot['message'] == 'queued rebuild'
    assert snapshot['pending_jobs'] == 3
    assert snapshot['worldinfo']['state'] == 'building'

    AppContext._instance = None
