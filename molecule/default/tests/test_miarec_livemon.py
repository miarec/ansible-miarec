import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

miarec_livemon_version = os.environ.get('MIAREC_LIVEMON_VERSION')


def test_directories(host):
    dirs = [
        "/opt/miarec_livemon/releases/{}".format(miarec_livemon_version),
        "/opt/miarec_livemon/shared",
        "/var/log/miarec_livemon"
    ]
    for dir in dirs:
        d = host.file(dir)
        assert d.exists, f"Directory {dir} does not exist"
        assert d.is_directory


def test_files(host):
    files = [
        "/opt/miarec_livemon/releases/{}/miarec_livemon".format(miarec_livemon_version),
        "/opt/miarec_livemon/releases/{}/miarec_livemon.ini".format(miarec_livemon_version),
        "/var/log/miarec_livemon/livemon.log"
    ]
    for file in files:
        f = host.file(file)
        assert f.exists, f"File {file} does not exist"
        assert f.is_file


def test_service(host):
    s = host.service("miarec_livemon")
    assert s.is_enabled
    assert s.is_running


def test_socket(host):
    assert host.socket("tcp://0.0.0.0:6087").is_listening
