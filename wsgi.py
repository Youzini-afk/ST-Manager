import threading

from app import ensure_startup_config, is_running_in_docker
from core import create_app, init_services
from core.auth import is_auth_enabled
from core.deployment import is_server_profile, log_public_auth_warning_if_needed


in_docker = is_running_in_docker()
ensure_startup_config(in_docker)
log_public_auth_warning_if_needed(
    server_profile=is_server_profile(in_docker),
    auth_enabled=is_auth_enabled(),
)
threading.Thread(target=init_services, daemon=True).start()

app = create_app()
