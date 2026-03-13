from playbook_schemas.v1.playbook import PlaybookSpecV1

from app.agent.playbook_loader import load_playbooks_from_dir

# Loaded once at import time. To add a playbook: drop a .yaml file in
# services/api/app/agent/playbooks/ and restart the server.
PLAYBOOKS: dict[str, PlaybookSpecV1] = load_playbooks_from_dir()


def get_playbook(name: str) -> PlaybookSpecV1:
    if name not in PLAYBOOKS:
        raise KeyError(f"Unknown playbook: '{name}'. Available: {list(PLAYBOOKS)}")
    return PLAYBOOKS[name]
