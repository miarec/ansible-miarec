"""The services run as the dedicated users set in molecule.yml, not as root."""
import os
import pytest
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')


@pytest.mark.parametrize("comm, user, group", [
    ("miarec", "miarec", "miarec"),
    ("miarec_screen", "miarec", "miarec"),
    ("miarec_livemon", "miarec", "miarec"),
    # The Celery worker and beat
    ("celery", "celery", "miarec"),
])
def test_process_user(host, comm, user, group):
    result = host.run("ps -C %s -o user:32=,group:32=", comm)
    assert result.rc == 0, f"No {comm} process is running"
    owners = {tuple(line.split()) for line in result.stdout.splitlines() if line.strip()}
    assert owners == {(user, group)}, f"Unexpected {comm} process owners: {owners}"


def test_apache_in_miarec_group(host):
    """Apache can read recordings in directories owned by the miarec group."""
    apache_user = "www-data" if host.system_info.distribution == "ubuntu" else "apache"
    assert "miarec" in host.user(apache_user).groups, f"{apache_user} is not in the miarec group"
    # The running processes get the group only after Apache restarts.
    result = host.run("ps -u %s -o supgrp:256=", apache_user)
    assert result.rc == 0, f"No {apache_user} process is running"
    for groups in result.stdout.splitlines():
        assert "miarec" in groups.split(","), f"An {apache_user} process runs without the miarec group: {groups}"
