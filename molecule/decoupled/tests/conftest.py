"""Shared helpers for the decoupled and decoupled-tls scenarios.

Each tier runs in its own container on one Docker network. Containers resolve
each other by name through the Docker DNS, so the tests look up peer addresses
by the inventory host name instead of hard-coding them.

Both scenarios run these tests. The provisioner environment in molecule.yml
tells which transports use TLS and whether PGBouncer is installed.
"""
import os
import testinfra.utils.ansible_runner

runner = testinfra.utils.ansible_runner.AnsibleRunner(os.environ['MOLECULE_INVENTORY_FILE'])


def env_flag(name, default=False):
    """Return an Ansible-style boolean from the provisioner environment."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "yes", "on", "1")


# decoupled-tls sets TLS_ENABLED. Clients then use TLS for the database and Redis.
TLS = env_flag("TLS_ENABLED")
INSTALL_PGBOUNCER = env_flag("INSTALL_PGBOUNCER", default=True)
# PostgreSQL itself uses TLS when the clients connect to it directly, or when
# MOLECULE_POSTGRESQL_SSL=true asks for TLS between PGBouncer and PostgreSQL.
POSTGRESQL_SSL = TLS and (env_flag("POSTGRESQL_SSL") or not INSTALL_PGBOUNCER)

DB_NAME = "miarecdb"
DB_USER = "miarec"
DB_PASSWORD = "password"
PGBOUNCER_PORT = 6432
POSTGRESQL_PORT = 5432
# The port that the application tiers connect to
DB_PORT = PGBOUNCER_PORT if INSTALL_PGBOUNCER else POSTGRESQL_PORT
REDIS_PORT = 6379

# MiaRec Web client certificates, uploaded to the web and Celery hosts
MIARECWEB_PYTHON = "/opt/miarecweb/current/pyenv/bin/python"
MIARECWEB_TLS_DIR = "/etc/miarecweb/tls"
# A client certificate that no service CA has signed (molecule/shared/tls-certs.yml)
UNTRUSTED_TLS_DIR = "/var/tmp/tls-untrusted"


def hosts_in(group):
    """Return the inventory host names in a group."""
    return runner.get_hosts(group)


def resolve(host, name):
    """Resolve a container name to its IPv4 address from inside a container."""
    result = host.run("getent ahostsv4 %s", name)
    assert result.rc == 0, f"Cannot resolve {name}: {result.stderr}"
    return result.stdout.split()[0]


def peer_ip(host, group):
    """Return the IPv4 address of the first host in a group."""
    return resolve(host, hosts_in(group)[0])


def own_ip(host):
    """Return the IPv4 address of the container running the test."""
    # The RHEL 7 image has no hostname command.
    return resolve(host, host.file("/proc/sys/kernel/hostname").content_string.strip())


def process_owners(host, comm):
    """Return the set of (user, group) pairs of the processes with a command name."""
    result = host.run("ps -C %s -o user:32=,group:32=", comm)
    assert result.rc == 0, f"No {comm} process is running"
    return {tuple(line.split()) for line in result.stdout.splitlines() if line.strip()}


def listening_on_all_interfaces(host, port):
    """Return True when a TCP port is bound to the wildcard address."""
    sockets = host.socket.get_listening_sockets()
    return f"tcp://0.0.0.0:{port}" in sockets or f"tcp://:::{port}" in sockets


def ini_option(ini, section, option):
    """Return the value of an option in an INI file, or None when it is not set."""
    current = None
    for line in ini.content_string.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
        elif current == section and "=" in line and not line.startswith(("#", ";")):
            key, value = line.split("=", 1)
            if key.strip() == option:
                return value.strip()
    return None


def postgresql_paths(host):
    """Return the PostgreSQL configuration directory and service name.

    The postgresql role keeps the configuration in /etc/postgresql on every
    distro. On RedHat, /var/lib/pgsql holds the data and an unused pg_hba.conf.
    """
    version = os.environ.get('POSTGRESQL_VERSION')
    if host.system_info.distribution == "ubuntu":
        return f"/etc/postgresql/{version}/main", "postgresql"
    return f"/etc/postgresql/{version}/data", f"postgresql-{version}"


_DB_QUERY = """
import sys, psycopg2
conn = psycopg2.connect(sys.argv[1], connect_timeout=5)
cur = conn.cursor()
cur.execute(sys.argv[2])
print(cur.fetchone()[0])
"""


def db_query(host, sql, tls=TLS, client_cert=f"{MIARECWEB_TLS_DIR}/client"):
    """Run a query on the database tier from a MiaRec Web host.

    Connects to the port that the application uses (PGBouncer or PostgreSQL).
    With tls=True, verifies the server certificate and presents client_cert.
    With tls=False, the connection does not use TLS at all.
    """
    dsn = f"host={peer_ip(host, 'db')} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"
    if tls:
        dsn += (f" sslmode=verify-ca sslrootcert={MIARECWEB_TLS_DIR}/ca.crt"
                f" sslcert={client_cert}.crt sslkey={client_cert}.key")
    else:
        dsn += " sslmode=disable"
    return host.run("%s -c %s %s %s", MIARECWEB_PYTHON, _DB_QUERY, dsn, sql)


def admin_query(host, sql="SELECT current_user"):
    """Run a query on the database tier as the PostgreSQL administrator, without a password.

    Connects from a MiaRec Web host to the port that the application uses.
    sslmode=prefer tries TLS first and falls back to plaintext.
    """
    dsn = f"host={peer_ip(host, 'db')} port={DB_PORT} dbname=postgres user=postgres sslmode=prefer"
    return host.run("%s -c %s %s %s", MIARECWEB_PYTHON, _DB_QUERY, dsn, sql)


_REDIS_PING = """
import sys, redis
kwargs = dict(host=sys.argv[1], port=int(sys.argv[2]), socket_connect_timeout=5, socket_timeout=5)
if len(sys.argv) > 3:
    kwargs.update(ssl=True, ssl_ca_certs=sys.argv[3], ssl_certfile=sys.argv[4] + ".crt",
                  ssl_keyfile=sys.argv[4] + ".key", ssl_check_hostname=False)
print(redis.Redis(**kwargs).ping())
"""


def redis_ping(host, tls=TLS, client_cert=f"{MIARECWEB_TLS_DIR}/redis-client"):
    """Send PING to the Redis tier from a MiaRec Web host.

    With tls=True, verifies the server certificate and presents client_cert.
    """
    args = [peer_ip(host, 'redis'), str(REDIS_PORT)]
    if tls:
        args += [f"{MIARECWEB_TLS_DIR}/redis-ca.crt", client_cert]
    return host.run("%s -c %s" + " %s" * len(args), MIARECWEB_PYTHON, _REDIS_PING, *args)
