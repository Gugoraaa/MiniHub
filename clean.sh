#!/usr/bin/env bash

cd "$(dirname "$0")"

pkill -f 'dnsmasq.*hq/site.conf' 2>/dev/null || true
pkill -f 'dnsmasq.*tmp/dhcp_hq.conf' 2>/dev/null || true
pkill -f 'dhcrelay.*192.168.101.10' 2>/dev/null || true
pkill -f 'dhclient.*hdtest-eth0' 2>/dev/null || true
pkill -f 'python3 -m http.server 80' 2>/dev/null || true
rm -f /tmp/dnsmasq-hq.pid /tmp/dnsmasq-hq.log
rm -f /tmp/http-hq.pid /tmp/http-hq.log
rm -f tmp/dhcp_hq.pid tmp/dhcp_hq.leases tmp/dhcp_hq.log
rm -rf /tmp/hq-web
mn -c >/dev/null 2>&1 || true
