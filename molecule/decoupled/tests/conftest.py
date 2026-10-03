"""Shared helpers for the decoupled scenario.

Each tier runs in its own container on one Docker network. Containers resolve
each other by name through the Docker DNS, so the tests look up peer addresses
by the inventory host name instead of hard-coding them.
"""
import os
import testinfra.utils.ansible_runner

runner = testinfra.utils.ansible_runner.AnsibleRunner(os.environ['MOLECULE_INVENTORY_FILE'])

DB_NAME = "miarecdb"
DB_USER = "miarec"
DB_PASSWORD = "password"
PGBOUNCER_PORT = 6432
REDIS_PORT = 6379


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
