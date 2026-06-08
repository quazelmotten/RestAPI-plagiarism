#!/bin/sh
set -e

AMQP_PORT="${RMQ_PORT:-5777}"
MGMT_PORT="${RABBITMQ_MANAGEMENT_PORT:-15672}"
DIST_PORT="${RABBITMQ_DIST_PORT:-25672}"

cat > /etc/rabbitmq/rabbitmq.conf << EOF
listeners.tcp.default = ${AMQP_PORT}
management.tcp.port = ${MGMT_PORT}
EOF

cat > /etc/rabbitmq/advanced.config << EOF
[
  {kernel, [
    {inet_dist_listen_min, ${DIST_PORT}},
    {inet_dist_listen_max, ${DIST_PORT}}
  ]},
  {rabbit, [
    {tcp_listeners, [${AMQP_PORT}]}
  ]},
  {rabbitmq_management, [
    {listener, [{port, ${MGMT_PORT}}]}
  ]}
].
EOF

exec /usr/local/bin/docker-entrypoint.sh "$@"
