FROM ghcr.io/insight-platform/savant-rs-py314:savant-latest AS build

RUN apt-get update && apt-get install -y build-essential
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /build/
WORKDIR /build/
RUN uv pip install --system --requirements pyproject.toml && \
    uv build && \
    CLOUDPIN_VERSION=`uv version --short` && \
    uv pip install --system "savant-cloudpin @ /build/dist/savant_cloudpin-$CLOUDPIN_VERSION.tar.gz"

WORKDIR /
RUN uv cache clean && \
    apt-get remove -y build-essential && \
    apt autoremove -y && \
    apt clean && \
    rm -rf /bin/uv /bin/uvx /build /var/lib/apt/lists/*


FROM build AS savant-cloudpin

ENTRYPOINT ["python", "-m", "savant_cloudpin"]