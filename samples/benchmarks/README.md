# Benchmarks

Here is a benchmark of CloudPin with fully enabled SSL WebSockets transport. The source stream is a video loop. You can run the benchmark with the stream synchronization enabled or without it, meaning it runs at a normal or at a higher frame rate. The stream passes through SSL enabled CloudPin along the following way:

Client ⟶ WebSockets SSL channel ⟶ Server ⟶ short circuit connection ⟶ Server ⟶ WebSockets SSL channel ⟶ Client

Benchmark results are placed in [samples/benchmarks/reports/](./reports/) directory.

## Run the benchmark

* no synchronization:
    ```bash
    docker compose -f samples/benchmarks/compose.no-sync.yaml up --exit-code-from=benchmark
    ```
* with synchronization:
    ```bash
    docker compose -f samples/benchmarks/compose.sync.yaml up --exit-code-from=benchmark
    ```