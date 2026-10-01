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

.PHONY: help tls-certs-all tls-certs-postgresql tls-certs-pgbouncer tls-certs-redis \
	tls-certs-miarec tls-certs-miarecweb tls-certs-validate tls-certs-clean

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_\-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

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
