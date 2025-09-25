#!/bin/bash
echo url="https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=" \
| curl -k -o /dev/stdout -K -
