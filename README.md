# Savant CloudPin Service

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
