# SSL secured CloudPin setup with Nginx

This is a demonstration of how Nginx can be used and have SSL WebSockets transport. The source stream is a typical camera video. The stream passes through SSL enabled CloudPin client and CloudPin server behind Nginx as a HTTPS proxy and  along the following way:

Client ⟶ WebSockets SSL ⟶ Nginx ⟶ WebSockets ⟶ Server ⟶ short circuit connection ⟶ Server ⟶ WebSockets ⟶ Nginx ⟶ WebSockets SSL ⟶ Client

Finally the stream is output to HLS.

## To see it in action 

Run the following command:

```bash
docker compose -f samples/nginx/compose.yaml up
```

See if it works: http://localhost/stream/test

Explore metrics with Prometheus: http://localhost:9090/query