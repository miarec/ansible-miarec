"""Web tier: Apache and MiaRec Web."""
import json
import uuid

import pytest
from conftest import (
    hosts_in, host_of, shares_host, address_of, own_address, process_owners, listening_on_all_interfaces,
    apache_service, get_json, wait_for, untrusted_file, admin_query, assert_db_connections_match_tls,
    needs_tls, INSTALL_PGBOUNCER, MIARECWEB_PYTHON, MIARECWEB_TLS_DIR, MIARECWEB_VERSION,
)

testinfra_hosts = hosts_in('web')

HEALTH_URL = "http://localhost/health"
# MiaRec Web answers 10 health requests per minute from one address, so poll slowly.
HEALTH_POLL_INTERVAL = 6


def health(host):
    """Return (HTTP status, payload) of the MiaRec Web health endpoint."""
    return get_json(host, HEALTH_URL)


def wait_for_health(host, done):
    """Poll the health endpoint until done(status, payload) is true and return the last answer."""
    last = []

    def check():
        last[:] = health(host)
        return done(*last)

    wait_for(check, interval=HEALTH_POLL_INTERVAL)
    return tuple(last)


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


def test_celery_round_trip(host):
    """A task sent from the web host runs on a Celery worker and returns a result.

    In the decoupled scenarios, the web host has no Celery worker, so the reply
    proves that the worker on the Celery host consumes tasks from Redis and
    stores the results back in Redis.
    """
    probe_id = str(uuid.uuid4())
    script = (
        "import json, sys\n"
        "from miarecweb.celery.celery_app import celery_app, load_config_from_file\n"
        "celery_config, _ = load_config_from_file(sys.argv[1])\n"
        "celery_app.conf.update(celery_config)\n"
        "result = celery_app.send_task('miarecweb.observability.celery_health_probe', args=[sys.argv[2]], expires=60)\n"
        "print(json.dumps({'task_id': result.id, 'reply': result.get(timeout=60)}))\n"
    )
    result = host.run("%s -c %s %s %s", MIARECWEB_PYTHON, script, "/opt/miarecweb/current/production.ini", probe_id)
    assert result.rc == 0, f"Celery health probe failed: {result.stderr}"
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["reply"]["probe_id"] == probe_id, f"Unexpected probe reply: {payload}"
    assert payload["reply"]["celery_task_id"] == payload["task_id"], f"Unexpected probe reply: {payload}"


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
    # Neither hba file has a rule for the administrator from another host.
    if INSTALL_PGBOUNCER:
        expected = "no authentication method is found"
    else:
        expected = f'no pg_hba.conf entry for host "{own_address(host)}", user "postgres"'
    assert expected in result.stderr, f"Rejected for another reason: {result.stderr}"


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
