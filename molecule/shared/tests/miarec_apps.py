"""Checks that the recorder and the screen controller share.

Both applications register in the database when they start, report the state of
their database and Redis connections on the /health endpoint of their REST API,
and answer other REST requests only from the addresses that the playbooks allow.
"""
import pytest
from conftest import (
    hosts_in, name_of, address_of, assert_db_connections_match_tls, db_rows, get_json, host_of,
    host_named, hostname, miarecweb_client, own_address, process_age, untrusted_file, wait_for,
    REST_USER, REST_PASSWORD,
)

# The hosts that MiaRec Web runs on. They may call the REST API.
REST_CLIENT_GROUPS = ["web", "celery"]


def health(host, port):
    """Return (HTTP status, payload) of the local /health endpoint."""
    return get_json(host, f"http://127.0.0.1:{port}/health")


def healthy(host, port):
    status, payload = health(host, port)
    return status == 200 and payload.get("database") == "ok" and payload.get("redis") == "ok"


def assert_health_from_web(host, group, port):
    """The web host reaches the REST API, and the application reaches PostgreSQL and Redis."""
    web = host_of("web")
    status, payload = get_json(web, f"http://{address_of(web, group)}:{port}/health")
    assert status == 200, f"Unexpected health status {status}: {payload}"
    assert payload.get("database") == "ok", f"Unexpected database status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"


def assert_rest_api_allows(host, group, port, client_group, version):
    """A MiaRec Web host calls the REST API and gets the version of the running application."""
    client = host_of(client_group)
    url = f"http://{address_of(client, group)}:{port}/api/version.json"
    status, payload = get_json(client, url, REST_USER, REST_PASSWORD)
    assert status == 200, f"The {client_group} host cannot call the REST API: {status} {payload}"
    assert payload["data"]["version"] == version


def other_hosts(group):
    """Return the hosts that may not call the REST API of a group.

    They run no MiaRec Web, and they are not the application host itself, which
    reaches its own REST API over the loopback interface.
    """
    allowed = {name for g in REST_CLIENT_GROUPS + [group] for name in hosts_in(g)}
    return [name for name in hosts_in("all") if name not in allowed]


def other_hosts_params(group):
    """Return pytest parameters for other_hosts(), or one skipped parameter when there is none."""
    return other_hosts(group) or [pytest.param(None, marks=pytest.mark.skip(reason="No other host"))]


def assert_rest_api_rejects(host, group, port, client_name):
    """A host without MiaRec Web cannot call the REST API, even with the right password."""
    client = host_named(client_name)
    url = f"http://{address_of(client, group)}:{port}/api/version.json"
    status, _ = get_json(client, url, REST_USER, REST_PASSWORD)
    assert status == 401, f"{client_name} called the REST API: HTTP {status}"


def assert_registered(host, table, where, comm):
    """The running application wrote its start time to the database.

    The row is not older than the process, so the process that runs now wrote it.
    """
    rows = db_rows(
        miarecweb_client(),
        f"SELECT extract(epoch FROM now() - start_time) AS age FROM {table} "
        f"WHERE {where} AND host_name = %s AND stop_time IS NULL",
        [hostname(host)],
    )
    assert len(rows) == 1, f"Expected one running {comm} on {hostname(host)} in {table}: {rows}"
    # One second of tolerance for rounding
    assert float(rows[0]["age"]) <= process_age(host, comm) + 1, \
        f"{table} has a start time from before the running {comm} process started"


def assert_db_connections(host, group):
    """The open database connections of the application use TLS exactly when the scenario has TLS."""
    inspector = miarecweb_client()
    address = "127.0.0.1" if name_of(inspector) == name_of(host) else own_address(host)
    assert_db_connections_match_tls(inspector, address, group)


def assert_untrusted_ca_breaks(host, port, service, ca_file, component):
    """With a CA that did not sign the server certificate, the application cannot reach the server.

    So the application verifies the server certificate, and the health checks
    pass only because the configured CA signed it.
    """
    other = "redis" if component == "database" else "database"

    def failed():
        status, payload = health(host, port)
        return status == 503 and payload.get(component) == "error"

    with untrusted_file(host, ca_file, service, healthy=lambda: healthy(host, port)):
        assert wait_for(failed, timeout=60), \
            f"{service} stayed healthy with an untrusted {component} CA: {health(host, port)}"
        _, payload = health(host, port)
        assert payload.get(other) == "ok", f"The {other} connection failed too: {payload}"
