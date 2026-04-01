import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.data.ui_store import get_resource_item_categories, set_resource_item_categories


def test_set_resource_item_categories_normalizes_mode_keys_and_paths():
    ui_data = {}

    changed = set_resource_item_categories(
        ui_data,
        {
            'worldinfo': {
                'D:\\Res\\Lucy\\lorebooks\\book.json': {'category': ' 科幻/赛博朋克 '},
            },
            'presets': {
                'D:\\Res\\Lucy\\presets\\companion.json': {'category': ' 写作/长文 '},
            },
        },
    )

    assert changed is True

    payload = get_resource_item_categories(ui_data)
    assert sorted(payload.keys()) == ['presets', 'updated_at', 'worldinfo']
    assert list(payload['worldinfo'].keys()) == ['d:/res/lucy/lorebooks/book.json']
    assert list(payload['presets'].keys()) == ['d:/res/lucy/presets/companion.json']
    assert payload['worldinfo']['d:/res/lucy/lorebooks/book.json']['category'] == '科幻/赛博朋克'
    assert payload['presets']['d:/res/lucy/presets/companion.json']['category'] == '写作/长文'
    assert payload['updated_at'] > 0


def test_resetting_same_payload_is_noop():
    ui_data = {}
    payload = {'worldinfo': {}, 'presets': {}}

    assert set_resource_item_categories(ui_data, payload) is True
    assert set_resource_item_categories(ui_data, payload) is False
