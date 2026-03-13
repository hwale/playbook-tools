import logging
from pathlib import Path

import yaml
from playbook_schemas.v1.playbook import PlaybookSpecV1

logger = logging.getLogger(__name__)

# Default location: the playbooks/ directory sitting alongside this file.
PLAYBOOKS_DIR = Path(__file__).parent / "playbooks"


def load_playbooks_from_dir(path: Path = PLAYBOOKS_DIR) -> dict[str, PlaybookSpecV1]:
    """
    Scans a directory for *.yaml files and loads each as a PlaybookSpecV1.

    Why file-based instead of hardcoded Python dicts:
      Dropping a new .yaml file = new playbook, no code change or redeploy.
      Files are also git-versionable and human-readable, making it easy to
      review system prompt changes in PRs.

    Why not a database:
      Playbooks are configuration, not user data. They change infrequently,
      are authored by developers, and benefit from being co-located with code
      (version-controlled alongside the codebase). A DB adds infra dependency
      with no real benefit at this scale.

    Loading failures are logged as warnings (not crashes) so a malformed file
    doesn't prevent the other playbooks from loading.
    """
    playbooks: dict[str, PlaybookSpecV1] = {}

    if not path.exists():
        logger.warning("Playbooks directory not found: %s", path)
        return playbooks

    for yaml_file in sorted(path.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            spec = PlaybookSpecV1(**data)
            playbooks[spec.name] = spec
            logger.debug("Loaded playbook: %s", spec.name)
        except Exception:
            logger.warning("Failed to load playbook from %s", yaml_file.name, exc_info=True)

    logger.info("Loaded %d playbook(s): %s", len(playbooks), list(playbooks))
    return playbooks
