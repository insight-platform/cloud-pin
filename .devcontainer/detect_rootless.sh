ROOTLESS_DETECTED=`docker context inspect | sed  -n s/rootless/ROOTLESS/ip`

if [ "$ROOTLESS_DETECTED" -a "$DOCKER_MODE" != "rootless" ]
then
	echo "\nERROR: Docker runs in ROOTLESS MODE. " >&2
	echo "Set DOCKER_MODE environment variable to 'rootless' and try again. " >&2
	echo "\tFor instance run VS Code with 'DOCKER_MODE=rootless code .'\n" >&2

	exit 1
fi
