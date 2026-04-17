from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_state_settings_form_includes_profile_specific_preset_directories():
    source = read_project_file('static/js/state.js')

    assert 'st_openai_preset_dir:' in source
    assert 'st_textgen_preset_dir:' in source
    assert 'st_instruct_preset_dir:' in source
    assert 'st_context_preset_dir:' in source
    assert 'st_sysprompt_dir:' in source
    assert 'st_reasoning_dir:' in source


def test_settings_template_exposes_profile_specific_preset_directory_inputs():
    source = read_project_file('templates/modals/settings.html')

    assert 'x-model="settingsForm.st_openai_preset_dir"' in source
    assert 'x-model="settingsForm.st_textgen_preset_dir"' in source
    assert 'x-model="settingsForm.st_instruct_preset_dir"' in source
    assert 'x-model="settingsForm.st_context_preset_dir"' in source
    assert 'x-model="settingsForm.st_sysprompt_dir"' in source
    assert 'x-model="settingsForm.st_reasoning_dir"' in source
