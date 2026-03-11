SHELL := /bin/bash

# ---------------------------
# Certificate generation vars
# ---------------------------
CERTS_DIR ?= certs
CA_DIR := $(CERTS_DIR)/root
CA_KEY := $(CA_DIR)/ca.key
CA_CERT := $(CA_DIR)/ca.crt
CA_SERIAL := $(CA_DIR)/ca.srl
OPENSSL ?= openssl
TLS_DAYS ?= 365
SERIAL_OPT := -CAserial $(CA_SERIAL)

.PHONY: help tls-certs-all tls-certs-root tls-certs-postgresql tls-certs-pgbouncer tls-certs-redis tls-certs-clean

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_\-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

tls-certs-all: tls-certs-postgresql tls-certs-pgbouncer tls-certs-redis ## Generate TLS bundles for all services
	@echo "All TLS certificate bundles are ready under $(CERTS_DIR)/"

tls-certs-root: ## Generate (or reuse) root CA shared by service certs
	@mkdir -p $(CA_DIR)
	@if [ ! -f $(CA_KEY) ] || [ ! -f $(CA_CERT) ]; then \
		echo "Generating root CA in $(CA_DIR)"; \
		$(OPENSSL) req -x509 -newkey rsa:4096 -sha256 -days $(TLS_DAYS) -nodes \
			-keyout $(CA_KEY) -out $(CA_CERT) \
			-subj "/CN=MiaRec-Root-CA"; \
		chmod 600 $(CA_KEY); \
		chmod 644 $(CA_CERT); \
	else \
		echo "Root CA already exists at $(CA_CERT)"; \
	fi
	@if [ ! -f $(CA_SERIAL) ]; then \
		printf '01\n' > $(CA_SERIAL); \
	fi

tls-certs-postgresql: tls-certs-root ## Generate PostgreSQL server/client TLS bundle
	@echo ">> Generating PostgreSQL certificates"
	@mkdir -p $(CERTS_DIR)/postgresql
	@install -m 0644 $(CA_CERT) $(CERTS_DIR)/postgresql/ca.crt
	@if [ ! -f $(CERTS_DIR)/postgresql/server.key ]; then \
		$(OPENSSL) genrsa -out $(CERTS_DIR)/postgresql/server.key 2048; \
		chmod 600 $(CERTS_DIR)/postgresql/server.key; \
	else \
		echo "   $(CERTS_DIR)/postgresql/server.key already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/postgresql/server.crt ]; then \
		$(OPENSSL) req -new -key $(CERTS_DIR)/postgresql/server.key \
			-out $(CERTS_DIR)/postgresql/server.csr \
			-subj "/CN=postgresql-server" \
			-addext "subjectAltName = DNS:localhost,IP:127.0.0.1" \
			-addext "extendedKeyUsage = serverAuth"; \
		$(OPENSSL) x509 -req -in $(CERTS_DIR)/postgresql/server.csr \
			-CA $(CA_CERT) -CAkey $(CA_KEY) $(SERIAL_OPT) \
			-out $(CERTS_DIR)/postgresql/server.crt \
			-days $(TLS_DAYS) -sha256; \
		rm -f $(CERTS_DIR)/postgresql/server.csr; \
		chmod 644 $(CERTS_DIR)/postgresql/server.crt; \
	else \
		echo "   $(CERTS_DIR)/postgresql/server.crt already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/postgresql/client.key ]; then \
		$(OPENSSL) genrsa -out $(CERTS_DIR)/postgresql/client.key 2048; \
		chmod 600 $(CERTS_DIR)/postgresql/client.key; \
	else \
		echo "   $(CERTS_DIR)/postgresql/client.key already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/postgresql/client.crt ]; then \
		$(OPENSSL) req -new -key $(CERTS_DIR)/postgresql/client.key \
			-out $(CERTS_DIR)/postgresql/client.csr \
			-subj "/CN=postgresql-client" \
			-addext "extendedKeyUsage = clientAuth"; \
		$(OPENSSL) x509 -req -in $(CERTS_DIR)/postgresql/client.csr \
			-CA $(CA_CERT) -CAkey $(CA_KEY) $(SERIAL_OPT) \
			-out $(CERTS_DIR)/postgresql/client.crt \
			-days $(TLS_DAYS) -sha256; \
		rm -f $(CERTS_DIR)/postgresql/client.csr; \
		chmod 644 $(CERTS_DIR)/postgresql/client.crt; \
	else \
		echo "   $(CERTS_DIR)/postgresql/client.crt already exists"; \
	fi

tls-certs-pgbouncer: tls-certs-root ## Generate PGBouncer client/server TLS bundle
	@echo ">> Generating PGBouncer certificates"
	@mkdir -p $(CERTS_DIR)/pgbouncer
	@install -m 0644 $(CA_CERT) $(CERTS_DIR)/pgbouncer/ca.crt
	@if [ ! -f $(CERTS_DIR)/pgbouncer/server.key ]; then \
		$(OPENSSL) genrsa -out $(CERTS_DIR)/pgbouncer/server.key 2048; \
		chmod 600 $(CERTS_DIR)/pgbouncer/server.key; \
	else \
		echo "   $(CERTS_DIR)/pgbouncer/server.key already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/pgbouncer/server.crt ]; then \
		$(OPENSSL) req -new -key $(CERTS_DIR)/pgbouncer/server.key \
			-out $(CERTS_DIR)/pgbouncer/server.csr \
			-subj "/CN=pgbouncer-server" \
			-addext "subjectAltName = DNS:localhost,IP:127.0.0.1" \
			-addext "extendedKeyUsage = serverAuth"; \
		$(OPENSSL) x509 -req -in $(CERTS_DIR)/pgbouncer/server.csr \
			-CA $(CA_CERT) -CAkey $(CA_KEY) $(SERIAL_OPT) \
			-out $(CERTS_DIR)/pgbouncer/server.crt \
			-days $(TLS_DAYS) -sha256; \
		rm -f $(CERTS_DIR)/pgbouncer/server.csr; \
		chmod 644 $(CERTS_DIR)/pgbouncer/server.crt; \
	else \
		echo "   $(CERTS_DIR)/pgbouncer/server.crt already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/pgbouncer/client.key ]; then \
		$(OPENSSL) genrsa -out $(CERTS_DIR)/pgbouncer/client.key 2048; \
		chmod 600 $(CERTS_DIR)/pgbouncer/client.key; \
	else \
		echo "   $(CERTS_DIR)/pgbouncer/client.key already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/pgbouncer/client.crt ]; then \
		$(OPENSSL) req -new -key $(CERTS_DIR)/pgbouncer/client.key \
			-out $(CERTS_DIR)/pgbouncer/client.csr \
			-subj "/CN=pgbouncer-client" \
			-addext "extendedKeyUsage = clientAuth"; \
		$(OPENSSL) x509 -req -in $(CERTS_DIR)/pgbouncer/client.csr \
			-CA $(CA_CERT) -CAkey $(CA_KEY) $(SERIAL_OPT) \
			-out $(CERTS_DIR)/pgbouncer/client.crt \
			-days $(TLS_DAYS) -sha256; \
		rm -f $(CERTS_DIR)/pgbouncer/client.csr; \
		chmod 644 $(CERTS_DIR)/pgbouncer/client.crt; \
	else \
		echo "   $(CERTS_DIR)/pgbouncer/client.crt already exists"; \
	fi

tls-certs-redis: tls-certs-root ## Generate Redis server/client TLS bundle
	@echo ">> Generating Redis certificates"
	@mkdir -p $(CERTS_DIR)/redis
	@install -m 0644 $(CA_CERT) $(CERTS_DIR)/redis/ca.crt
	@if [ ! -f $(CERTS_DIR)/redis/server.key ]; then \
		$(OPENSSL) genrsa -out $(CERTS_DIR)/redis/server.key 2048; \
		chmod 600 $(CERTS_DIR)/redis/server.key; \
	else \
		echo "   $(CERTS_DIR)/redis/server.key already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/redis/server.crt ]; then \
		$(OPENSSL) req -new -key $(CERTS_DIR)/redis/server.key \
			-out $(CERTS_DIR)/redis/server.csr \
			-subj "/CN=redis-server" \
			-addext "subjectAltName = DNS:localhost,IP:127.0.0.1" \
			-addext "extendedKeyUsage = serverAuth"; \
		$(OPENSSL) x509 -req -in $(CERTS_DIR)/redis/server.csr \
			-CA $(CA_CERT) -CAkey $(CA_KEY) $(SERIAL_OPT) \
			-out $(CERTS_DIR)/redis/server.crt \
			-days $(TLS_DAYS) -sha256; \
		rm -f $(CERTS_DIR)/redis/server.csr; \
		chmod 644 $(CERTS_DIR)/redis/server.crt; \
	else \
		echo "   $(CERTS_DIR)/redis/server.crt already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/redis/client.key ]; then \
		$(OPENSSL) genrsa -out $(CERTS_DIR)/redis/client.key 2048; \
		chmod 600 $(CERTS_DIR)/redis/client.key; \
	else \
		echo "   $(CERTS_DIR)/redis/client.key already exists"; \
	fi
	@if [ ! -f $(CERTS_DIR)/redis/client.crt ]; then \
		$(OPENSSL) req -new -key $(CERTS_DIR)/redis/client.key \
			-out $(CERTS_DIR)/redis/client.csr \
			-subj "/CN=redis-client" \
			-addext "extendedKeyUsage = clientAuth"; \
		$(OPENSSL) x509 -req -in $(CERTS_DIR)/redis/client.csr \
			-CA $(CA_CERT) -CAkey $(CA_KEY) $(SERIAL_OPT) \
			-out $(CERTS_DIR)/redis/client.crt \
			-days $(TLS_DAYS) -sha256; \
		rm -f $(CERTS_DIR)/redis/client.csr; \
		chmod 644 $(CERTS_DIR)/redis/client.crt; \
	else \
		echo "   $(CERTS_DIR)/redis/client.crt already exists"; \
	fi

tls-certs-clean: ## Remove generated certificate artifacts
	@rm -rf $(CERTS_DIR)
	@echo "Removed $(CERTS_DIR)/"
