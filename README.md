# Savant CloudPin Service

[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/insight-platform/cloud-pin)
[![Checks](https://github.com/insight-platform/cloud-pin/actions/workflows/checks.yml/badge.svg?event=push)](https://github.com/insight-platform/cloud-pin/actions/workflows/checks.yml)

A service to run Savant pipeline remotely (cloud) via WebSockets (WS).


![CloudPin service overview diagram](docs/img/service-overview.drawio.svg)

where channels:
* Client CloudPin:
  * Pipeline source (ZMQ Router) - 1
  * Pipeline sink (ZMQ Dealer) - 6
  * Upstream bridge (WS) - 2
* Server CloudPin:
  * Pipeline sink (ZMQ Dealer) - 3
  * Pipeline source (ZMQ Router) - 4
  * Downstream bridge (WS) - 5

There are [samples and benchmarks](samples/README.md)