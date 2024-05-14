import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

miarecweb_version = os.environ.get('MIARECWEB_VERSION')
miarec_version = os.environ.get('MIAREC_VERSION')
miarec_screen_version = os.environ.get('MIAREC_SCREEN_VERSION')
miarec_livemon_version = os.environ.get('MIAREC_LIVEMON_VERSION')
miarec_version = os.environ.get('MIAREC_VERSION')
postgresql_version = os.environ.get('POSTGRESQL_VERSION')

def test_directories(host):

    dirs = [
        "/opt/miarecweb/releases/{}".format(miarecweb_version),
        "/opt/miarec/releases/{}".format(miarec_version),
        "/opt/miarec_screen/releases/{}".format(miarec_screen_version),
        "/opt/miarec_livemon/releases/{}".format(miarec_livemon_version),
        "/opt/redis",
        "/etc/postgresql/{}".format(postgresql_version),
        "/var/log/miarecweb",
        "/var/log/miarecweb/celery",
        "/var/log/miarec",
        "/var/log/miarec_screen",
        "/var/log/miarec_livemon",
        "/var/log/pgbouncer",
        "/var/log/redis",
    ]
    for dir in dirs:
        d = host.file(dir)
        assert d.is_directory
        assert d.exists

def test_files(host):
    if host.system_info.distribution == "ubuntu":
        postgresql_conf_dir = "main"

    else:
        postgresql_conf_dir = "data"

    files = [
        "/opt/miarecweb/releases/{}/production.ini".format(miarecweb_version),
        "/opt/miarec/releases/{}/miarec.ini".format(miarec_version),
        "/opt/miarec_screen/releases/{}/miarec_screen.ini".format(miarec_screen_version),
        "/opt/miarec_livemon/releases/{}/miarec_livemon.ini".format(miarec_livemon_version),
        "/opt/redis/redis.conf",
        "/etc/postgresql/{}/{}/postgresql.conf".format(postgresql_version,postgresql_conf_dir)
    ]

    for file in files:
        f = host.file(file)
        assert f.exists
        assert f.is_file


def test_service(host):
    if host.system_info.distribution == "ubuntu":
        apache_service = "apache2"
        postgresql_service = "postgresql"

    else:
        apache_service = "httpd"
        postgresql_service = "postgresql-{}".format(postgresql_version)

    services = [
        "miarec",
        "miarec_livemon",
        "miarec_screen",
        apache_service,
        "celeryd",
        "celerybeat",
        "redis_6379",
        postgresql_service,
        "pgbouncer"
    ]

    for service in services:
        s = host.service(service)
        assert s.is_enabled
        assert s.is_running


def test_socket(host):
    sockets = [
        "tcp://0.0.0.0:80",
        "tcp://0.0.0.0:443",
        "tcp://0.0.0.0:5080",
        "tcp://0.0.0.0:6087",
        "tcp://0.0.0.0:6088",
        "tcp://0.0.0.0:6089",
        "tcp://0.0.0.0:6091",
        "tcp://0.0.0.0:6092",
        "tcp://0.0.0.0:6554",
        "tcp://0.0.0.0:9080",
        "tcp://127.0.0.1:5432",
        "tcp://127.0.0.1:6432",
        "tcp://127.0.0.1:6379"
    ]
    for socket in sockets:
        s = host.socket(socket)
        assert s.is_listening

def test_script(host):
    assert host.run("/opt/miarecweb/current/pyenv/bin/python -m miarecweb.scripts.create_root_user -u molecule -p molecule --skip-if-exists").rc == 0, "Miarecweb script failed to execute"