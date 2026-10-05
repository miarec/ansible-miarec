"""Web tier: Apache, miarecweb, and live monitoring. No Celery."""
import json
import os
import re
import uuid
from conftest import admin_query, hosts_in, peer_ip, process_owners, TLS, DB_PORT, REDIS_PORT

testinfra_hosts = hosts_in('web')

miarecweb_version = os.environ.get('MIARECWEB_VERSION')
miarec_livemon_version = os.environ.get('MIAREC_LIVEMON_VERSION')


def test_directories(host):
    for dir in [
        "/opt/miarecweb/releases/{}".format(miarecweb_version),
        "/opt/miarec_livemon/releases/{}".format(miarec_livemon_version),
        "/var/log/miarec_livemon",
    ]:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_service(host):
    apache = "apache2" if host.system_info.distribution == "ubuntu" else "httpd"
    for service in [apache, "miarec_livemon"]:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_process_user(host):
    assert process_owners(host, "miarec_livemon") == {("miarec", "miarec")}


def test_apache_in_miarec_group(host):
    """Apache can read recordings in directories owned by the miarec group."""
    apache_user = "www-data" if host.system_info.distribution == "ubuntu" else "apache"
    assert "miarec" in host.user(apache_user).groups, f"{apache_user} is not in the miarec group"
    # The running processes get the group only after Apache restarts.
    result = host.run("ps -u %s -o supgrp:256=", apache_user)
    assert result.rc == 0, f"No {apache_user} process is running"
    for groups in result.stdout.splitlines():
        assert "miarec" in groups.split(","), f"An {apache_user} process runs without the miarec group: {groups}"


def test_no_celery(host):
    for path in ["/etc/systemd/system/celeryd.service", "/etc/systemd/system/celerybeat.service"]:
        assert not host.file(path).exists, f"{path} must not exist on the web host"


def test_socket(host):
    for socket in ["tcp://0.0.0.0:80", "tcp://0.0.0.0:443", "tcp://0.0.0.0:6087"]:
        assert host.socket(socket).is_listening, f"Socket {socket} is not listening"


def test_production_ini_points_to_peers(host):
    ini = host.file("/opt/miarecweb/releases/{}/production.ini".format(miarecweb_version))
    assert ini.exists
    db_ip = peer_ip(host, 'db')
    redis_ip = peer_ip(host, 'redis')
    assert ini.contains(f"^DATABASE_HOST = {db_ip}$")
    assert ini.contains(f"^DATABASE_PORT = {DB_PORT}$")
    assert ini.contains(f"^REDIS_HOST = {redis_ip}$")
    assert ini.contains(f"^REDIS_PORT = {REDIS_PORT}$")


def test_production_ini_tls(host):
    """In decoupled-tls, MiaRec Web connects to the database and Redis over TLS."""
    content = host.file("/opt/miarecweb/releases/{}/production.ini".format(miarecweb_version)).content_string
    assert bool(re.search(r"^DATABASE_SSL_PARAMS = .*sslmode=(require|verify-ca|verify-full)", content, re.M)) == TLS
    assert re.search(r"^REDIS_SCHEMA = {}$".format("rediss" if TLS else "redis"), content, re.M)


def test_db_rejects_remote_admin_without_password(host):
    """Another host cannot log in to the database tier as the administrator without a password."""
    result = admin_query(host)
    assert result.rc != 0, f"The web host logged in as postgres without a password: {result.stdout}"
    # PGBouncer reports a missing hba rule as "no authentication method is found".
    rejections = ("no pg_hba.conf entry", "no authentication method", "password", "authentication failed")
    assert any(error in result.stderr for error in rejections), \
        f"The connection failed before authentication: {result.stderr}"


def test_health_endpoint(host):
    """The web application reaches PostgreSQL and Redis on their hosts."""
    result = host.run("curl -fsSLk http://localhost/health")
    assert result.rc == 0, f"Health endpoint not reachable: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("postgresql") == "ok", f"Unexpected PostgreSQL status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"


def test_celery_round_trip(host):
    """A task sent from the web host runs on the Celery host and returns a result.

    The web host has no Celery worker, so the reply proves that the worker on the
    Celery host consumes tasks from Redis and stores results back in Redis.
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
    result = host.run(
        "/opt/miarecweb/current/pyenv/bin/python -c %s %s %s",
        script, "/opt/miarecweb/current/production.ini", probe_id,
    )
    assert result.rc == 0, f"Celery health probe failed: {result.stderr}"
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["reply"]["probe_id"] == probe_id, f"Unexpected probe reply: {payload}"
    assert payload["reply"]["celery_task_id"] == payload["task_id"], f"Unexpected probe reply: {payload}"


def test_script(host):
    result = host.run("/opt/miarecweb/current/pyenv/bin/python -m miarecweb.scripts.create_root_user -u admin -p admin")
    assert result.rc == 0 or "already exists" in result.stderr, f"Miarecweb script failed: {result.stderr}"
