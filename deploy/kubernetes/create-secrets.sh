#!/bin/sh

set -eu
set +x

mode="create"
namespace="tempconverter"
secret_name="tempconverter-runtime"
temp_dir=""
random_source=""

case "${1:-}" in
    create | normalize)
        mode="$1"
        namespace="${2:-tempconverter}"
        ;;
    "")
        ;;
    *)
        namespace="$1"
        ;;
esac

cleanup() {
    if [ -n "$temp_dir" ] && [ -d "$temp_dir" ]; then
        rm -f \
            "$temp_dir/db-password" \
            "$temp_dir/db-root-password" \
            "$temp_dir/flask-secret-key"
        rmdir "$temp_dir" 2>/dev/null || true
    fi
}

fail() {
    echo "error=$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1-not-found"
}

write_random_hex() {
    byte_count="$1"
    output_file="$2"

    if [ "$random_source" = "openssl" ]; then
        random_value="$(openssl rand -hex "$byte_count")"
    else
        random_value="$(
            od -An -N "$byte_count" -tx1 /dev/urandom |
                tr -d '[:space:]'
        )"
    fi

    expected_length=$((byte_count * 2))
    [ "${#random_value}" -eq "$expected_length" ] ||
        fail "random-generation-failed"

    printf '%s' "$random_value" >"$output_file"
    unset random_value
}

normalize_key() {
    key="$1"
    expected_length="$2"
    encoded_value="$(
        kubectl get secret "$secret_name" \
            --namespace "$namespace" \
            --output "jsonpath={.data['$key']}"
    )"

    [ -n "$encoded_value" ] || fail "missing-secret-key-$key"

    if ! decoded_value="$(printf '%s' "$encoded_value" | base64 -d)"; then
        fail "invalid-secret-key-$key"
    fi
    unset encoded_value

    # POSIX command substitution removes trailing line endings only.
    printf '%s' "$decoded_value" >"$temp_dir/$key"
    unset decoded_value
    actual_length="$(wc -c <"$temp_dir/$key" | tr -d '[:space:]')"
    [ "$actual_length" -eq "$expected_length" ] ||
        fail "unexpected-secret-key-length-$key"
}

trap cleanup EXIT HUP INT TERM
require_command kubectl

kubectl get namespace "$namespace" >/dev/null 2>&1 ||
    fail "namespace-not-found"

umask 077
temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/tempconverter-secrets.XXXXXX")"

if [ "$mode" = "normalize" ]; then
    require_command base64
    require_command tr
    require_command wc

    kubectl get secret "$secret_name" \
        --namespace "$namespace" >/dev/null 2>&1 ||
        fail "secret-not-found"

    normalize_key db-password 64
    normalize_key db-root-password 64
    normalize_key flask-secret-key 96

    kubectl create secret generic "$secret_name" \
        --namespace "$namespace" \
        --from-file="db-password=$temp_dir/db-password" \
        --from-file="db-root-password=$temp_dir/db-root-password" \
        --from-file="flask-secret-key=$temp_dir/flask-secret-key" \
        --dry-run=client \
        --output=yaml |
        kubectl apply --filename=- >/dev/null

    echo "secret=$secret_name namespace=$namespace status=normalized-for-env"
    exit 0
fi

if kubectl get secret "$secret_name" \
    --namespace "$namespace" >/dev/null 2>&1; then
    fail "secret-already-exists"
fi

if command -v openssl >/dev/null 2>&1; then
    random_source="openssl"
elif [ -r /dev/urandom ] &&
    command -v od >/dev/null 2>&1 &&
    command -v tr >/dev/null 2>&1; then
    random_source="urandom"
else
    fail "secure-random-source-not-found"
fi

write_random_hex 32 "$temp_dir/db-password"
write_random_hex 32 "$temp_dir/db-root-password"
write_random_hex 48 "$temp_dir/flask-secret-key"

kubectl create secret generic "$secret_name" \
    --namespace "$namespace" \
    --from-file="db-password=$temp_dir/db-password" \
    --from-file="db-root-password=$temp_dir/db-root-password" \
    --from-file="flask-secret-key=$temp_dir/flask-secret-key" \
    >/dev/null

echo "secret=$secret_name namespace=$namespace status=created"
