"""Shared helpers for the tests of every scenario.

The scenarios differ in where the components run and which connections use TLS:

    default        all components on one host, no TLS
    tls            all components on one host, TLS
    decoupled      one host per tier, no TLS
    decoupled-tls  one host per tier, TLS

The tests treat the components as black boxes. They connect to the services,
call their APIs, and read the data that the services write, but they never read
a configuration file. Each test file covers one inventory group and runs on its
hosts. The provisioner environment in molecule.yml tells which connections use
TLS and whether PGBouncer is installed.
"""
import contextlib
import json
import os
import time

import pytest
import testinfra
import testinfra.utils.ansible_runner

runner = testinfra.utils.ansible_runner.AnsibleRunner(os.environ['MOLECULE_INVENTORY_FILE'])


def env_flag(name, default=False):
    """Return an Ansible-style boolean from the provisioner environment."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "yes", "on", "1")


# The TLS scenarios set TLS_ENABLED. The clients then use TLS for the database and Redis.
TLS = env_flag("TLS_ENABLED")
INSTALL_PGBOUNCER = env_flag("INSTALL_PGBOUNCER", default=True)
# PostgreSQL itself uses TLS when the clients connect to it directly, or when
# POSTGRESQL_SSL asks for TLS between PGBouncer and PostgreSQL.
POSTGRESQL_SSL = TLS and (env_flag("POSTGRESQL_SSL") or not INSTALL_PGBOUNCER)
# DB_CLIENTCERT: the database tier requires a client certificate that its CA
# signed, not only a password (postgresql_ssl_require_clientcert on PostgreSQL,
# pgbouncer_client_tls_sslmode=verify-ca on PGBouncer).
DB_CLIENTCERT = TLS and env_flag("DB_CLIENTCERT")

MIARECWEB_VERSION = os.environ.get("MIARECWEB_VERSION")
MIAREC_VERSION = os.environ.get("MIAREC_VERSION")
MIAREC_SCREEN_VERSION = os.environ.get("MIAREC_SCREEN_VERSION")
POSTGRESQL_VERSION = os.environ.get("POSTGRESQL_VERSION")

DB_NAME = "miarecdb"
DB_USER = "miarec"
DB_PASSWORD = "password"
PGBOUNCER_PORT = 6432
POSTGRESQL_PORT = 5432
# The port that the applications connect to
DB_PORT = PGBOUNCER_PORT if INSTALL_PGBOUNCER else POSTGRESQL_PORT
REDIS_PORT = 6379
RECORDER_REST_PORT = 6088
SCREEN_REST_PORT = 6089

# The REST API user of the recorder and the screen controller. The roles set its
# allowed addresses. The password is the default of the INI files that ship with
# the applications.
REST_USER = "webui"
REST_PASSWORD = "password"

# The groups whose hosts connect to the database and Redis
CLIENT_GROUPS = ["web", "celery", "celerybeat", "recorder", "screen"]

MIARECWEB_PYTHON = "/opt/miarecweb/current/pyenv/bin/python"
MIARECWEB_TLS_DIR = "/etc/miarecweb/tls"
MIAREC_TLS_DIR = "/etc/miarec/tls"
# A client certificate that every service CA trusts, on the database host, for
# the tests that run psql there (molecule/shared/tls-certs.yml).
TEST_CLIENT_CERT = "/var/tmp/tls-test-client/client"
# A self-signed certificate that no service CA trusts (molecule/shared/tls-certs.yml).
# The TLS scenarios create it on every host.
UNTRUSTED_CERT = "/var/tmp/tls-untrusted/client"

needs_tls = pytest.mark.skipif(not TLS, reason="TLS is off")


# ---------------------------------------------------------------------------
# Hosts and addresses
# ---------------------------------------------------------------------------

def hosts_in(group):
    """Return the inventory host names in a group."""
    return runner.get_hosts(group)


def host_named(name):
    """Return a testinfra host for an inventory host.

    Uses the Ansible backend, like the hosts that the tests run on, so that
    host.ansible() works. runner.get_host() returns a Docker backend instead.
    """
    return testinfra.get_host(f"ansible://{name}", ansible_inventory=os.environ['MOLECULE_INVENTORY_FILE'])


def host_of(group):
    """Return a testinfra host for the first host in a group."""
    return host_named(hosts_in(group)[0])


def name_of(host):
    """Return the inventory name of a testinfra host.

    The test hosts use the Ansible backend, and runner.get_host() returns hosts
    with the Docker backend. Both report the inventory name as the host name.
    """
    return host.backend.get_hostname()


def shares_host(host, group):
    """Return True when the host also belongs to a group."""
    return name_of(host) in hosts_in(group)


def has_remote_clients(host):
    """Return True when a host that connects to the database or Redis is another host."""
    return any(name != name_of(host) for group in CLIENT_GROUPS for name in hosts_in(group))


def resolve(host, name):
    """Resolve a container name to its IPv4 address from inside a container."""
    result = host.run("getent ahostsv4 %s", name)
    assert result.rc == 0, f"Cannot resolve {name}: {result.stderr}"
    return result.stdout.split()[0]


def address_of(host, group):
    """Return the address at which a host reaches the first host of a group.

    Components on the same host connect over the loopback interface, as in the
    single-host scenarios.
    """
    peer = hosts_in(group)[0]
    if peer == name_of(host):
        return "127.0.0.1"
    return resolve(host, peer)


def hostname(host):
    """Return the kernel hostname. The RHEL 7 image has no hostname command."""
    return host.file("/proc/sys/kernel/hostname").content_string.strip()


def own_address(host):
    """Return the IPv4 address of the container on the scenario network."""
    return resolve(host, hostname(host))


# ---------------------------------------------------------------------------
# Processes and sockets
# ---------------------------------------------------------------------------

def process_owners(host, comm):
    """Return the set of (user, group) pairs of the processes with a command name."""
    result = host.run("ps -C %s -o user:32=,group:32=", comm)
    assert result.rc == 0, f"No {comm} process is running"
    return {tuple(line.split()) for line in result.stdout.splitlines() if line.strip()}


def process_age(host, comm):
    """Return the age in seconds of the oldest process with a command name."""
    result = host.run("ps -C %s -o etimes=", comm)
    assert result.rc == 0, f"No {comm} process is running"
    return max(int(age) for age in result.stdout.split())


def is_listening(host, address, port):
    """Return True when a TCP port is bound to an address, or to the wildcard that covers it.

    testinfra does not count a wildcard socket (0.0.0.0 or ::) as listening on a
    specific address.
    """
    wildcard = "0.0.0.0" if "." in address else "::"
    sockets = host.socket.get_listening_sockets()
    return f"tcp://{address}:{port}" in sockets or f"tcp://{wildcard}:{port}" in sockets


def listening_on_all_interfaces(host, port):
    """Return True when a TCP port is bound to the wildcard address."""
    sockets = host.socket.get_listening_sockets()
    return f"tcp://0.0.0.0:{port}" in sockets or f"tcp://:::{port}" in sockets


def run_as(host, user, command):
    """Run a command as an OS user, from a directory that every user can read."""
    if user == "root":
        return host.run(f"cd /tmp && {command}")
    return host.run("cd /tmp && su -s /bin/sh %s -c %s", user, command)


def apache_service(host):
    return "apache2" if host.system_info.distribution == "ubuntu" else "httpd"


def postgresql_service(host):
    if host.system_info.distribution == "ubuntu":
        return "postgresql"
    return f"postgresql-{POSTGRESQL_VERSION}"


def redis_service(host):
    if host.run("systemctl cat %s", f"redis_{REDIS_PORT}").rc == 0:
        # Redis built from source (TLS scenarios on EL 7 and 8)
        return f"redis_{REDIS_PORT}"
    return "redis-server" if host.system_info.distribution == "ubuntu" else "redis"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http_get(host, url, user=None, password=None):
    """Send a GET request from a host and return (status, body).

    Uses the Ansible uri module, which works on every host, also on hosts
    without curl. Follows redirects and does not verify server certificates.
    """
    args = {
        "url": url,
        "return_content": True,
        "validate_certs": False,
        "timeout": 10,
        # Report every status instead of failing on it
        "status_code": list(range(100, 600)),
    }
    if user is not None:
        args.update(url_username=user, url_password=password, force_basic_auth=True)
    result = host.ansible("uri", json.dumps(args), check=False)
    return result.get("status", -1), result.get("content", "")


def get_json(host, url, user=None, password=None):
    """Send a GET request and return (status, decoded JSON body or {})."""
    status, body = http_get(host, url, user, password)
    try:
        return status, json.loads(body)
    except ValueError:
        return status, {}


def wait_for(check, timeout=90, interval=2):
    """Call check() until it returns a true value or the timeout expires.

    Returns the last value, so the caller can assert on it.
    """
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value or time.monotonic() >= deadline:
            return value
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Database and Redis clients
#
# The clients run on a MiaRec Web host, which has Python with psycopg2 and
# redis-py, and the MiaRec Web client certificates.
# ---------------------------------------------------------------------------

def miarecweb_client():
    """Return the host that runs the database and Redis clients."""
    return host_of("celery")


_DB_QUERY = """
import json, sys, psycopg2
conn = psycopg2.connect(sys.argv[1], connect_timeout=5)
conn.autocommit = True
cur = conn.cursor()
cur.execute(sys.argv[2], json.loads(sys.argv[3]))
columns = [column[0] for column in cur.description]
print(json.dumps([dict(zip(columns, row)) for row in cur.fetchall()], default=str))
"""


def db_query(client, sql, params=None, tls=TLS, client_cert=f"{MIARECWEB_TLS_DIR}/db-client",
             ca_file=f"{MIARECWEB_TLS_DIR}/db-ca.crt", dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD):
    """Run a query on the database tier from a MiaRec Web host.

    Connects to the port that the applications use (PGBouncer or PostgreSQL).
    With tls=True, verifies the server certificate against ca_file and presents
    client_cert (none when client_cert is None). With tls=False, the connection
    does not use TLS at all. Returns the command result. Its stdout holds the
    rows as a JSON list of objects.
    """
    dsn = f"host={address_of(client, 'db')} port={DB_PORT} dbname={dbname} user={user}"
    if password is not None:
        dsn += f" password={password}"
    if tls:
        dsn += f" sslmode=verify-ca sslrootcert={ca_file}"
        if client_cert:
            dsn += f" sslcert={client_cert}.crt sslkey={client_cert}.key"
    else:
        dsn += " sslmode=disable"
    return client.run("%s -c %s %s %s %s", MIARECWEB_PYTHON, _DB_QUERY, dsn, sql, json.dumps(params))


def db_rows(client, sql, params=None, **kwargs):
    """Run a query that must succeed and return its rows as a list of dicts."""
    result = db_query(client, sql, params, **kwargs)
    assert result.rc == 0, f"Query failed: {result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def db_client_connections(client):
    """Return (address, uses_tls) for each open connection of the applications to the database tier.

    Asks PGBouncer (SHOW CLIENTS) when it is installed, otherwise PostgreSQL.
    """
    if INSTALL_PGBOUNCER:
        # The application user is a PGBouncer stats user (vars/db.yml).
        rows = db_rows(client, "SHOW CLIENTS", dbname="pgbouncer")
        return [(row["addr"], bool(row["tls"])) for row in rows if row["database"] == DB_NAME]
    rows = db_rows(
        client,
        "SELECT host(a.client_addr) AS addr, s.ssl FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid) "
        "WHERE a.usename = %s AND a.datname = %s AND a.client_addr IS NOT NULL",
        [DB_USER, DB_NAME],
    )
    return [(row["addr"], row["ssl"]) for row in rows]


def assert_db_connections_match_tls(client, address, tier):
    """The open database connections from an address exist and use TLS exactly when the scenario has TLS."""
    connections = [uses_tls for addr, uses_tls in db_client_connections(client) if addr == address]
    assert connections, f"The {tier} host ({address}) has no open connection to the database tier"
    expected = "TLS" if TLS else "plaintext"
    assert all(uses_tls == TLS for uses_tls in connections), \
        f"Not every connection of the {tier} host ({address}) uses {expected}: {connections}"


def admin_query(client, sql="SELECT current_user"):
    """Log in to the database tier as the PostgreSQL administrator, without a password.

    sslmode=prefer tries TLS first and falls back to plaintext.
    """
    dsn = f"host={address_of(client, 'db')} port={DB_PORT} dbname=postgres user=postgres sslmode=prefer"
    return client.run("%s -c %s %s %s %s", MIARECWEB_PYTHON, _DB_QUERY, dsn, sql, "null")


_REDIS_PING = """
import sys, redis
kwargs = dict(host=sys.argv[1], port=int(sys.argv[2]), socket_connect_timeout=5, socket_timeout=5)
if len(sys.argv) > 3:
    kwargs.update(ssl=True, ssl_ca_certs=sys.argv[3], ssl_check_hostname=False)
if len(sys.argv) > 4:
    kwargs.update(ssl_certfile=sys.argv[4] + ".crt", ssl_keyfile=sys.argv[4] + ".key")
print(redis.Redis(**kwargs).ping())
"""


def redis_ping(client, tls=TLS, client_cert=f"{MIARECWEB_TLS_DIR}/redis-client",
               ca_file=f"{MIARECWEB_TLS_DIR}/redis-ca.crt"):
    """Send PING to the Redis tier from a MiaRec Web host.

    With tls=True, verifies the server certificate against ca_file and presents
    client_cert (none when client_cert is None).
    """
    args = [address_of(client, 'redis'), str(REDIS_PORT)]
    if tls:
        args.append(ca_file)
        if client_cert:
            args.append(client_cert)
    return client.run("%s -c %s" + " %s" * len(args), MIARECWEB_PYTHON, _REDIS_PING, *args)


# ---------------------------------------------------------------------------
# Failure path: an untrusted TLS file
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def untrusted_file(host, path, service, healthy, interval=2):
    """Replace a TLS file with the untrusted certificate and restart a service.

    On exit, restores the file, restarts the service, and waits until healthy()
    returns True (polling every interval seconds), so a failed test does not
    leave a broken service behind.
    """
    backup = f"/var/tmp/{service}-{os.path.basename(path)}.orig"
    result = host.run("cp -p %s %s", path, backup)
    assert result.rc == 0, f"Cannot back up {path}: {result.stderr}"
    try:
        # cp into the existing file keeps its owner and mode.
        result = host.run("cp %s %s && systemctl restart %s", f"{UNTRUSTED_CERT}.crt", path, service)
        assert result.rc == 0, f"Cannot replace {path} and restart {service}: {result.stderr}"
        yield
    finally:
        host.run("cp -p %s %s && rm -f %s && systemctl restart %s", backup, path, backup, service)
        assert wait_for(healthy, interval=interval), f"{service} did not recover after {path} was restored"
