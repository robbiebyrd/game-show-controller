#!/usr/bin/env bash
# Tunnel OLA RPC port (9010) from Pi to localhost:9010
ssh -N -L 9011:localhost:9010 robbiebyrd@10.11.0.104
