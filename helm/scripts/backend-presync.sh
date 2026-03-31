#!/bin/bash

set -x  # Print each command
set +e  # Disable immediate exit on error
echo "Starting backend-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

# Note: admin_allowed_users should be a JSON array string, e.g., '["user1","user2"]'
# This will be parsed by Pydantic Settings as a list type
# Create configmap
create_or_update_configmap backend-be-security \
  --from-literal=admin_allowed_users="$admin_allowed_users"
