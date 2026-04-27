import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services.preset_versions import build_family_entry_id
from core.services.preset_versions import build_merge_version_plan
from core.services.preset_versions import ensure_unique_version_labels
from core.services.preset_versions import extract_preset_version_meta
from core.services.preset_versions import generate_preset_family_id
from core.services.preset_versions import group_preset_list_items
from core.services.preset_versions import upsert_preset_version_meta


def test_extract_preset_version_meta_degrades_cleanly_for_legacy_payload_without_metadata():
    meta = extract_preset_version_meta(
        {'name': 'Legacy Creative Preset'},
        fallback_name='Fallback Name',
        fallback_filename='creative-v3.json',
    )

    assert meta == {
        'family_id': '',
        'family_name': 'Fallback Name',
        'version_label': 'creative-v3',
        'version_order': 100,
        'is_default_version': False,
        'is_versioned': False,
    }


def test_upsert_preset_version_meta_writes_manager_metadata_block():
    updated = upsert_preset_version_meta(
        {'name': 'Creative v2', 'temperature': 1.1},
        family_id='family-123',
        family_name='Creative Family',
        version_label='v2',
        version_order=20,
        is_default_version=True,
    )

    assert updated['name'] == 'Creative v2'
    assert updated['temperature'] == 1.1
    assert updated['x_st_manager'] == {
        'preset_family_id': 'family-123',
        'preset_family_name': 'Creative Family',
        'preset_version_label': 'v2',
        'preset_version_order': 20,
        'preset_is_default_version': True,
    }


def test_group_preset_list_items_collapses_versioned_items_into_scoped_family_entry():
    family_id = generate_preset_family_id()
    version_two_id = build_family_entry_id('global', 'root-alpha', family_id)
    items = [
        {
            'id': 'single-beta',
            'name': 'Utility',
            'filename': 'utility.json',
            'mtime': 170,
            'source_type': 'global',
            'root_scope_key': 'root-beta',
        },
        {
            'id': 'creative-v1',
            'name': 'Creative Family',
            'filename': 'creative-v1.json',
            'mtime': 160,
            'source_type': 'global',
            'root_scope_key': 'root-alpha',
            'preset_version': {
                'family_id': family_id,
                'family_name': 'Creative Family',
                'version_label': 'v1',
                'version_order': 20,
                'is_default_version': False,
                'is_versioned': True,
            },
        },
        {
            'id': 'creative-v2',
            'name': 'Creative Family',
            'filename': 'creative-v2.json',
            'mtime': 190,
            'source_type': 'global',
            'root_scope_key': 'root-alpha',
            'preset_version': {
                'family_id': family_id,
                'family_name': 'Creative Family',
                'version_label': 'v2',
                'version_order': 10,
                'is_default_version': True,
                'is_versioned': True,
            },
        },
        {
            'id': 'creative-v3',
            'name': 'Creative Family',
            'filename': 'creative-v3.json',
            'mtime': 180,
            'source_type': 'global',
            'root_scope_key': 'root-alpha',
            'preset_version': {
                'family_id': family_id,
                'family_name': 'Creative Family',
                'version_label': 'v3',
                'version_order': 10,
                'is_default_version': False,
                'is_versioned': True,
            },
        },
    ]

    grouped = group_preset_list_items(items)

    assert [entry['id'] for entry in grouped] == [version_two_id, 'single-beta']

    family_entry = grouped[0]
    assert family_entry['entry_type'] == 'family'
    assert family_entry['id'] == version_two_id
    assert family_entry['name'] == 'Creative Family'
    assert family_entry['family_id'] == family_id
    assert family_entry['family_name'] == 'Creative Family'
    assert family_entry['default_version_id'] == 'creative-v2'
    assert family_entry['default_version_label'] == 'v2'
    assert family_entry['version_count'] == 3
    assert [version['id'] for version in family_entry['versions']] == [
        'creative-v2',
        'creative-v3',
        'creative-v1',
    ]

    single_entry = grouped[1]
    assert single_entry['entry_type'] == 'single'
    assert single_entry['id'] == 'single-beta'


def test_ensure_unique_version_labels_suffixes_duplicate_labels_in_order():
    assert ensure_unique_version_labels(['v1', 'v1', 'v2', 'v1']) == ['v1', 'v1 (2)', 'v2', 'v1 (3)']


def test_ensure_unique_version_labels_avoids_collisions_with_existing_suffixed_labels():
    assert ensure_unique_version_labels(['v1', 'v1 (2)', 'v1']) == ['v1', 'v1 (2)', 'v1 (3)']


def test_build_merge_version_plan_keeps_target_default_and_rehomes_all_members():
    target_family_id = generate_preset_family_id()
    source_family_id = generate_preset_family_id()
    target_entry = {
        'entry_type': 'family',
        'id': build_family_entry_id('global', 'root-alpha', target_family_id),
        'family_id': target_family_id,
        'family_name': 'Creative Family',
        'default_version_id': 'target-v1',
        'versions': [
            {
                'id': 'target-v1',
                'name': 'Creative Family',
                'filename': 'target-v1.json',
                'preset_version': {
                    'family_id': target_family_id,
                    'family_name': 'Creative Family',
                    'version_label': 'v1',
                    'version_order': 10,
                    'is_default_version': True,
                    'is_versioned': True,
                },
            },
            {
                'id': 'target-v2',
                'name': 'Creative Family',
                'filename': 'target-v2.json',
                'preset_version': {
                    'family_id': target_family_id,
                    'family_name': 'Creative Family',
                    'version_label': 'v2',
                    'version_order': 20,
                    'is_default_version': False,
                    'is_versioned': True,
                },
            },
        ],
    }
    source_entries = [
        {
            'entry_type': 'family',
            'id': build_family_entry_id('global', 'root-beta', source_family_id),
            'family_id': source_family_id,
            'family_name': 'Legacy Family',
            'default_version_id': 'source-v1',
            'versions': [
                {
                    'id': 'source-v1',
                    'name': 'Legacy Family',
                    'filename': 'source-v1.json',
                    'preset_version': {
                        'family_id': source_family_id,
                        'family_name': 'Legacy Family',
                        'version_label': 'v1',
                        'version_order': 10,
                        'is_default_version': True,
                        'is_versioned': True,
                    },
                },
                {
                    'id': 'source-v3',
                    'name': 'Legacy Family',
                    'filename': 'source-v3.json',
                    'preset_version': {
                        'family_id': source_family_id,
                        'family_name': 'Legacy Family',
                        'version_label': 'v3',
                        'version_order': 30,
                        'is_default_version': False,
                        'is_versioned': True,
                    },
                },
            ],
        },
        {
            'id': 'single-imported',
            'name': 'Imported Single',
            'filename': 'imported-single.json',
            'preset_version': {
                'family_id': '',
                'family_name': '',
                'version_label': 'v2',
                'version_order': 100,
                'is_default_version': False,
                'is_versioned': False,
            },
        },
    ]

    plan = build_merge_version_plan(
        target_entry=target_entry,
        source_entries=source_entries,
        family_name='Merged Creative Family',
    )

    assert plan['family_id'] == target_family_id
    assert plan['family_name'] == 'Merged Creative Family'
    assert plan['default_version_id'] == 'target-v1'
    assert [member['id'] for member in plan['members']] == [
        'target-v1',
        'target-v2',
        'source-v1',
        'source-v3',
        'single-imported',
    ]
    assert [member['preset_version']['version_label'] for member in plan['members']] == [
        'v1',
        'v2',
        'v1 (2)',
        'v3',
        'v2 (2)',
    ]
    assert [member['preset_version']['version_order'] for member in plan['members']] == [10, 20, 30, 40, 50]
    assert [member['preset_version']['family_id'] for member in plan['members']] == [target_family_id] * 5
    assert [member['preset_version']['family_name'] for member in plan['members']] == ['Merged Creative Family'] * 5
    assert [member['preset_version']['is_default_version'] for member in plan['members']] == [
        True,
        False,
        False,
        False,
        False,
    ]
    assert all(member['preset_version']['is_versioned'] is True for member in plan['members'])
