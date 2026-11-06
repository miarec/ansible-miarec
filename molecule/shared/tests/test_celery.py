"""Celery tier: worker and beat.

test_web.py sends a task from the web host and checks that a worker runs it.
"""
import pytest
from conftest import hosts_in, shares_host, process_owners, listening_on_all_interfaces

testinfra_hosts = hosts_in('celery')


def test_service(host):
    for service in ["celeryd", "celerybeat"]:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_process_user(host):
    """The Celery worker and beat run as the celery user in the miarec group."""
    assert process_owners(host, "celery") == {("celery", "miarec")}


def test_no_apache(host):
    """Apache runs on the web host in the decoupled scenarios."""
    if shares_host(host, "web"):
        pytest.skip("Apache runs on this host")
    apache = "apache2" if host.system_info.distribution == "ubuntu" else "httpd"
    assert host.run("ps -C %s", apache).rc != 0, f"{apache} must not run on the Celery host"
    assert not listening_on_all_interfaces(host, 80)
