#!/usr/bin/env sh

ROOTLESS_DETECTED=`docker context inspect | sed -n s/rootless/ROOTLESS/ip`

if [ -z "$ROOTLESS_DETECTED" ]
then
	echo "\nINFO: Rootful Docker is detected. OK "
	exit 0
fi

ROOTLESS_SET_BY_ENV_FILE=`cat .devcontainer/.env 2>&1 | sed -n s/DOCKER_MODE=rootless/ROOTLESS/ip`

if [ "$ROOTLESS_SET_BY_ENV_FILE" -o "$DOCKER_MODE" = "rootless" ]
then
	echo "\nINFO: Rootless Docker is detected. OK "
	exit 0
fi

echo "\nERROR: Docker runs in ROOTLESS MODE. " >&2
echo "Set DOCKER_MODE environment variable to 'rootless' and try again. " >&2
echo "You can do it with .env file as well by placing it at '.devcontainer/.env'. " >&2
echo "\tFor instance run VS Code with 'DOCKER_MODE=rootless code .'" >&2
echo "\tor create .env file with 'echo DOCKER_MODE=rootless >> .devcontainer/.env'\n" >&2
exit 1
