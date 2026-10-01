#!/usr/bin/env bash
#
# Manage the local TLS certificate set that the playbooks upload to the hosts.
#
#   tls-certs.sh generate DIR BUNDLE...   Create the files that are missing
#   tls-certs.sh validate DIR [BUNDLE...] Check the files that are present
#
# BUNDLE is one of: postgresql pgbouncer redis miarec miarecweb all
#
# Layout of DIR (the same for generated and customer-provided sets):
#
#   root/ca.crt      Root CA certificate (source for the per-service ca.crt copies)
#   root/ca.key      Root CA private key. Generated sets only. Customer-provided
#                    sets never contain it, and the script never asks for it
#                    unless it has to issue a new certificate.
#   <service>/...    One directory per service, see bundle_spec below.
#
# The generate command is idempotent: it never overwrites a file. Remove a
# file and run generate again to reissue it.
#
# Environment:
#   OPENSSL       openssl binary (default: openssl)
#   TLS_DAYS      validity of service certificates in days (default: 3650)
#   TLS_CA_DAYS   validity of the root CA in days (default: 3650)
#   TLS_KEY_BITS  RSA key size for service keys (default: 2048)
#   TLS_SAN       subjectAltName for server certificates
#                 (default: DNS:localhost,IP:127.0.0.1)
#   TLS_SAN_<BUNDLE>  per-service override, for example TLS_SAN_REDIS

set -euo pipefail

OPENSSL="${OPENSSL:-openssl}"
TLS_DAYS="${TLS_DAYS:-3650}"
TLS_CA_DAYS="${TLS_CA_DAYS:-3650}"
TLS_KEY_BITS="${TLS_KEY_BITS:-2048}"
TLS_SAN="${TLS_SAN:-DNS:localhost,IP:127.0.0.1}"

ALL_BUNDLES="postgresql pgbouncer redis miarec miarecweb"

# ---------------------------------------------------------------------------
# Bundle definitions
# ---------------------------------------------------------------------------

# Print one line per file of a bundle:
#   ca      <file>             copy of the root CA certificate
#   server  <name> <CN>        <name>.key and <name>.crt, a TLS server certificate
#   client  <name> <CN>        <name>.key and <name>.crt, a TLS client certificate
bundle_spec() {
    case "$1" in
        postgresql)
            echo "ca ca.crt"
            echo "server server postgresql-server"
            ;;
        pgbouncer)
            echo "ca ca.crt"
            echo "server server pgbouncer-server"
            echo "client client pgbouncer-client"
            ;;
        redis)
            echo "ca ca.crt"
            echo "server server redis-server"
            ;;
        miarec|miarecweb)
            echo "ca ca.crt"
            echo "client client $1-client"
            echo "ca redis-ca.crt"
            echo "client redis-client $1-redis-client"
            ;;
        *)
            die "unknown bundle '$1' (expected: $ALL_BUNDLES all)"
            ;;
    esac
}

# Print one line per trust relationship between bundles:
#   <cert> <purpose> <ca file that the peer uses to verify it>
# Only relationships between the selected bundles are checked.
trust_spec() {
    cat <<'SPEC'
postgresql/server.crt sslserver pgbouncer/ca.crt
postgresql/server.crt sslserver miarec/ca.crt
postgresql/server.crt sslserver miarecweb/ca.crt
pgbouncer/server.crt sslserver miarec/ca.crt
pgbouncer/server.crt sslserver miarecweb/ca.crt
pgbouncer/client.crt sslclient postgresql/ca.crt
miarec/client.crt sslclient postgresql/ca.crt
miarec/client.crt sslclient pgbouncer/ca.crt
miarecweb/client.crt sslclient postgresql/ca.crt
miarecweb/client.crt sslclient pgbouncer/ca.crt
redis/server.crt sslserver miarec/redis-ca.crt
redis/server.crt sslserver miarecweb/redis-ca.crt
miarec/redis-client.crt sslclient redis/ca.crt
miarecweb/redis-client.crt sslclient redis/ca.crt
SPEC
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() { echo "error: $*" >&2; exit 1; }
info() { echo "$*"; }

TMPDIR_WORK=""
cleanup() { if [ -n "$TMPDIR_WORK" ]; then rm -rf "$TMPDIR_WORK"; fi; }
trap cleanup EXIT

tmpdir() {
    [ -n "$TMPDIR_WORK" ] || TMPDIR_WORK="$(mktemp -d)"
    echo "$TMPDIR_WORK"
}

expand_bundles() {
    local out=""
    for b in "$@"; do
        if [ "$b" = "all" ]; then
            out="$out $ALL_BUNDLES"
        else
            bundle_spec "$b" > /dev/null   # validates the name
            out="$out $b"
        fi
    done
    # shellcheck disable=SC2086
    printf '%s\n' $out | awk '!seen[$0]++'
}

bundle_selected() {
    local needle="$1"; shift
    for b in "$@"; do [ "$b" = "$needle" ] && return 0; done
    return 1
}

upper() { echo "$1" | tr '[:lower:]' '[:upper:]'; }

# ---------------------------------------------------------------------------
# Root CA
# ---------------------------------------------------------------------------

# Sets CA_CERT, CA_KEY, CA_SERIAL and CA_CAN_SIGN for DIR.
# Generates the root CA only when neither the key nor the certificate exists.
ensure_root_ca() {
    local dir="$1"
    CA_CERT="$dir/root/ca.crt"
    CA_KEY="$dir/root/ca.key"
    CA_SERIAL="$dir/root/ca.srl"
    CA_CAN_SIGN=0

    if [ -f "$CA_CERT" ] && [ -f "$CA_KEY" ]; then
        CA_CAN_SIGN=1
    elif [ -f "$CA_CERT" ]; then
        info "Root CA: using $CA_CERT (no private key, new certificates cannot be issued)"
    elif [ -f "$CA_KEY" ]; then
        die "$CA_KEY exists but $CA_CERT is missing. Restore the certificate, or remove the key to generate a new root CA."
    else
        info "Root CA: generating $CA_CERT"
        mkdir -p "$dir/root"
        local cnf
        cnf="$(tmpdir)/ca.cnf"
        cat > "$cnf" <<'CNF'
[req]
distinguished_name = dn
x509_extensions = v3_ca
prompt = no

[dn]
CN = MiaRec-Root-CA

[v3_ca]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
CNF
        (umask 077 && "$OPENSSL" genrsa -out "$CA_KEY" 4096 2>/dev/null)
        "$OPENSSL" req -x509 -new -key "$CA_KEY" -sha256 -days "$TLS_CA_DAYS" \
            -config "$cnf" -out "$CA_CERT"
        chmod 600 "$CA_KEY"
        chmod 644 "$CA_CERT"
        CA_CAN_SIGN=1
    fi
}

# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

ensure_ca_copy() {
    local dest="$1"
    if [ -f "$dest" ]; then
        info "  keep     $dest"
        return
    fi
    [ -f "$CA_CERT" ] || die "cannot create $dest: $CA_CERT does not exist"
    info "  create   $dest"
    install -m 0644 "$CA_CERT" "$dest"
}

ensure_key() {
    local key="$1"
    if [ -f "$key" ]; then
        info "  keep     $key"
        return
    fi
    info "  create   $key"
    (umask 077 && "$OPENSSL" genrsa -out "$key" "$TLS_KEY_BITS" 2>/dev/null)
    chmod 600 "$key"
}

# ensure_cert <kind> <key> <cert> <CN> <SAN>
ensure_cert() {
    local kind="$1" key="$2" crt="$3" cn="$4" san="$5"
    if [ -f "$crt" ]; then
        info "  keep     $crt"
        return
    fi
    [ "$CA_CAN_SIGN" = 1 ] || die "cannot issue $crt: $CA_KEY does not exist. Provide the certificate yourself, or remove $CA_CERT to generate a new self-signed root CA."

    info "  create   $crt"
    local work ext csr
    work="$(tmpdir)"
    ext="$work/$(basename "$crt").ext"
    csr="$work/$(basename "$crt").csr"
    {
        echo "basicConstraints = CA:FALSE"
        echo "subjectKeyIdentifier = hash"
        echo "authorityKeyIdentifier = keyid,issuer"
        if [ "$kind" = server ]; then
            echo "keyUsage = critical, digitalSignature, keyEncipherment"
            echo "extendedKeyUsage = serverAuth"
            echo "subjectAltName = $san"
        else
            echo "keyUsage = critical, digitalSignature"
            echo "extendedKeyUsage = clientAuth"
        fi
    } > "$ext"
    "$OPENSSL" req -new -key "$key" -subj "/CN=$cn" -out "$csr"
    "$OPENSSL" x509 -req -in "$csr" -CA "$CA_CERT" -CAkey "$CA_KEY" \
        -CAserial "$CA_SERIAL" -CAcreateserial \
        -days "$TLS_DAYS" -sha256 -extfile "$ext" -out "$crt" 2>/dev/null
    chmod 644 "$crt"
}

generate_bundle() {
    local dir="$1" bundle="$2"
    local san_var
    san_var="TLS_SAN_$(upper "$bundle")"
    local san="${!san_var:-$TLS_SAN}"

    info "Bundle $bundle ($dir/$bundle)"
    mkdir -p "$dir/$bundle"
    while read -r kind name cn; do
        case "$kind" in
            ca)
                ensure_ca_copy "$dir/$bundle/$name"
                ;;
            server|client)
                local key="$dir/$bundle/$name.key" crt="$dir/$bundle/$name.crt"
                if [ -f "$crt" ] && [ ! -f "$key" ]; then
                    die "$crt exists but $key is missing. Restore the key, or remove the certificate to reissue it."
                fi
                ensure_key "$key"
                ensure_cert "$kind" "$key" "$crt" "$cn" "$san"
                ;;
        esac
    done < <(bundle_spec "$bundle")
}

cmd_generate() {
    [ $# -ge 2 ] || die "usage: $0 generate DIR BUNDLE..."
    local dir="$1"; shift
    local bundles
    bundles="$(expand_bundles "$@")"
    mkdir -p "$dir"
    ensure_root_ca "$dir"
    for b in $bundles; do
        generate_bundle "$dir" "$b"
    done
    info "Done. Run '$0 validate $dir' to check the set."
}

# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

FAILS=0
WARNS=0
ok()   { echo "[ OK ] $*"; }
warn() { echo "[WARN] $*"; WARNS=$((WARNS + 1)); }
fail() { echo "[FAIL] $*"; FAILS=$((FAILS + 1)); }

pubkey_of_key()  { "$OPENSSL" pkey -in "$1" -pubout 2>/dev/null; }
pubkey_of_cert() { "$OPENSSL" x509 -in "$1" -pubkey -noout 2>/dev/null; }

check_cert_readable() {
    "$OPENSSL" x509 -in "$1" -noout 2>/dev/null
}

check_key_readable() {
    "$OPENSSL" pkey -in "$1" -noout 2>/dev/null
}

check_validity() {
    local crt="$1"
    local end
    end="$("$OPENSSL" x509 -in "$crt" -noout -enddate | cut -d= -f2)"
    if ! "$OPENSSL" x509 -in "$crt" -noout -checkend 0 > /dev/null; then
        fail "$crt expired on $end"
    elif ! "$OPENSSL" x509 -in "$crt" -noout -checkend $((30 * 86400)) > /dev/null; then
        warn "$crt expires within 30 days ($end)"
    else
        ok "$crt valid until $end"
    fi
}

check_is_ca() {
    local crt="$1"
    if "$OPENSSL" x509 -in "$crt" -noout -text | grep -q 'CA:TRUE'; then
        ok "$crt is a CA certificate"
    else
        warn "$crt has no basicConstraints CA:TRUE"
    fi
}

check_pair() {
    local key="$1" crt="$2"
    if [ "$(pubkey_of_key "$key")" = "$(pubkey_of_cert "$crt")" ]; then
        ok "$crt matches $key"
    else
        fail "$crt does not match $key"
    fi
}

# check_trust <cert> <purpose> <ca file>
check_trust() {
    local crt="$1" purpose="$2" ca="$3"
    local out
    if out="$("$OPENSSL" verify -purpose "$purpose" -CAfile "$ca" "$crt" 2>&1)"; then
        ok "$crt is trusted by $ca ($purpose)"
    else
        fail "$crt is NOT trusted by $ca ($purpose): $(echo "$out" | grep -v '^C = \|OK$' | tr '\n' ' ')"
    fi
}

check_same_ca() {
    local copy="$1" root="$2"
    if cmp -s "$copy" "$root"; then
        ok "$copy is identical to $root"
    else
        fail "$copy differs from $root"
    fi
}

validate_bundle() {
    local dir="$1" bundle="$2" root_cert="$3"
    echo "-- $bundle"
    local prefix="$dir/$bundle"
    while read -r kind name _; do
        case "$kind" in
            ca)
                local ca="$prefix/$name"
                if [ ! -f "$ca" ]; then fail "$ca is missing"; continue; fi
                if ! check_cert_readable "$ca"; then fail "$ca is not a PEM certificate"; continue; fi
                check_validity "$ca"
                check_is_ca "$ca"
                [ -n "$root_cert" ] && check_same_ca "$ca" "$root_cert"
                ;;
            server|client)
                local key="$prefix/$name.key" crt="$prefix/$name.crt"
                local good=1
                if [ ! -f "$key" ]; then fail "$key is missing"; good=0; fi
                if [ ! -f "$crt" ]; then fail "$crt is missing"; good=0; fi
                [ "$good" = 1 ] || continue
                if ! check_key_readable "$key"; then fail "$key is not a PEM private key"; good=0; fi
                if ! check_cert_readable "$crt"; then fail "$crt is not a PEM certificate"; good=0; fi
                [ "$good" = 1 ] || continue
                check_validity "$crt"
                check_pair "$key" "$crt"
                if [ -n "$root_cert" ]; then
                    check_trust "$crt" "ssl$kind" "$root_cert"
                fi
                ;;
        esac
    done < <(bundle_spec "$bundle")
}

cmd_validate() {
    [ $# -ge 1 ] || die "usage: $0 validate DIR [BUNDLE...]"
    local dir="$1"; shift
    [ -d "$dir" ] || die "$dir does not exist"
    local bundles
    if [ $# -eq 0 ]; then
        bundles="$(expand_bundles all)"
    else
        bundles="$(expand_bundles "$@")"
    fi

    echo "Validating TLS certificate set in $dir"
    echo "-- root CA"
    local root_cert=""
    if [ -f "$dir/root/ca.crt" ]; then
        root_cert="$dir/root/ca.crt"
        if check_cert_readable "$root_cert"; then
            check_validity "$root_cert"
            check_is_ca "$root_cert"
        else
            fail "$root_cert is not a PEM certificate"
            root_cert=""
        fi
        if [ -f "$dir/root/ca.key" ]; then
            if check_key_readable "$dir/root/ca.key"; then
                check_pair "$dir/root/ca.key" "$dir/root/ca.crt"
            else
                fail "$dir/root/ca.key is not a PEM private key"
            fi
        else
            ok "$dir/root/ca.key is absent (external CA, generate cannot issue new certificates)"
        fi
    else
        ok "$dir/root is absent (external CA, per-service CA files are checked against each other)"
    fi

    for b in $bundles; do
        validate_bundle "$dir" "$b" "$root_cert"
    done

    echo "-- trust between services"
    local any=0
    while read -r crt purpose ca; do
        bundle_selected "${crt%%/*}" $bundles || continue
        bundle_selected "${ca%%/*}" $bundles || continue
        [ -f "$dir/$crt" ] && [ -f "$dir/$ca" ] || continue
        check_trust "$dir/$crt" "$purpose" "$dir/$ca"
        any=1
    done < <(trust_spec)
    [ "$any" = 1 ] || echo "(nothing to check for the selected bundles)"

    echo
    if [ "$FAILS" -gt 0 ]; then
        echo "FAILED: $FAILS problem(s), $WARNS warning(s)"
        return 1
    fi
    echo "OK: no problems, $WARNS warning(s)"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

usage() {
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

command -v "$OPENSSL" > /dev/null 2>&1 || die "$OPENSSL not found (set OPENSSL to the openssl binary)"

case "${1:-}" in
    generate) shift; cmd_generate "$@" ;;
    validate) shift; cmd_validate "$@" ;;
    -h|--help|help|"") usage; [ -n "${1:-}" ] || exit 1 ;;
    *) die "unknown command '$1' (expected: generate, validate)" ;;
esac
