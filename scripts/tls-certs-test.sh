#!/usr/bin/env bash
#
# Regression tests of scripts/tls-certs.sh. They need only openssl and run in
# a few seconds:
#
#   scripts/tls-certs-test.sh        or        make tls-certs-test
#
# The tests generate a self-signed set with the script and validate it, and
# then build a certificate set issued by a two-level CA (root and intermediate)
# with openssl, in the layouts that an operator may provide, and check that the
# validator accepts the valid ones and rejects the broken ones.
#
# Environment:
#   OPENSSL   openssl binary (default: openssl)

set -euo pipefail

OPENSSL="${OPENSSL:-openssl}"
HERE="$(cd "$(dirname "$0")" && pwd)"
TLS_CERTS="$HERE/tls-certs.sh"

WORK="$(mktemp -d)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

PASSED=0
FAILED=0

# expect <ok|fail> <description> -- <validate arguments>
# Runs the validator and compares its exit status with the expectation. On a
# mismatch, prints the validator output.
expect() {
    local want="$1" what="$2"; shift 3
    local out rc=0
    out="$("$TLS_CERTS" validate "$@" 2>&1)" || rc=$?
    if { [ "$want" = ok ] && [ $rc -eq 0 ]; } || { [ "$want" = fail ] && [ $rc -ne 0 ]; }; then
        echo "PASS  $what"
        PASSED=$((PASSED + 1))
    else
        echo "FAIL  $what (validator exit status $rc, expected $want)"
        echo "$out" | sed 's/^/      /'
        FAILED=$((FAILED + 1))
    fi
}

# ---------------------------------------------------------------------------
# A two-level CA: root -> intermediate -> leaf certificates. The extension
# files keep the commands compatible with OpenSSL 1.0.2, which has no -addext.
# ---------------------------------------------------------------------------

CA="$WORK/ca"
mkdir -p "$CA"

cat > "$CA/ca.cnf" <<'CNF'
[req]
distinguished_name = dn
x509_extensions = v3_ca
prompt = no
[dn]
CN = Test Root CA
[v3_ca]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
CNF

cat > "$CA/intermediate.ext" <<'EXT'
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid, issuer
EXT

cat > "$CA/server.ext" <<'EXT'
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:localhost, IP:127.0.0.1
EXT

cat > "$CA/client.ext" <<'EXT'
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = clientAuth
EXT

# new_ca <name> <cnf>: a self-signed CA certificate and key
new_ca() {
    "$OPENSSL" req -x509 -new -newkey rsa:2048 -nodes -sha256 -days 3650 \
        -config "$2" -keyout "$CA/$1.key" -out "$CA/$1.crt" 2>/dev/null
}

# issue <issuer> <name> <CN> <ext file>: a certificate signed by an issuer
issue() {
    local issuer="$1" name="$2" cn="$3" ext="$4"
    "$OPENSSL" genrsa -out "$CA/$name.key" 2048 2>/dev/null
    "$OPENSSL" req -new -key "$CA/$name.key" -subj "/CN=$cn" -out "$CA/$name.csr" 2>/dev/null
    "$OPENSSL" x509 -req -in "$CA/$name.csr" -CA "$CA/$issuer.crt" -CAkey "$CA/$issuer.key" \
        -CAcreateserial -days 3650 -sha256 -extfile "$ext" -out "$CA/$name.crt" 2>/dev/null
}

new_ca root "$CA/ca.cnf"
issue root intermediate "Test Issuing CA" "$CA/intermediate.ext"
issue intermediate pg-server "postgresql" "$CA/server.ext"
issue intermediate pgb-server "pgbouncer" "$CA/server.ext"
issue intermediate pgb-client "pgbouncer-client" "$CA/client.ext"
issue intermediate redis-server "redis" "$CA/server.ext"
issue intermediate miarec-db-client "miarec-db-client" "$CA/client.ext"
issue intermediate miarec-redis-client "miarec-redis-client" "$CA/client.ext"
issue intermediate miarecweb-db-client "miarecweb-db-client" "$CA/client.ext"
issue intermediate miarecweb-redis-client "miarecweb-redis-client" "$CA/client.ext"

# A CA that no service trusts
sed 's/Test Root CA/Foreign Root CA/' "$CA/ca.cnf" > "$CA/foreign.cnf"
new_ca foreign "$CA/foreign.cnf"
issue foreign foreign-client "miarecweb-db-client" "$CA/client.ext"

# layout <dir> <cert file content> <ca file content>
#
# Writes a complete customer-provided set. The cert mode "leaf" writes the
# leaf certificate alone, "chain" the leaf followed by the intermediate. The
# CA mode "root" writes the root alone, "root+intermediate" both.
layout() {
    local dir="$1" cert_mode="$2" ca_mode="$3"
    rm -rf "$dir"
    mkdir -p "$dir/postgresql" "$dir/pgbouncer" "$dir/redis" "$dir/miarec" "$dir/miarecweb"
    put_cert() {  # <name> <dest>
        cp "$CA/$1.key" "$2.key"
        chmod 600 "$2.key"
        cp "$CA/$1.crt" "$2.crt"
        [ "$cert_mode" = chain ] && cat "$CA/intermediate.crt" >> "$2.crt"
        return 0
    }
    put_ca() {  # <dest>
        cp "$CA/root.crt" "$1"
        [ "$ca_mode" = root+intermediate ] && cat "$CA/intermediate.crt" >> "$1"
        return 0
    }
    put_ca "$dir/postgresql/ca.crt"
    put_cert pg-server "$dir/postgresql/server"
    put_ca "$dir/pgbouncer/ca.crt"
    put_cert pgb-server "$dir/pgbouncer/server"
    put_cert pgb-client "$dir/pgbouncer/client"
    put_ca "$dir/redis/ca.crt"
    put_cert redis-server "$dir/redis/server"
    for app in miarec miarecweb; do
        put_ca "$dir/$app/db-ca.crt"
        put_cert "$app-db-client" "$dir/$app/db-client"
        put_ca "$dir/$app/redis-ca.crt"
        put_cert "$app-redis-client" "$dir/$app/redis-client"
    done
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

echo "-- generated set"
"$TLS_CERTS" generate "$WORK/generated" all > /dev/null
expect ok "the generated self-signed set is valid" -- "$WORK/generated"
expect ok "the generated set is valid bundle by bundle" -- "$WORK/generated" postgresql miarecweb

echo "-- set issued by a root CA through an intermediate CA"
layout "$WORK/chain" chain root
expect ok "chain in the certificate files, root alone in the CA files" -- "$WORK/chain"
layout "$WORK/cafile" leaf root+intermediate
expect ok "leaf alone in the certificate files, root and intermediate in the CA files" -- "$WORK/cafile"
layout "$WORK/both" chain root+intermediate
expect ok "chain in the certificate files and intermediate in the CA files" -- "$WORK/both"

echo "-- broken sets"
layout "$WORK/missing" leaf root
expect fail "the intermediate is in neither file" -- "$WORK/missing"

layout "$WORK/foreign" chain root
cp "$CA/foreign-client.crt" "$WORK/foreign/miarecweb/db-client.crt"
cp "$CA/foreign-client.key" "$WORK/foreign/miarecweb/db-client.key"
chmod 600 "$WORK/foreign/miarecweb/db-client.key"
expect fail "a client certificate that a foreign CA issued" -- "$WORK/foreign"

layout "$WORK/mismatch" chain root
cp "$CA/pgb-server.key" "$WORK/mismatch/postgresql/server.key"
chmod 600 "$WORK/mismatch/postgresql/server.key"
expect fail "a private key that does not match its certificate" -- "$WORK/mismatch"

layout "$WORK/purpose" chain root
cp "$WORK/purpose/postgresql/server.crt" "$WORK/purpose/miarecweb/db-client.crt"
cp "$WORK/purpose/postgresql/server.key" "$WORK/purpose/miarecweb/db-client.key"
expect fail "a server certificate in the place of a client certificate" -- "$WORK/purpose"

layout "$WORK/absent" chain root
rm "$WORK/absent/redis/server.crt"
expect fail "a missing certificate file" -- "$WORK/absent"

echo
if [ "$FAILED" -gt 0 ]; then
    echo "FAILED: $FAILED of $((PASSED + FAILED)) tests"
    exit 1
fi
echo "OK: $PASSED tests passed"
