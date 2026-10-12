"""Versioned policy-bundle normalization for durable suite state."""
from copy import deepcopy

from .config import PolicyError, require


SCHEMA_VERSION = 2


def _legacy_dimensions(config):
    legacy = config.pop('TYPECHAIN', None)
    present = ('HOST_SERVICES' in config, 'CONTAINER_POLICY' in config)
    if all(present):
        # Schema 1 always serialized both effective fields. They are the
        # authority: TYPECHAIN=0 may only be the old injected default.
        return
    if legacy is None and not any(present):
        raise PolicyError('Schema 1 policy lacks host/container policy dimensions')
    if legacy is None or any(present):
        raise PolicyError('Ambiguous schema 1 TYPECHAIN policy; refusing to guess')
    require(legacy in ('0', '1', '2'), 'Invalid schema 1 TYPECHAIN value')
    config['HOST_SERVICES'] = 'false' if legacy == '1' else 'true'
    config['CONTAINER_POLICY'] = 'off' if legacy == '0' else 'restrict'


def migrate_policy(policy):
    """Return a schema-2 bundle without changing its caller-owned snapshots."""
    require(isinstance(policy, dict), 'Invalid policy state')
    result = deepcopy(policy)
    version = result.get('schema', 1)
    require(type(version) is int and version in (1, SCHEMA_VERSION),
            f'Unsupported policy schema: {version!r}')
    config = result.get('config')
    require(isinstance(config, dict), 'Policy state has no configuration')
    config = dict(config)
    if version == 1:
        _legacy_dimensions(config)
        # Config bundles already contain the effective resolved source list
        # and parsed ACL; replaying either input source during migration would
        # make old state depend on current DNS/filesystem contents.
        require(not config.get('BYPASS_SOURCE_DOMAINS'),
                'Schema 1 policy contains unresolved bypass domains; refusing DNS migration')
        config['ACCESS_POLICY'] = ''
        result['config'] = config
        result['schema'] = SCHEMA_VERSION
    else:
        require('TYPECHAIN' not in config, 'Schema 2 policy must not contain TYPECHAIN')
        require(not config.get('ACCESS_POLICY'), 'Schema 2 policy must store parsed ACL, not an ACCESS_POLICY path')
        require(not config.get('BYPASS_SOURCE_DOMAINS'),
                'Schema 2 policy must not contain unresolved bypass domains')
    return result


def migrate_record(name, record):
    """Migrate bundle fields in a store record in memory, never its snapshot."""
    if record is None:
        return None
    if name in ('current', 'persisted'):
        return migrate_policy(record)
    if name == 'pending':
        result = deepcopy(record)
        for key in ('previous', 'candidate'):
            if result.get(key) is not None:
                result[key] = migrate_policy(result[key])
        return result
    return record


def canonical_for_storage(name, record):
    """Upgrade policy files only at confirmed-state write points."""
    if name in ('current', 'persisted'):
        return migrate_policy(record)
    return record
