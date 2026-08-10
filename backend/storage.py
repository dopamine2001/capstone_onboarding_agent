"""
Simple in-memory storage for generated connectors.
(Swap for a real database later if needed.)
"""
import itertools

_connectors = {}
_id_counter = itertools.count(1)


def save_connector(record):
    connector_id = next(_id_counter)
    record["id"] = connector_id
    _connectors[connector_id] = record
    return record


def get_all():
    return list(_connectors.values())


def get_by_id(connector_id):
    return _connectors.get(connector_id)
