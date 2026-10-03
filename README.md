# Ansible playbook to install MiaRec applications

Documentation: [Installation of MiaRec on Linux using Ansible](https://www.miarec.com/doc/administration-guide/doc918)

## Testing

The playbooks are tested with Molecule. For the scenarios and their variables, see [molecule/README.md](molecule/README.md).

```
uv sync
MOLECULE_DISTRO=ubuntu2404 uv run molecule test -s decoupled
```

### Run tests for several distros in parallel

Give each run its own `MOLECULE_EPHEMERAL_DIRECTORY`. Otherwise, the runs share Molecule state and break each other. The container names already include the distro, so they don't collide.

```
for d in ubuntu2404 rockylinux9 rhel7 rhel8 rhel9; do
  MOLECULE_DISTRO=$d MOLECULE_EPHEMERAL_DIRECTORY=/tmp/molecule/$d \
    uv run molecule test -s decoupled </dev/null > /tmp/molecule-$d.log 2>&1 &
done
wait
```

### Raise the inotify instance limit

Before you run several scenarios at the same time, raise the host's inotify instance limit:

```
echo 'fs.inotify.max_user_instances = 1024' | sudo tee /etc/sysctl.d/99-inotify.conf
sudo sysctl -w fs.inotify.max_user_instances=1024
```

Every test container runs systemd, which uses inotify instances: about 5–10 for each RHEL or Rocky Linux container and up to 20 for each Ubuntu container. The kernel counts instances per host user, and root in every container is root on the host, so all containers share one limit. The default limit is 128, which two `decoupled` scenarios (12 containers) can exceed. When the limit runs out, systemd in the next container fails to start, and the run fails with `Failed to connect to bus: No such file or directory`.
