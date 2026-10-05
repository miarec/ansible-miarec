SHELL := /bin/bash

# ---------------------------------------------------------------------------
# TLS certificate set
#
# The playbooks upload the files under CERTS_DIR to the hosts. Generate a
# self-signed set with `make tls-certs-all`, or place certificates issued by
# your own CA in the same layout. Run `make tls-certs-validate` before a
# deployment. All logic lives in scripts/tls-certs.sh.
#
# Variables (override on the command line, for example
# `make tls-certs-all CERTS_DIR=/tmp/certs TLS_SAN=IP:10.0.0.5`):
#   CERTS_DIR     output directory (default: certs)
#   OPENSSL       openssl binary
#   TLS_DAYS      validity of service certificates in days (default: 3650)
#   TLS_CA_DAYS   validity of the root CA in days (default: 3650)
#   TLS_KEY_BITS  RSA key size for service keys (default: 2048)
#   TLS_SAN       subjectAltName of server certificates
#                 (default: DNS:localhost,IP:127.0.0.1)
#   TLS_SAN_<SERVICE>  per-service override, for example TLS_SAN_REDIS
# ---------------------------------------------------------------------------
CERTS_DIR ?= certs
TLS_CERTS := scripts/tls-certs.sh

# Pass every variable to the script through the environment.
.EXPORT_ALL_VARIABLES:

# ---------------------------------------------------------------------------
# Molecule test configurations
#
# Each test-* target runs one configuration that CI tests. Every configuration
# has its own container names and Molecule state directory, so any number of
# configurations can run at the same time, also on the same distro.
#
# Variables (override on the command line, for example
# `make test-decoupled-tls DISTRO=rockylinux9 MOLECULE_COMMAND=converge`):
#   DISTRO            OS of the containers (default: ubuntu2404). For the
#                     tested distros, see .github/workflows/ci.yml.
#   MOLECULE_COMMAND  Molecule command to run (default: test). With converge,
#                     verify, login, or destroy, the next command of the same
#                     configuration reuses the containers and the state.
#   MOLECULE_RUNS_DIR parent of the Molecule state directories
#                     (default: ~/.cache/molecule/ansible-miarec)
#
# Other MOLECULE_* variables from the environment, for example
# MOLECULE_MIARECWEB_VERSION, reach the scenarios unchanged.
# ---------------------------------------------------------------------------
DISTRO ?= ubuntu2404
MOLECULE_COMMAND ?= test
MOLECULE_RUNS_DIR ?= $(HOME)/.cache/molecule/ansible-miarec

MOLECULE_TARGETS := test-default test-default-no-pgbouncer \
	test-tls test-tls-no-pgbouncer \
	test-decoupled test-decoupled-no-pgbouncer \
	test-decoupled-tls test-decoupled-tls-no-pgbouncer test-decoupled-tls-postgresql-ssl

.PHONY: help tls-certs-all tls-certs-postgresql tls-certs-pgbouncer tls-certs-redis \
	tls-certs-miarec tls-certs-miarecweb tls-certs-validate tls-certs-clean \
	$(MOLECULE_TARGETS)

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_\-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-34s\033[0m %s\n", $$1, $$2}'

tls-certs-all: ## Generate the missing TLS files for all services
	@$(TLS_CERTS) generate $(CERTS_DIR) all

tls-certs-postgresql: ## Generate the missing TLS files for PostgreSQL
	@$(TLS_CERTS) generate $(CERTS_DIR) postgresql

tls-certs-pgbouncer: ## Generate the missing TLS files for PGBouncer
	@$(TLS_CERTS) generate $(CERTS_DIR) pgbouncer

tls-certs-redis: ## Generate the missing TLS files for Redis
	@$(TLS_CERTS) generate $(CERTS_DIR) redis

tls-certs-miarec: ## Generate the missing TLS files for the MiaRec recorder
	@$(TLS_CERTS) generate $(CERTS_DIR) miarec

tls-certs-miarecweb: ## Generate the missing TLS files for MiaRec Web
	@$(TLS_CERTS) generate $(CERTS_DIR) miarecweb

tls-certs-validate: ## Validate the TLS certificate set (generated or customer-provided)
	@$(TLS_CERTS) validate $(CERTS_DIR)

tls-certs-clean: ## Remove the TLS certificate set
	@rm -rf $(CERTS_DIR)
	@echo "Removed $(CERTS_DIR)/"

# Settings of each configuration. MOLECULE_INSTANCE_SUFFIX goes into the
# container and network names. Configurations that share a scenario need
# different suffixes; the base configuration keeps the names that CI uses.
$(MOLECULE_TARGETS): MOLECULE_INSTALL_PGBOUNCER := true
$(MOLECULE_TARGETS): MOLECULE_POSTGRESQL_SSL := false
$(MOLECULE_TARGETS): MOLECULE_INSTANCE_SUFFIX :=

test-default: ## Test all components on one host
test-default: SCENARIO := default

test-default-no-pgbouncer: ## Test all components on one host, without PGBouncer
test-default-no-pgbouncer: SCENARIO := default
test-default-no-pgbouncer: MOLECULE_INSTALL_PGBOUNCER := false
test-default-no-pgbouncer: MOLECULE_INSTANCE_SUFFIX := -no-pgbouncer

test-tls: ## Test all components on one host, with TLS
test-tls: SCENARIO := tls

test-tls-no-pgbouncer: ## Test all components on one host, with TLS, without PGBouncer
test-tls-no-pgbouncer: SCENARIO := tls
test-tls-no-pgbouncer: MOLECULE_INSTALL_PGBOUNCER := false
test-tls-no-pgbouncer: MOLECULE_INSTANCE_SUFFIX := -no-pgbouncer

test-decoupled: ## Test one host per tier
test-decoupled: SCENARIO := decoupled

test-decoupled-no-pgbouncer: ## Test one host per tier, without PGBouncer
test-decoupled-no-pgbouncer: SCENARIO := decoupled
test-decoupled-no-pgbouncer: MOLECULE_INSTALL_PGBOUNCER := false
test-decoupled-no-pgbouncer: MOLECULE_INSTANCE_SUFFIX := -no-pgbouncer

test-decoupled-tls: ## Test one host per tier, with TLS
test-decoupled-tls: SCENARIO := decoupled-tls

test-decoupled-tls-no-pgbouncer: ## Test one host per tier, with TLS, without PGBouncer
test-decoupled-tls-no-pgbouncer: SCENARIO := decoupled-tls
test-decoupled-tls-no-pgbouncer: MOLECULE_INSTALL_PGBOUNCER := false
test-decoupled-tls-no-pgbouncer: MOLECULE_INSTANCE_SUFFIX := -no-pgbouncer

test-decoupled-tls-postgresql-ssl: ## Test one host per tier, with TLS, also from PGBouncer to PostgreSQL
test-decoupled-tls-postgresql-ssl: SCENARIO := decoupled-tls
test-decoupled-tls-postgresql-ssl: MOLECULE_POSTGRESQL_SSL := true
test-decoupled-tls-postgresql-ssl: MOLECULE_INSTANCE_SUFFIX := -postgresql-ssl

$(MOLECULE_TARGETS):
	MOLECULE_DISTRO=$(DISTRO) \
	MOLECULE_INSTALL_PGBOUNCER=$(MOLECULE_INSTALL_PGBOUNCER) \
	MOLECULE_POSTGRESQL_SSL=$(MOLECULE_POSTGRESQL_SSL) \
	MOLECULE_INSTANCE_SUFFIX=$(MOLECULE_INSTANCE_SUFFIX) \
	MOLECULE_EPHEMERAL_DIRECTORY=$(MOLECULE_RUNS_DIR)/$(@:test-%=%)-$(DISTRO) \
	uv run molecule $(MOLECULE_COMMAND) -s $(SCENARIO)
