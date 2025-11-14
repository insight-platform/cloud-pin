# Plain HTTP setup of CloudPin service 

This is a demonstration of CloudPin with plain HTTP WebSockets transport without SSL. The source stream is a typical camera video. The stream passes through CloudPin along the following way:

Client ⟶ WebSockets channel ⟶ Server ⟶ short circuit connection ⟶ Server ⟶ WebSockets channel ⟶ Client

Finally the stream is output to HLS.

## To see it in action 

Run the following command:

```bash
docker compose -f samples/http/compose.yaml up
```

See if it works: http://localhost/stream/test

Explore metrics with Prometheus: http://localhost:9090/query