# 20260309_tls

Adds opt-in TLS for every connection to PostgreSQL, PGBouncer, and Redis, and changes several defaults that existing deployments pick up on their next run.

## 🎯 Problem

Deployments that must encrypt their database and Redis traffic had no supported way to do it. Operators created certificates by hand, copied them to each host, and overrode settings per component. Nothing checked that the result encrypted the traffic or rejected plaintext clients.

---

## 👀 What changes for users

- One switch per server turns on TLS: `postgresql_ssl`, `pgbouncer_client_tls`, and `redis_tls`. MiaRec Web, Celery, the recorder, and the screen controller follow these switches and verify the server certificate.
- `make tls-certs-all` creates a self-signed certificate set. Certificates from your own CA work in the same layout, and `make tls-certs-validate` checks a set before a deployment. The playbooks upload the files and restart a service only when its own files changed.
- Client certificates are optional: `postgresql_ssl_require_clientcert` and `pgbouncer_client_tls_sslmode: verify-ca`.
- The playbooks stop before they change a host when a TLS combination can't work, such as client certificates without `postgresql_ssl`, or a PGBouncer client TLS mode other than `require`, `verify-ca`, or `verify-full`.

---

## ⚠️ Upgrade impact

These changes apply on the next run of an existing deployment, with or without TLS.

- **Recordings directory.** The recorder's default recordings directory changes from `/var/miarec/recordings` to `/var/recordings/<inventory hostname>`. New recordings go to the new directory, and existing recordings stay where they are. A recordings directory set in the web portal takes precedence. To keep the old path, set `miarec_recordings_dir: /var/miarec/recordings` in `vars/custom.yml`.
- **Screen controller version.** The default `miarec_screen_version` changes from 2024.4.5.0 to 2026.11.15.0, so a deployment that doesn't set the version upgrades the screen controller. TLS needs 2026.8.3.0 or later. 2026.8.3.0 and 2026.10.26.0 crash on every connection to ports 6091 and 6092.
- **PGBouncer local logins.** The `stats` user no longer reads PGBouncer statistics over the loopback address without a password. A local monitoring system needs its own rule in `pgbouncer_hba_custom`; `vars/db.yml` shows an example.
- **PostgreSQL local logins.** Every user in `postgresql_users` can log in over the loopback address with a password, not only the MiaRec user. The administrator logs in only through the Unix socket, with peer authentication, and `postgresql_default_auth_method` no longer changes that rule.
- **Ubuntu 20.04** is no longer tested or documented.

---

## 🐛 Bug details

The PGBouncer role writes its own rules before the rules from `vars/db.yml`, and PGBouncer applies the first rule that matches. Its rules for local connections therefore always won: a password rule for every user, and a passwordless rule for `stats`. The ansible-miarec rules for local connections never applied.

* **Severity**: low. `stats` can read pool statistics only, and only from the database host. With client TLS, `client_tls_sslmode` still rejects plaintext before the rules apply.
* **Symptom**: none visible. The rules for local connections in `vars/db.yml` had no effect.
* **Exposure**: every release since PGBouncer support was added in April 2021 (`b1028db`).

---

## 🔧 Implementation notes

- Each role uploads its own TLS files and restarts only its own service. The screen controller keeps separate copies in `/etc/miarec_screen/tls`, so on a host shared with the recorder, a certificate renewal restarts both services.
- Redis TLS files live in `/etc/redis-tls`, because the RHEL Redis package changes the owner of everything under `/etc/redis` at every boot.
- Redis added TLS in 6.0, and RHEL 7 and 8 package older versions. With `redis_tls`, the playbook fails early there unless Redis is built from source.
- Plan: `docs/plans/20260309_tls/plan.md`.

---

## 📌 Related issues

Follow-up: #20, server certificates for the SIPREC listener and the screen controller's control interface.
