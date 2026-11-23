# Nguyễn Tâm Bình - 2324801030003
import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("overrides", [{"jwt_secret": "short"}, {"jwt_secret": "replace-with-at-least-32-random-bytes"}, {"fernet_key": "invalid"}, {"ssh_port_start": 23000, "ssh_port_end": 22000}, {"scheduler_strategy": "random"}])
def test_invalid_settings_fail_closed(overrides):
    values = {"database_url": "sqlite+pysqlite:///:memory:", "jwt_secret": "local-test-only-000000000000000000000000", "fernet_key": Fernet.generate_key().decode()}
    values.update(overrides)
    with pytest.raises((ValueError, ValidationError)):
        Settings(_env_file=None, **values)
