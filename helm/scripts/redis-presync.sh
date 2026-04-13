#!/bin/bash

set -x  # Print each command
set +e  # Disable immediate exit on error
echo "Starting sso-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"


# Create configmap
create_or_update_configmap redis-config \
  --from-literal=redis_port="$redis_port" \
  --from-literal=redis_password="$redis_password" 