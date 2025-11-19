#!/usr/bin/env sh

CA_NAME=demo

# Setup a demo authority
if ! [ -f "demoCA/private/cakey.pem" -a -f "demoCA/cacert.pem" ]
then
    mkdir -p demoCA
    mkdir -p demoCA/private
    mkdir -p demoCA/newcerts
    touch demoCA/index.txt
    echo "01" > demoCA/serial

    openssl req -new -x509 -days 3650 -noenc -extensions v3_ca \
        -keyout demoCA/private/cakey.pem -out demoCA/cacert.pem \
        -subj "/CN=$CA_NAME/C=US/ST=California/L=San Francisco/O=$CA_NAME" \
        -addext "keyUsage=critical,digitalSignature,keyCertSign"
fi

# Create server/client keys and certificates signed by the demo authority
for name in ${SERVER_NAME:-server} ${CLIENT_NAME:-client}
do
    if [ -f "$name.key" -a -f "$name.pem" ]
    then
        continue
    fi
    openssl genrsa -out $name.key 2048
    openssl req -new -key $name.key -out $name.csr \
        -subj "/CN=$name/C=US/ST=California/L=San Francisco/O=$CA_NAME"
    openssl ca -batch -in $name.csr -out $name.pem
done
