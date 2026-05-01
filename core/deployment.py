import logging
import os


logger = logging.getLogger(__name__)

TRUE_VALUES = {'1', 'true', 'yes', 'on'}


def env_flag(name: str) -> bool:
    return os.environ.get(name, '').strip().lower() in TRUE_VALUES


def get_env_host():
    value = os.environ.get('HOST', '').strip()
    return value or None


def get_env_port():
    raw = os.environ.get('PORT', '').strip()
    if not raw:
        return None

    try:
        port = int(raw)
    except ValueError:
        logger.warning('Ignoring invalid PORT value: %s', raw)
        return None

    if port <= 0 or port > 65535:
        logger.warning('Ignoring invalid PORT value: %s', raw)
        return None

    return port


def is_server_profile(in_docker: bool = False) -> bool:
    if env_flag('STM_SERVER_PROFILE'):
        return True
    if os.environ.get('PORT', '').strip():
        return True
    return bool(in_docker)


def should_auto_open_browser(in_docker: bool = False) -> bool:
    if env_flag('STM_DISABLE_BROWSER_OPEN'):
        return False
    return not is_server_profile(in_docker)


def build_security_status(*, server_profile: bool, auth_enabled: bool) -> dict:
    public_auth_warning = bool(server_profile and not auth_enabled)
    message = ''
    if public_auth_warning:
        message = (
            '公网部署未启用登录保护。请设置 STM_AUTH_USER / STM_AUTH_PASS '
            '或在设置中配置外网访问账号密码。'
        )

    return {
        'server_profile': bool(server_profile),
        'auth_enabled': bool(auth_enabled),
        'public_auth_warning': public_auth_warning,
        'message': message,
    }


def log_public_auth_warning_if_needed(*, server_profile: bool, auth_enabled: bool):
    if not server_profile or auth_enabled:
        return

    logger.warning(
        '\n'
        '============================================================\n'
        'ST-Manager is running in server profile without login auth.\n'
        'Set STM_AUTH_USER and STM_AUTH_PASS before exposing it publicly.\n'
        '============================================================'
    )
