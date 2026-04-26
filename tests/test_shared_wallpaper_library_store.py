import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.data.ui_store import get_shared_wallpaper_library, set_shared_wallpaper_library


def test_set_shared_wallpaper_library_normalizes_items_and_selection_ids():
    ui_data = {}

    changed = set_shared_wallpaper_library(
        ui_data,
        {
            'items': {
                ' wallpaper-a ': {
                    'file': 'assets\\wallpapers\\alpha.png',
                    'filename': ' alpha.png ',
                    'width': '1920.9',
                    'height': '1080',
                    'mtime': '1712345678',
                    'created_at': '1712000000',
                    'origin_package_id': 123,
                    'origin_variant_id': ' v-main ',
                },
                'wallpaper-b': {
                    'id': 'ignored-id',
                    'source_type': 'package_embedded',
                    'file': '/pkg/demo/beta.jpg/',
                    'filename': 'beta.jpg',
                    'width': None,
                    'height': 'bad',
                    'mtime': -10,
                    'created_at': False,
                    'origin_package_id': None,
                    'origin_variant_id': 'variant-b',
                },
            },
            'manager_wallpaper_id': 'missing-id',
            'preview_wallpaper_id': ' wallpaper-b ',
        },
    )

    assert changed is True

    payload = get_shared_wallpaper_library(ui_data)
    assert sorted(payload.keys()) == ['items', 'manager_wallpaper_id', 'preview_wallpaper_id', 'updated_at']
    assert sorted(payload['items'].keys()) == ['wallpaper-a', 'wallpaper-b']
    assert payload['manager_wallpaper_id'] == ''
    assert payload['preview_wallpaper_id'] == 'wallpaper-b'
    assert payload['updated_at'] > 0

    assert payload['items']['wallpaper-a'] == {
        'id': 'wallpaper-a',
        'source_type': 'imported',
        'file': 'assets/wallpapers/alpha.png',
        'filename': 'alpha.png',
        'width': 1920,
        'height': 1080,
        'mtime': 1712345678,
        'created_at': 1712000000,
        'origin_package_id': '123',
        'origin_variant_id': 'v-main',
    }
    assert payload['items']['wallpaper-b'] == {
        'id': 'wallpaper-b',
        'source_type': 'package_embedded',
        'file': 'pkg/demo/beta.jpg',
        'filename': 'beta.jpg',
        'width': 0,
        'height': 0,
        'mtime': 0,
        'created_at': 0,
        'origin_package_id': '',
        'origin_variant_id': 'variant-b',
    }


def test_set_shared_wallpaper_library_equivalent_payload_is_noop_for_existing_dict():
    ui_data = {}

    assert set_shared_wallpaper_library(
        ui_data,
        {
            'items': {
                'wallpaper-a': {
                    'file': 'assets/wallpapers/alpha.png',
                    'filename': 'alpha.png',
                }
            },
            'manager_wallpaper_id': 'wallpaper-a',
            'preview_wallpaper_id': 'wallpaper-a',
        },
    ) is True

    first_updated_at = ui_data['_shared_wallpaper_library_v1']['updated_at']

    assert set_shared_wallpaper_library(
        ui_data,
        {
            'items': {
                ' wallpaper-a ': {
                    'source_type': 'unknown',
                    'file': 'assets\\wallpapers\\alpha.png',
                    'filename': ' alpha.png ',
                    'width': 0,
                    'height': 0,
                    'mtime': 0,
                    'created_at': 0,
                    'origin_package_id': '',
                    'origin_variant_id': '',
                }
            },
            'manager_wallpaper_id': ' wallpaper-a ',
            'preview_wallpaper_id': 'wallpaper-a',
            'updated_at': first_updated_at + 100,
        },
    ) is False
    assert ui_data['_shared_wallpaper_library_v1']['updated_at'] == first_updated_at


def test_set_shared_wallpaper_library_preserves_builtin_selection_ids_without_persisted_items():
    ui_data = {}

    changed = set_shared_wallpaper_library(
        ui_data,
        {
            'items': {},
            'manager_wallpaper_id': ' builtin:space/stars.png ',
            'preview_wallpaper_id': 'builtin:space/stars.png',
        },
    )

    assert changed is True
    payload = get_shared_wallpaper_library(ui_data)
    assert payload['manager_wallpaper_id'] == 'builtin:space/stars.png'
    assert payload['preview_wallpaper_id'] == 'builtin:space/stars.png'
