"""Web tier: Apache and MiaRec Web."""
import pytest
from conftest import (
    hosts_in, host_of, host_named, name_of, shares_host, address_of, process_owners, listening_on_all_interfaces,
    apache_service, get_json, wait_for, untrusted_file, admin_query, assert_db_connections_match_tls,
    needs_tls, MIARECWEB_PYTHON, MIARECWEB_TLS_DIR, MIARECWEB_VERSION,
)

testinfra_hosts = hosts_in('web')

HEALTH_URL = "http://localhost/health"
CELERY_PROBE_PATH = "/health/celery/probe"
# MiaRec Web answers 10 requests per minute from one address to each health
# endpoint, so poll slowly.
HEALTH_POLL_INTERVAL = 6
# The probe waits up to 10 seconds for the worker, so wait longer for the answer.
CELERY_PROBE_HTTP_TIMEOUT = 30


def health(host):
    """Return (HTTP status, payload) of the MiaRec Web health endpoint."""
    return get_json(host, HEALTH_URL)


def poll(get, done):
    """Call get() until done(status, payload) is true and return the last answer."""
    last = []

    def check():
        last[:] = get()
        return done(*last)

    wait_for(check, interval=HEALTH_POLL_INTERVAL)
    return tuple(last)


def wait_for_health(host, done):
    """Poll the health endpoint until done(status, payload) is true and return the last answer."""
    return poll(lambda: health(host), done)


def celery_probe(client, address):
    """Call the Celery health probe of MiaRec Web from a host and return (HTTP status, payload).

    Retries while the probe answers that the client sent too many requests.
    """
    url = f"http://{address}{CELERY_PROBE_PATH}"
    return poll(lambda: get_json(client, url, timeout=CELERY_PROBE_HTTP_TIMEOUT),
                lambda status, payload: status != 429)


def assert_celery_probe_passes(client, address):
    status, payload = celery_probe(client, address)
    assert status == 200, f"Unexpected Celery probe status {status}: {payload}"
    assert payload.get("status") == "ok", f"Unexpected Celery probe payload: {payload}"
    assert payload.get("worker_processed") is True, f"No Celery worker ran the probe task: {payload}"


def other_hosts():
    """Return the hosts that may not call the Celery health probe.

    The scenarios allow the web host itself and the Celery host.
    """
    allowed = set(hosts_in("web") + hosts_in("celery"))
    return [name for name in hosts_in("all") if name not in allowed] or \
        [pytest.param(None, marks=pytest.mark.skip(reason="No other host"))]


def healthy(host):
    status, payload = health(host)
    return status == 200 and payload.get("postgresql") == "ok" and payload.get("redis") == "ok"


def test_service(host):
    s = host.service(apache_service(host))
    assert s.is_enabled
    assert s.is_running


def test_listening(host):
    for port in [80, 443]:
        assert listening_on_all_interfaces(host, port), f"Apache does not listen on port {port}"


def test_apache_in_miarec_group(host):
    """Apache processes run with the miarec group, so they can read the MiaRec files of that group."""
    apache_user = "www-data" if host.system_info.distribution == "ubuntu" else "apache"
    # The running processes get the group only after Apache restarts.
    result = host.run("ps -u %s -o supgrp:256=", apache_user)
    assert result.rc == 0, f"No {apache_user} process is running"
    for groups in result.stdout.splitlines():
        assert "miarec" in groups.split(","), f"An {apache_user} process runs without the miarec group: {groups}"


def test_version(host):
    result = host.run("%s -c %s", MIARECWEB_PYTHON,
                      "import importlib.metadata as m; print(m.version('miarecweb'))")
    assert result.rc == 0, result.stderr
    assert result.stdout.strip() == MIARECWEB_VERSION


def test_health_endpoint(host):
    """MiaRec Web reaches PostgreSQL and Redis."""
    status, payload = wait_for_health(host, lambda status, payload: status != 429)
    assert status == 200, f"Unexpected health status {status}: {payload}"
    assert payload.get("postgresql") == "ok", f"Unexpected PostgreSQL status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"


def test_db_connections_use_tls(host):
    """The open database connections of MiaRec Web use TLS exactly when the scenario has TLS.

    The Celery host inspects the connections, so the inspecting connection does
    not count for the web host in the decoupled scenarios.
    """
    inspector = host_of("celery")
    assert_db_connections_match_tls(inspector, address_of(inspector, "web"), "web")


def test_celery_probe(host):
    """The Celery health probe sends a task to a Celery worker and gets the result back.

    The request goes through Apache, so the task leaves from the MiaRec Web
    process that serves the users. In the decoupled scenarios, the web host has
    no Celery worker, so the reply proves that the worker on the Celery host
    consumes tasks from Redis and stores the results back in Redis.
    """
    assert_celery_probe_passes(host, "localhost")


def test_celery_probe_allows_listed_host(host):
    """A host in miarecweb_celery_probe_hosts calls the Celery health probe.

    The decoupled scenarios list the Celery host. By default, MiaRec Web allows
    only the web host itself, so the answer proves that the role applies the list.
    """
    client = host_of("celery")
    if name_of(client) == name_of(host):
        pytest.skip("The Celery host is the web host")
    assert_celery_probe_passes(client, address_of(client, "web"))


@pytest.mark.parametrize("client_name", other_hosts())
def test_celery_probe_rejects_other_hosts(host, client_name):
    """A host that is not in miarecweb_celery_probe_hosts cannot call the Celery health probe."""
    client = host_named(client_name)
    status, payload = celery_probe(client, address_of(client, "web"))
    assert status == 403, f"{client_name} called the Celery health probe: HTTP {status} {payload}"


def test_script(host):
    """A MiaRec Web command-line script writes to the database."""
    result = host.run("%s -m miarecweb.scripts.create_root_user -u admin -p admin", MIARECWEB_PYTHON)
    assert result.rc == 0 or "already exists" in result.stderr, f"MiaRec Web script failed: {result.stderr}"


def test_db_rejects_remote_admin_without_password(host):
    """Another host cannot log in to the database tier as the administrator without a password."""
    if shares_host(host, "db"):
        pytest.skip("The database runs on this host. See test_postgresql_auth.py.")
    result = admin_query(host)
    assert result.rc != 0, f"The web host logged in as postgres without a password: {result.stdout}"


@needs_tls
def test_untrusted_db_ca_breaks_the_database_connection(host):
    """With a CA that did not sign the database server certificate, MiaRec Web cannot reach the database.

    So MiaRec Web verifies the server certificate, and test_health_endpoint
    passes only because the configured CA signed it.
    """
    with untrusted_file(host, f"{MIARECWEB_TLS_DIR}/db-ca.crt", apache_service(host),
                        healthy=lambda: healthy(host), interval=HEALTH_POLL_INTERVAL):
        status, payload = wait_for_health(host, lambda status, payload: status == 503)
        assert status == 503, f"MiaRec Web stayed healthy with an untrusted database CA: {status} {payload}"
        assert payload.get("postgresql") == "error", f"Unexpected health payload: {payload}"
        assert payload.get("redis") == "ok", f"Unexpected health payload: {payload}"


@needs_tls
def test_untrusted_redis_ca_breaks_the_redis_connection(host):
    """With a CA that did not sign the Redis server certificate, MiaRec Web cannot reach Redis.

    The health endpoint counts requests in Redis, so it fails with HTTP 500
    before it checks the components.
    """
    def redis_failed(status, payload):
        return status == 500 or (status == 503 and payload.get("redis") == "error")

    with untrusted_file(host, f"{MIARECWEB_TLS_DIR}/redis-ca.crt", apache_service(host),
                        healthy=lambda: healthy(host), interval=HEALTH_POLL_INTERVAL):
        status, payload = wait_for_health(host, redis_failed)
        assert redis_failed(status, payload), \
            f"MiaRec Web stayed healthy with an untrusted Redis CA: {status} {payload}"


def test_no_celery(host):
    """The Celery workers run on their own host in the decoupled scenarios."""
    if shares_host(host, "celery") or shares_host(host, "celerybeat"):
        pytest.skip("Celery runs on this host")
    assert host.run("ps -C celery").rc != 0, "Celery must not run on the web host"
