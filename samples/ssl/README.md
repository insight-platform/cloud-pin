# SSL secured setup of CloudPin service 

This is a demonstration of CloudPin with fully enabled SSL WebSockets transport. The source stream is a typical camera video. The stream passes through SSL enabled CloudPin along the following way:

Client ⟶ WebSockets SSL channel ⟶ Server ⟶ short circuit connection ⟶ Server ⟶ WebSockets SSL channel ⟶ Client

Finally the stream is output to HLS.

## To see it in action 

Run the following command:

```bash
docker compose -f samples/ssl/compose.yaml up
```

See if it works: http://localhost/stream/test

Explore metrics with Prometheus: http://localhost:9090/query