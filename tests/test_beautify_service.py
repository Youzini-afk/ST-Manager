import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.data.ui_store import get_beautify_library, set_beautify_library
from core.services.beautify_service import BeautifyService


def _build_service(tmp_path, ui_data):
    library_root = tmp_path / 'data' / 'library' / 'beautify'
    return BeautifyService(
        library_root=library_root,
        ui_data_loader=lambda: ui_data,
        ui_data_saver=lambda data: ui_data.clear() or ui_data.update(data),
    )


def _import_theme_for_package(service, tmp_path, filename='theme_pc.json', name='Demo', platform='pc'):
    theme_file = tmp_path / filename
    theme_file.write_text(
        json.dumps({'name': name, 'main_text_color': '#fff'}, ensure_ascii=False),
        encoding='utf-8',
    )
    return service.import_theme(str(theme_file), platform=platform)


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


def test_set_beautify_library_normalizes_global_settings_screenshots_and_identity_overrides():
    ui_data = {}

    changed = set_beautify_library(
        ui_data,
        {
            'global_settings': {
                'wallpaper': {
                    'file': 'data\\library\\beautify\\global\\wallpapers\\main.webp',
                    'filename': ' main.webp ',
                    'width': '1080',
                    'height': '1920',
                    'mtime': '456',
                },
                'identities': {
                    'character': {
                        'name': ' Alice ',
                        'avatar_file': 'data\\avatars\\alice.png',
                    },
                    'user': {
                        'name': ' Bob ',
                        'avatar_file': 'data\\avatars\\bob.png',
                    },
                },
            },
            'packages': {
                ' pkg_demo ': {
                    'id': ' pkg_demo ',
                    'name': ' Demo Theme ',
                    'screenshots': {
                        ' shot_1 ': {
                            'id': ' shot_1 ',
                            'file': 'data\\library\\beautify\\packages\\pkg_demo\\screens\\01.webp',
                            'filename': ' 01.webp ',
                            'width': '1280',
                            'height': '720',
                            'mtime': '789',
                        },
                        '': {
                            'file': 'ignored.webp',
                        },
                    },
                    'identity_overrides': {
                        'character': {
                            'name': ' Carol ',
                            'avatar_file': 'data\\avatars\\carol.png',
                        },
                        'user': {
                            'name': ' Dave ',
                            'avatar_file': 'data\\avatars\\dave.png',
                        },
                    },
                    'variants': {},
                    'wallpapers': {},
                },
            },
        },
    )

    assert changed is True

    payload = get_beautify_library(ui_data)
    global_settings = payload['global_settings']
    global_wallpaper = global_settings['wallpaper']
    package_info = payload['packages']['pkg_demo']
    screenshot_info = package_info['screenshots']['shot_1']

    assert global_wallpaper['file'] == 'data/library/beautify/global/wallpapers/main.webp'
    assert global_wallpaper['filename'] == 'main.webp'
    assert global_wallpaper['width'] == 1080
    assert global_wallpaper['height'] == 1920
    assert global_wallpaper['mtime'] == 456
    assert global_settings['identities']['character'] == {
        'name': 'Alice',
        'avatar_file': 'data/avatars/alice.png',
    }
    assert global_settings['identities']['user'] == {
        'name': 'Bob',
        'avatar_file': 'data/avatars/bob.png',
    }
    assert screenshot_info == {
        'id': 'shot_1',
        'file': 'data/library/beautify/packages/pkg_demo/screens/01.webp',
        'filename': '01.webp',
        'width': 1280,
        'height': 720,
        'mtime': 789,
    }
    assert package_info['identity_overrides']['character'] == {
        'name': 'Carol',
        'avatar_file': 'data/avatars/carol.png',
    }
    assert package_info['identity_overrides']['user'] == {
        'name': 'Dave',
        'avatar_file': 'data/avatars/dave.png',
    }


def test_set_beautify_library_global_settings_affects_equality():
    ui_data = {}
    base_payload = {
        'global_settings': {
            'wallpaper': {
                'file': 'data\\library\\beautify\\global\\wallpapers\\main.webp',
                'filename': ' main.webp ',
                'width': '1080',
                'height': '1920',
                'mtime': '456',
            },
            'identities': {
                'character': {
                    'name': ' Alice ',
                    'avatar_file': 'data\\avatars\\alice.png',
                },
                'user': {
                    'name': ' Bob ',
                    'avatar_file': 'data\\avatars\\bob.png',
                },
            },
        },
        'packages': {
            'pkg_demo': {
                'id': 'pkg_demo',
                'name': 'Demo Theme',
                'variants': {},
                'wallpapers': {},
            },
        },
    }

    assert set_beautify_library(ui_data, base_payload) is True
    assert set_beautify_library(
        ui_data,
        {
            'global_settings': {
                'wallpaper': {
                    'file': 'data/library/beautify/global/wallpapers/main.webp',
                    'filename': 'main.webp',
                    'width': 1080,
                    'height': 1920,
                    'mtime': 456,
                },
                'identities': {
                    'character': {
                        'name': 'Alice',
                        'avatar_file': 'data/avatars/alice.png',
                    },
                    'user': {
                        'name': 'Bob',
                        'avatar_file': 'data/avatars/bob.png',
                    },
                },
            },
            'packages': {
                'pkg_demo': {
                    'id': 'pkg_demo',
                    'name': 'Demo Theme',
                    'variants': {},
                    'wallpapers': {},
                },
            },
        },
    ) is False

    assert set_beautify_library(
        ui_data,
        {
            'global_settings': {
                'wallpaper': {
                    'file': 'data/library/beautify/global/wallpapers/updated.webp',
                    'filename': 'updated.webp',
                    'width': 1080,
                    'height': 1920,
                    'mtime': 457,
                },
                'identities': {
                    'character': {
                        'name': 'Alice',
                        'avatar_file': 'data/avatars/alice.png',
                    },
                    'user': {
                        'name': 'Bob',
                        'avatar_file': 'data/avatars/bob.png',
                    },
                },
            },
            'packages': {
                'pkg_demo': {
                    'id': 'pkg_demo',
                    'name': 'Demo Theme',
                    'variants': {},
                    'wallpapers': {},
                },
            },
        },
    ) is True


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


def test_import_global_wallpaper_replaces_stable_slot_and_updates_global_settings(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    first_wallpaper = tmp_path / 'first-wallpaper.png'
    second_wallpaper = tmp_path / 'second-wallpaper.png'
    Image.new('RGB', (1080, 1920), '#112233').save(first_wallpaper)
    Image.new('RGB', (720, 1280), '#445566').save(second_wallpaper)

    first_result = service.import_global_wallpaper(str(first_wallpaper))
    second_result = service.import_global_wallpaper(str(second_wallpaper))

    assert first_result['wallpaper']['file'] == 'data/library/beautify/global/wallpapers/wallpaper.png'
    assert second_result['wallpaper']['file'] == 'data/library/beautify/global/wallpapers/wallpaper.png'
    assert second_result['wallpaper']['filename'] == 'wallpaper.png'
    assert second_result['wallpaper']['width'] == 720
    assert second_result['wallpaper']['height'] == 1280
    assert (tmp_path / second_result['wallpaper']['file']).exists()

    saved_library = get_beautify_library(ui_data)
    assert saved_library['global_settings']['wallpaper'] == second_result['wallpaper']


def test_get_global_settings_returns_saved_wallpaper_and_identities(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    wallpaper_file = tmp_path / 'global-wallpaper.png'
    character_avatar = tmp_path / 'character.png'
    Image.new('RGB', (1080, 1920), '#123456').save(wallpaper_file)
    Image.new('RGB', (256, 256), '#654321').save(character_avatar)

    imported_wallpaper = service.import_global_wallpaper(str(wallpaper_file))
    service.import_global_avatar('character', str(character_avatar))
    service.update_global_settings({'character_name': 'Alice'})

    settings = service.get_global_settings()

    assert settings['wallpaper'] == imported_wallpaper['wallpaper']
    assert settings['identities']['character'] == {
        'name': 'Alice',
        'avatar_file': 'data/library/beautify/global/avatars/character.png',
    }
    assert settings['identities']['user'] == {'name': '', 'avatar_file': ''}


def test_import_screenshot_and_update_package_identities_persist_package_detail_fields(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Screenshot Demo')

    screenshot_file = tmp_path / 'preview shot.png'
    Image.new('RGB', (1600, 900), '#224466').save(screenshot_file)

    screenshot_result = service.import_screenshot(imported_theme['package']['id'], str(screenshot_file))
    updated_package = service.update_package_identities(
        imported_theme['package']['id'],
        {
            'character_name': 'Alice',
            'user_name': 'Bob',
        },
    )

    package_summary = service.list_packages()[0]
    package_detail = service.get_package(imported_theme['package']['id'])

    assert package_summary['screenshot_count'] == 1
    assert screenshot_result['screenshot']['file'].endswith('/screenshots/preview shot.png')
    assert screenshot_result['screenshot']['width'] == 1600
    assert screenshot_result['screenshot']['height'] == 900
    assert package_detail['screenshots'] == {screenshot_result['screenshot']['id']: screenshot_result['screenshot']}
    assert package_detail['identity_overrides'] == {
        'character': {'name': 'Alice', 'avatar_file': ''},
        'user': {'name': 'Bob', 'avatar_file': ''},
    }
    assert updated_package['identity_overrides'] == package_detail['identity_overrides']


def test_import_global_avatar_and_import_package_avatar_use_stable_slots(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Avatar Demo')

    global_avatar = tmp_path / 'global-character.png'
    package_avatar = tmp_path / 'package-user.png'
    Image.new('RGB', (400, 400), '#884422').save(global_avatar)
    Image.new('RGB', (512, 512), '#228844').save(package_avatar)

    global_result = service.import_global_avatar('character', str(global_avatar))
    package_result = service.import_package_avatar(imported_theme['package']['id'], 'user', str(package_avatar))

    assert global_result['identity']['avatar_file'] == 'data/library/beautify/global/avatars/character.png'
    assert package_result['identity']['avatar_file'].endswith('/avatars/user.png')
    assert (tmp_path / global_result['identity']['avatar_file']).exists()
    assert (tmp_path / package_result['identity']['avatar_file']).exists()

    package_detail = service.get_package(imported_theme['package']['id'])
    assert package_detail['identity_overrides']['user'] == package_result['identity']
    assert get_beautify_library(ui_data)['global_settings']['identities']['character'] == global_result['identity']


def test_import_global_avatar_replaces_slot_and_removes_stale_old_extension_file(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    first_avatar = tmp_path / 'character.png'
    second_avatar = tmp_path / 'character.webp'
    Image.new('RGB', (300, 300), '#335577').save(first_avatar)
    Image.new('RGB', (320, 320), '#775533').save(second_avatar)

    first_result = service.import_global_avatar('character', str(first_avatar))
    second_result = service.import_global_avatar('character', str(second_avatar))

    assert first_result['identity']['avatar_file'] == 'data/library/beautify/global/avatars/character.png'
    assert second_result['identity']['avatar_file'] == 'data/library/beautify/global/avatars/character.webp'
    assert (tmp_path / 'data' / 'library' / 'beautify' / 'global' / 'avatars' / 'character.png').exists() is False
    assert (tmp_path / 'data' / 'library' / 'beautify' / 'global' / 'avatars' / 'character.webp').exists()


def test_update_global_settings_can_clear_names_and_avatar_values(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    character_avatar = tmp_path / 'character.png'
    user_avatar = tmp_path / 'user.png'
    wallpaper_file = tmp_path / 'wallpaper.png'
    Image.new('RGB', (300, 300), '#335577').save(character_avatar)
    Image.new('RGB', (300, 300), '#775533').save(user_avatar)
    Image.new('RGB', (1080, 1920), '#112244').save(wallpaper_file)

    service.import_global_wallpaper(str(wallpaper_file))
    service.import_global_avatar('character', str(character_avatar))
    service.import_global_avatar('user', str(user_avatar))
    updated_settings = service.update_global_settings(
        {
            'character_name': 'Alice',
            'user_name': 'Bob',
        }
    )

    cleared_settings = service.update_global_settings(
        {
            'clear_wallpaper': True,
            'character_name': '   ',
            'user_name': None,
            'clear_character_avatar': True,
            'clear_user_avatar': True,
        }
    )

    assert updated_settings['identities']['character']['name'] == 'Alice'
    assert updated_settings['identities']['user']['avatar_file'].endswith('/global/avatars/user.png')
    assert updated_settings['wallpaper']['file'].endswith('/global/wallpapers/wallpaper.png')
    assert cleared_settings['wallpaper'] == {
        'file': '',
        'filename': '',
        'width': 0,
        'height': 0,
        'mtime': 0,
    }
    assert cleared_settings['identities'] == {
        'character': {'name': '', 'avatar_file': ''},
        'user': {'name': '', 'avatar_file': ''},
    }
    assert (tmp_path / 'data' / 'library' / 'beautify' / 'global' / 'wallpapers' / 'wallpaper.png').exists() is False
    assert (tmp_path / 'data' / 'library' / 'beautify' / 'global' / 'avatars' / 'character.png').exists() is False
    assert (tmp_path / 'data' / 'library' / 'beautify' / 'global' / 'avatars' / 'user.png').exists() is False


def test_update_global_settings_ignores_nested_identity_avatar_payloads(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    character_avatar = tmp_path / 'character.png'
    Image.new('RGB', (300, 300), '#335577').save(character_avatar)
    service.import_global_avatar('character', str(character_avatar))

    updated_settings = service.update_global_settings(
        {
            'character_name': 'Alice',
            'identities': {'character': {'avatar_file': ''}},
            'avatar_file': '',
        }
    )

    assert updated_settings['identities']['character']['name'] == 'Alice'
    assert updated_settings['identities']['character']['avatar_file'].endswith('/global/avatars/character.png')


def test_update_global_settings_ignores_non_boolean_clear_flags(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    character_avatar = tmp_path / 'character.png'
    wallpaper_file = tmp_path / 'wallpaper.png'
    Image.new('RGB', (300, 300), '#335577').save(character_avatar)
    Image.new('RGB', (1080, 1920), '#112244').save(wallpaper_file)

    service.import_global_wallpaper(str(wallpaper_file))
    service.import_global_avatar('character', str(character_avatar))
    updated_settings = service.update_global_settings(
        {
            'character_name': 'Alice',
            'clear_wallpaper': 'false',
            'clear_character_avatar': 1,
        }
    )

    assert updated_settings['wallpaper']['file'].endswith('/global/wallpapers/wallpaper.png')
    assert updated_settings['identities']['character']['name'] == 'Alice'
    assert updated_settings['identities']['character']['avatar_file'].endswith('/global/avatars/character.png')


def test_update_package_identities_uses_flat_payload_and_clear_flags(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Identity Demo')

    avatar_file = tmp_path / 'package-user.png'
    Image.new('RGB', (512, 512), '#228844').save(avatar_file)
    service.import_package_avatar(imported_theme['package']['id'], 'user', str(avatar_file))

    updated_package = service.update_package_identities(
        imported_theme['package']['id'],
        {
            'character_name': 'Hero',
            'user_name': '',
            'clear_user_avatar': True,
            'user': {'avatar_file': 'should/not/pass.png'},
        },
    )

    assert updated_package['identity_overrides'] == {
        'character': {'name': 'Hero', 'avatar_file': ''},
        'user': {'name': '', 'avatar_file': ''},
    }


def test_update_package_identities_clear_flag_removes_package_avatar_file(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Avatar Clear Demo')

    avatar_file = tmp_path / 'package-character.png'
    Image.new('RGB', (512, 512), '#228844').save(avatar_file)
    imported_avatar = service.import_package_avatar(imported_theme['package']['id'], 'character', str(avatar_file))
    saved_avatar_path = tmp_path / imported_avatar['identity']['avatar_file']

    updated_package = service.update_package_identities(
        imported_theme['package']['id'],
        {
            'clear_character_avatar': True,
        },
    )

    assert saved_avatar_path.exists() is False
    assert updated_package['identity_overrides']['character']['avatar_file'] == ''


def test_update_package_identities_ignores_non_boolean_clear_flags(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Safe Flag Demo')

    avatar_file = tmp_path / 'package-user.png'
    Image.new('RGB', (512, 512), '#228844').save(avatar_file)
    imported_avatar = service.import_package_avatar(imported_theme['package']['id'], 'user', str(avatar_file))
    saved_avatar_path = tmp_path / imported_avatar['identity']['avatar_file']

    updated_package = service.update_package_identities(
        imported_theme['package']['id'],
        {
            'user_name': 'Player',
            'clear_user_avatar': 'false',
        },
    )

    assert saved_avatar_path.exists()
    assert updated_package['identity_overrides']['user']['name'] == 'Player'
    assert updated_package['identity_overrides']['user']['avatar_file'].endswith('/avatars/user.png')


def test_import_global_wallpaper_raises_value_error_for_invalid_image(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    invalid_file = tmp_path / 'invalid-wallpaper.png'
    invalid_file.write_bytes(b'not-an-image')

    try:
        service.import_global_wallpaper(str(invalid_file))
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert str(exc) == '壁纸文件无效'


def test_invalid_global_wallpaper_replacement_preserves_existing_asset(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    valid_wallpaper = tmp_path / 'valid-wallpaper.png'
    invalid_wallpaper = tmp_path / 'invalid-wallpaper.png'
    Image.new('RGB', (1080, 1920), '#112244').save(valid_wallpaper)
    invalid_wallpaper.write_bytes(b'not-an-image')

    first_result = service.import_global_wallpaper(str(valid_wallpaper))
    original_path = tmp_path / first_result['wallpaper']['file']
    original_mtime = first_result['wallpaper']['mtime']

    try:
        service.import_global_wallpaper(str(invalid_wallpaper))
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert str(exc) == '壁纸文件无效'

    settings = service.get_global_settings()
    assert original_path.exists()
    assert settings['wallpaper']['file'] == first_result['wallpaper']['file']
    assert settings['wallpaper']['mtime'] == original_mtime


def test_import_screenshot_raises_value_error_for_invalid_image(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Invalid Screenshot Demo')

    invalid_file = tmp_path / 'invalid-screenshot.png'
    invalid_file.write_bytes(b'not-an-image')

    try:
        service.import_screenshot(imported_theme['package']['id'], str(invalid_file))
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert str(exc) == '截图文件无效'


def test_import_wallpaper_raises_value_error_for_invalid_image_and_removes_copied_file(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Invalid Wallpaper Demo')

    invalid_file = tmp_path / 'invalid-wallpaper.png'
    invalid_file.write_bytes(b'not-an-image')
    wallpapers_dir = tmp_path / 'data' / 'library' / 'beautify' / 'packages' / imported_theme['package']['id'] / 'wallpapers'

    try:
        service.import_wallpaper(imported_theme['package']['id'], imported_theme['variant']['id'], str(invalid_file))
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert str(exc) == '壁纸文件无效'

    assert wallpapers_dir.exists() is False or list(wallpapers_dir.iterdir()) == []


def test_import_global_avatar_raises_value_error_for_invalid_image(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    invalid_file = tmp_path / 'invalid-avatar.png'
    invalid_file.write_bytes(b'not-an-image')

    try:
        service.import_global_avatar('character', str(invalid_file))
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert str(exc) == '头像文件无效'


def test_invalid_global_avatar_replacement_preserves_existing_asset(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)

    valid_avatar = tmp_path / 'valid-avatar.png'
    invalid_avatar = tmp_path / 'invalid-avatar.png'
    Image.new('RGB', (300, 300), '#335577').save(valid_avatar)
    invalid_avatar.write_bytes(b'not-an-image')

    first_result = service.import_global_avatar('character', str(valid_avatar))
    original_path = tmp_path / first_result['identity']['avatar_file']

    try:
        service.import_global_avatar('character', str(invalid_avatar))
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert str(exc) == '头像文件无效'

    settings = service.get_global_settings()
    assert original_path.exists()
    assert settings['identities']['character']['avatar_file'] == first_result['identity']['avatar_file']


def test_invalid_package_avatar_replacement_preserves_existing_asset(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Package Avatar Preserve Demo')

    valid_avatar = tmp_path / 'valid-package-avatar.png'
    invalid_avatar = tmp_path / 'invalid-package-avatar.png'
    Image.new('RGB', (300, 300), '#335577').save(valid_avatar)
    invalid_avatar.write_bytes(b'not-an-image')

    first_result = service.import_package_avatar(imported_theme['package']['id'], 'user', str(valid_avatar))
    original_path = tmp_path / first_result['identity']['avatar_file']

    try:
        service.import_package_avatar(imported_theme['package']['id'], 'user', str(invalid_avatar))
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert str(exc) == '头像文件无效'

    package_detail = service.get_package(imported_theme['package']['id'])
    assert original_path.exists()
    assert package_detail['identity_overrides']['user']['avatar_file'] == first_result['identity']['avatar_file']


def test_get_package_ignores_tampered_theme_file_outside_library(tmp_path):
    external_theme = tmp_path / 'external-theme.json'
    external_theme.write_text(json.dumps({'name': 'External', 'main_text_color': '#f00'}, ensure_ascii=False), encoding='utf-8')

    ui_data = {
        '_beautify_library_v1': {
            'packages': {
                'pkg_demo': {
                    'id': 'pkg_demo',
                    'name': 'Demo',
                    'variants': {
                        'var_pc': {
                            'id': 'var_pc',
                            'platform': 'pc',
                            'theme_name': 'Demo',
                            'theme_file': '../../external-theme.json',
                            'wallpaper_ids': [],
                            'preview_hint': {'needs_platform_review': False, 'preview_accuracy': 'base'},
                        }
                    },
                    'wallpapers': {},
                    'screenshots': {},
                    'identity_overrides': {},
                }
            }
        }
    }
    service = _build_service(tmp_path, ui_data)

    package_detail = service.get_package('pkg_demo')

    assert package_detail['variants']['var_pc']['theme_data'] == {}


def test_import_wallpaper_sanitizes_malicious_source_name(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Wallpaper Name Demo')

    wallpaper_file = tmp_path / 'wallpaper.png'
    Image.new('RGB', (1280, 720), '#223344').save(wallpaper_file)

    result = service.import_wallpaper(
        imported_theme['package']['id'],
        imported_theme['variant']['id'],
        str(wallpaper_file),
        source_name='../../outside.png',
    )
    saved_path = tmp_path / result['wallpaper']['file']

    assert result['wallpaper']['filename'] == 'outside.png'
    assert saved_path.exists()
    assert saved_path.parent.name == 'wallpapers'
    assert '..' not in result['wallpaper']['file']


def test_import_screenshot_sanitizes_windows_style_malicious_source_name(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Screenshot Name Demo')

    screenshot_file = tmp_path / 'shot.png'
    Image.new('RGB', (1280, 720), '#223344').save(screenshot_file)

    result = service.import_screenshot(
        imported_theme['package']['id'],
        str(screenshot_file),
        source_name='..\\..\\outside.png',
    )
    saved_path = tmp_path / result['screenshot']['file']

    assert result['screenshot']['filename'] == 'outside.png'
    assert saved_path.exists()
    assert saved_path.parent.name == 'screenshots'
    assert '..' not in result['screenshot']['file']


def test_remove_asset_file_does_not_delete_file_outside_library_for_malformed_metadata(tmp_path):
    outside_file = tmp_path / 'outside-avatar.png'
    outside_file.write_text('keep me', encoding='utf-8')

    service = _build_service(tmp_path, {})
    service._remove_asset_file('data/library/beautify/../../../outside-avatar.png')

    assert outside_file.exists()


def test_delete_package_removes_package_screenshots_and_avatars_with_directory(tmp_path):
    ui_data = {}
    service = _build_service(tmp_path, ui_data)
    imported_theme = _import_theme_for_package(service, tmp_path, name='Delete Demo')
    package_id = imported_theme['package']['id']

    screenshot_file = tmp_path / 'delete-shot.png'
    avatar_file = tmp_path / 'delete-avatar.png'
    Image.new('RGB', (1280, 720), '#111111').save(screenshot_file)
    Image.new('RGB', (256, 256), '#999999').save(avatar_file)

    screenshot_result = service.import_screenshot(package_id, str(screenshot_file))
    avatar_result = service.import_package_avatar(package_id, 'character', str(avatar_file))
    package_dir = tmp_path / 'data' / 'library' / 'beautify' / 'packages' / package_id

    assert (tmp_path / screenshot_result['screenshot']['file']).exists()
    assert (tmp_path / avatar_result['identity']['avatar_file']).exists()
    assert package_dir.exists()

    deleted = service.delete_package(package_id)

    assert deleted is True
    assert service.get_package(package_id) is None
    assert package_dir.exists() is False
    assert (tmp_path / screenshot_result['screenshot']['file']).exists() is False
    assert (tmp_path / avatar_result['identity']['avatar_file']).exists() is False


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
