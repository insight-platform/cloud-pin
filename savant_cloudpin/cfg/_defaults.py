from omegaconf import SI, OmegaConf

from savant_cloudpin.cfg._models import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    LoadConfig,
    ReaderConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    SSLCertConfig,
    SSLCertKeyConfig,
    WriterConfig,
)

DEFAULT_SOURCE_CONFIG = ReaderConfig(
    results_queue_size=SI("${oc.env:CLOUDPIN_SOURCE_RESULTS_QUEUE_SIZE,100}"),
    url="${oc.env:CLOUDPIN_SOURCE_URL,???}",
    receive_timeout=SI("${oc.env:CLOUDPIN_SOURCE_RECEIVE_TIMEOUT,null}"),
    receive_hwm=SI("${oc.env:CLOUDPIN_SOURCE_RECEIVE_HWM,null}"),
    topic_prefix_spec="${oc.env:CLOUDPIN_SOURCE_TOPIC_PREFIX_SPEC,null}",
    routing_ids_cache_size=SI("${oc.env:CLOUDPIN_ROUTING_IDS_CACHE_SIZE,null}"),
    fix_ipc_permissions=("${oc.env:CLOUDPIN_SOURCE_FIX_IPC_PERMISSIONS,null}"),
    source_blacklist_size=SI("${oc.env:CLOUDPIN_SOURCE_SOURCE_BLACKLIST_SIZE,null}"),
    source_blacklist_ttl=SI("${oc.env:CLOUDPIN_SOURCE_SOURCE_BLACKLIST_TTL,null}"),
)
DEFAULT_SINK_CONFIG = WriterConfig(
    max_inflight_messages=SI("${oc.env:CLOUDPIN_SINK_MAX_INFLIGHT_MESSAGES,100}"),
    url="${oc.env:CLOUDPIN_SINK_URL,???}",
    send_timeout=SI("${oc.env:CLOUDPIN_SINK_SEND_TIMEOUT,null}"),
    send_retries=SI("${oc.env:CLOUDPIN_SINK_SEND_RETRIES,null}"),
    send_hwm=SI("${oc.env:CLOUDPIN_SINK_SEND_HWM,null}"),
    receive_timeout=SI("${oc.env:CLOUDPIN_SINK_RECEIVE_TIMEOUT,null}"),
    receive_retries=SI("${oc.env:CLOUDPIN_SINK_RECEIVE_RETRIES,null}"),
    receive_hwm=SI("${oc.env:CLOUDPIN_SINK_RECEIVE_HWM,null}"),
    fix_ipc_permissions=SI("${oc.env:CLOUDPIN_SINK_FIX_IPC_PERMISSIONS,null}"),
)


DEFAULT_LOAD_CONFIG = LoadConfig(
    config="${oc.env:CLOUDPIN_CONFIG_FILE,./cloudpin.yml}",
    mode="${oc.env:CLOUDPIN_MODE,client}",
)

DEFAULT_CLIENT_CONFIG = ClientServiceConfig(
    websockets=ClientWSConfig(
        server_url="${oc.env:CLOUDPIN_WEBSOCKETS_SERVER_URL,???}",
        api_key="${oc.env:CLOUDPIN_WEBSOCKETS_API_KEY,???}",
        ssl=ClientSSLConfig(
            server=SSLCertConfig(
                certificate_path="${oc.env:CLOUDPIN_WEBSOCKETS_SSL_SERVER_CERTIFICATE_PATH,???}",
            ),
            client=SSLCertKeyConfig(
                certificate_path="${oc.env:CLOUDPIN_WEBSOCKETS_SSL_CLIENT_CERTIFICATE_PATH,???}",
                private_key_path="${oc.env:CLOUDPIN_WEBSOCKETS_SSL_CLIENT_PRIVATE_KEY_PATH,???}",
            ),
            disable_client_auth=SI(
                "${oc.env:CLOUDPIN_WEBSOCKETS_SSL_DISABLE_CLIENT_AUTH,false}"
            ),
            check_hostname=SI("${oc.env:CLOUDPIN_WEBSOCKETS_SSL_CHECK_HOSTNAME,true}"),
        ),
    ),
    io_timeout=SI("${oc.env:CLOUDPIN_IO_TIMEOUT,0.1}"),
    source=OmegaConf.structured(
        DEFAULT_SOURCE_CONFIG, flags={"throw_on_missing": True}
    ),
    sink=OmegaConf.structured(DEFAULT_SINK_CONFIG, flags={"throw_on_missing": True}),
)

DEFAULT_SERVER_CONFIG = ServerServiceConfig(
    websockets=ServerWSConfig(
        server_url="${oc.env:CLOUDPIN_WEBSOCKETS_SERVER_URL,???}",
        api_key="${oc.env:CLOUDPIN_WEBSOCKETS_API_KEY,???}",
        disable_ssl=SI("${oc.env:CLOUDPIN_WEBSOCKETS_DISABLE_SSL,false}"),
        ssl=ServerSSLConfig(
            server=SSLCertKeyConfig(
                certificate_path="${oc.env:CLOUDPIN_WEBSOCKETS_SSL_SERVER_CERTIFICATE_PATH,???}",
                private_key_path="${oc.env:CLOUDPIN_WEBSOCKETS_SSL_SERVER_PRIVATE_KEY_PATH,???}",
            ),
            client=SSLCertConfig(
                certificate_path="${oc.env:CLOUDPIN_WEBSOCKETS_SSL_CLIENT_CERTIFICATE_PATH,???}",
            ),
            disable_client_auth=SI(
                "${oc.env:CLOUDPIN_WEBSOCKETS_SSL_DISABLE_CLIENT_AUTH,false}"
            ),
        ),
    ),
    io_timeout=SI("${oc.env:CLOUDPIN_IO_TIMEOUT,0.1}"),
    source=OmegaConf.structured(
        DEFAULT_SOURCE_CONFIG, flags={"throw_on_missing": True}
    ),
    sink=OmegaConf.structured(DEFAULT_SINK_CONFIG, flags={"throw_on_missing": True}),
)
