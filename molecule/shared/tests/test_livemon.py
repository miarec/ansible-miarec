"""Live monitoring."""
from conftest import hosts_in, process_owners, listening_on_all_interfaces

testinfra_hosts = hosts_in('livemon')


def test_service(host):
    s = host.service("miarec_livemon")
    assert s.is_enabled
    assert s.is_running


def test_process_user(host):
    assert process_owners(host, "miarec_livemon") == {("miarec", "miarec")}


def test_listening(host):
    assert listening_on_all_interfaces(host, 6087), "Live monitoring does not listen on port 6087"
