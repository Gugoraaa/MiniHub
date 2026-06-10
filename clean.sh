#!/usr/bin/env bash

pkill -f 'dnsmasq.*hq/site.conf' 2>/dev/null || true
rm -f /tmp/dnsmasq-hq.pid /tmp/dnsmasq-hq.log
mn -c >/dev/null 2>&1 || true
