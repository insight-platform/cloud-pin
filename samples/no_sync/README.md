# Plain HTTP CloudPin with unlimited frame rate source 

This is a performace demonstration of  CloudPin with plain HTTP WebSockets transport without SSL. The source stream is a video loop without sync enabled, running at higher that the ordinary frame rate. The stream passes through CloudPin along the following way:

Client ⟶ WebSockets channel ⟶ Server ⟶ short circuit connection ⟶ Server ⟶ WebSockets channel ⟶ Client

Finally the stream is output to HLS.

## To see it in action 

Run the following command:

```bash
docker compose -f samples/no_sync/compose.yaml up
```

See if it works: http://localhost/stream/test

Explore metrics with Prometheus: http://localhost:9090/query