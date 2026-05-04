#!/usr/bin/env bash
# Source before running the SSO backend, e.g.:
#   source ./source-keycloak-stage-env.sh
#   python app.py

export KEYCLOAK_BASE_URL="https://auth.stage.redhat.com/auth"
export CLIENT_ID="TAG-001"
export CLIENT_SECRET="a0a82b17-e7e7-49c6-ad1c-3d03c79ff4fd"
export KEYCLOAK_REALM="EmployeeIDP"
export hostname_local="127.0.0.1"
export port="13456"
export frontend_url="http://127.0.0.1:5000"
export backend_env="development"
export redis_host="127.0.0.1"
export redis_port=6379
export redis_db=1
export redis_password=""
export redis_decode_responses=True
export redis_session_ttl=3600
