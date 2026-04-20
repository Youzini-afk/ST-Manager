import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.data.ui_store import get_beautify_library, set_beautify_library
from core.services.beautify_service import BeautifyService


def test_set_beautify_library_normalizes_package_variant_and_wallpaper_shape():
    ui_data = {}

    changed = set_beautify_library(
        ui_data,
        {
            'packages': {
                ' pkg_demo ': {
                    'id': ' pkg_demo ',
                    'name': ' Demo Theme ',
                    'variants': {
                        ' var_mobile ': {
                            'id': ' var_mobile ',
                            'platform': ' MOBILE ',
                            'theme_name': ' Demo Theme ',
                            'theme_file': 'data\\library\\beautify\\packages\\pkg_demo\\themes\\mobile.json',
                            'wallpaper_ids': [' wp_1 ', '', 'wp_1'],
                            'preview_hint': {
                                'needs_platform_review': 'yes',
                                'preview_accuracy': 'unknown',
                            },
                        },
                    },
                    'wallpapers': {
                        ' wp_1 ': {
                            'id': ' wp_1 ',
                            'variant_id': ' var_mobile ',
                            'file': 'data\\library\\beautify\\packages\\pkg_demo\\wallpapers\\mobile-1.webp',
                            'filename': ' demo.webp ',
                            'width': '1080',
                            'height': '1920',
                            'mtime': '123',
                        },
                    },
                },
            },
        },
    )

    assert changed is True

    payload = get_beautify_library(ui_data)
    package_info = payload['packages']['pkg_demo']
    variant_info = package_info['variants']['var_mobile']
    wallpaper_info = package_info['wallpapers']['wp_1']

    assert package_info['name'] == 'Demo Theme'
    assert variant_info['platform'] == 'mobile'
    assert variant_info['theme_file'] == 'data/library/beautify/packages/pkg_demo/themes/mobile.json'
    assert variant_info['wallpaper_ids'] == ['wp_1']
    assert variant_info['preview_hint']['needs_platform_review'] is True
    assert variant_info['preview_hint']['preview_accuracy'] == 'approx'
    assert wallpaper_info['variant_id'] == 'var_mobile'
    assert wallpaper_info['file'] == 'data/library/beautify/packages/pkg_demo/wallpapers/mobile-1.webp'
    assert wallpaper_info['filename'] == 'demo.webp'
    assert wallpaper_info['width'] == 1080
    assert wallpaper_info['height'] == 1920
    assert wallpaper_info['mtime'] == 123
    assert payload['updated_at'] > 0


def test_import_theme_creates_package_from_theme_name_and_detects_mobile_platform(tmp_path):
    library_root = tmp_path / 'data' / 'library' / 'beautify'
    ui_data = {}
    saved_payloads = []

    source_file = tmp_path / 'crying_移动端.json'
    source_file.write_text(
        json.dumps(
            {
                'name': 'crying',
                'main_text_color': '#ffffff',
                'custom_css': '.mes { color: red; }',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    service = BeautifyService(
        library_root=library_root,
        ui_data_loader=lambda: ui_data,
        ui_data_saver=lambda data: saved_payloads.append(json.loads(json.dumps(data, ensure_ascii=False))),
    )

    result = service.import_theme(str(source_file))

    assert result['package']['name'] == 'crying'
    assert result['package']['id'].startswith('pkg_')
    assert result['variant']['platform'] == 'mobile'
    assert result['variant']['theme_name'] == 'crying'
    assert result['variant']['preview_hint']['needs_platform_review'] is False
    assert result['variant']['preview_hint']['preview_accuracy'] == 'approx'

    saved_library = get_beautify_library(saved_payloads[-1])
    saved_package = saved_library['packages'][result['package']['id']]
    saved_variant = saved_package['variants'][result['variant']['id']]

    assert saved_variant['theme_file'].endswith('/themes/mobile.json')
    assert (tmp_path / saved_variant['theme_file']).exists()
    assert json.loads((tmp_path / saved_variant['theme_file']).read_text(encoding='utf-8'))['name'] == 'crying'


def test_import_theme_defaults_to_dual_and_marks_platform_review_when_guess_is_unclear(tmp_path):
    library_root = tmp_path / 'data' / 'library' / 'beautify'
    ui_data = {}

    source_file = tmp_path / 'mystery.json'
    source_file.write_text(
        json.dumps(
            {
                'name': '梧桐树下',
                'main_text_color': '#ffffff',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    service = BeautifyService(
        library_root=library_root,
        ui_data_loader=lambda: ui_data,
        ui_data_saver=lambda data: ui_data.clear() or ui_data.update(data),
    )

    result = service.import_theme(str(source_file))

    assert result['variant']['platform'] == 'dual'
    assert result['variant']['preview_hint']['needs_platform_review'] is True
    assert result['variant']['preview_hint']['preview_accuracy'] == 'base'


def test_import_wallpaper_binds_file_to_specific_variant_and_persists_dimensions(tmp_path):
    library_root = tmp_path / 'data' / 'library' / 'beautify'
    ui_data = {}

    theme_file = tmp_path / 'demo_pc.json'
    theme_file.write_text(
        json.dumps({'name': 'Demo PC', 'main_text_color': '#fff'}, ensure_ascii=False),
        encoding='utf-8',
    )

    wallpaper_file = tmp_path / 'wallpaper.png'
    Image.new('RGB', (1440, 900), '#334455').save(wallpaper_file)

    service = BeautifyService(
        library_root=library_root,
        ui_data_loader=lambda: ui_data,
        ui_data_saver=lambda data: ui_data.clear() or ui_data.update(data),
    )
    imported_theme = service.import_theme(str(theme_file), platform='pc')

    result = service.import_wallpaper(
        imported_theme['package']['id'],
        imported_theme['variant']['id'],
        str(wallpaper_file),
    )

    assert result['wallpaper']['variant_id'] == imported_theme['variant']['id']
    assert result['wallpaper']['width'] == 1440
    assert result['wallpaper']['height'] == 900
    assert result['wallpaper']['file'].endswith('/wallpapers/wallpaper.png')
    assert (tmp_path / result['wallpaper']['file']).exists()

    package_info = service.get_package(imported_theme['package']['id'])
    assert package_info['variants'][imported_theme['variant']['id']]['wallpaper_ids'] == [result['wallpaper']['id']]


def test_beautify_package_shape_no_longer_requires_install_state(tmp_path):
    library_root = tmp_path / 'data' / 'library' / 'beautify'
    ui_data = {}
    theme_file = tmp_path / 'theme_pc.json'
    theme_file.write_text(
        json.dumps({'name': 'Demo', 'main_text_color': '#fff'}, ensure_ascii=False),
        encoding='utf-8',
    )
    wallpaper_file = tmp_path / 'bg.webp'
    Image.new('RGB', (1280, 720), '#223344').save(wallpaper_file)

    service = BeautifyService(
        library_root=library_root,
        ui_data_loader=lambda: ui_data,
        ui_data_saver=lambda data: ui_data.clear() or ui_data.update(data),
    )
    imported_theme = service.import_theme(str(theme_file), platform='pc')
    imported_wallpaper = service.import_wallpaper(
        imported_theme['package']['id'],
        imported_theme['variant']['id'],
        str(wallpaper_file),
    )

    package_info = service.get_package(imported_theme['package']['id'])
    assert 'install_state' not in package_info


def test_beautify_service_removes_dead_st_client_and_wallpaper_index_helpers():
    source = (ROOT / 'core/services/beautify_service.py').read_text(encoding='utf-8')

    assert 'self.st_client =' not in source
    assert '_wallpaper_index_for_variant' not in source
