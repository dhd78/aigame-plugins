# Security

## Local-only HTTP

The bridge listens on:

```text
127.0.0.1:15528
```

It does not bind `0.0.0.0` or a LAN address.

## No authentication

The local HTTP API has no token or authentication:

- any local process can call `/state` and read the current dialogue;
- any local process can call `/advance` and send a click;
- do not expose the port through a proxy, tunnel, or firewall rule.

If multiple users share the machine, treat the port as readable/writable by
them.

## Reporting

Include:

- bridge version;
- Windows version;
- game version;
- dump path;
- `%TEMP%\senren-read-bridge.log`.
