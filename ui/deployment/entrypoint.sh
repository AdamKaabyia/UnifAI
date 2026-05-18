#!/bin/sh
set -e

: "${VERSION:=N/A}"
: "${TEAM_MEMBERS:=Lina Abu Yousef,Maya Carmi,Nir Rashti,Odai Odeh,Omri Sabach,Saar Fireshtein,Shani Tzvi,Yosi Habushi}"
: "${SUPPORT_LINK:=https://redhat-internal.slack.com/app_redirect?channel=forum-unifai}"

cat <<EOF > /usr/share/nginx/html/config.json
{
  "version": "${VERSION}",
  "teamMembers": "${TEAM_MEMBERS}",
  "supportLink": "${SUPPORT_LINK}"
}
EOF

# Replace env vars inside nginx.conf
export DOLLAR='$'
envsubst < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Start nginx
exec nginx -g 'daemon off;'
