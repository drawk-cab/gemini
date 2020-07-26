#!/bin/bash

export DIR=~/.gemini
export SUBDIR=test
mkdir -p "$DIR"/"$SUBDIR"
pushd "$DIR"
cd "$SUBDIR"


export CN=evad

export CLIENT_SN=$(date +"%Y%m%d%H%M%S")

if [ ! -f ../ca/ca.pem ]
then
  echo "Need a certificate authority first"
  exit 1
fi

if [ ! -f ../ca/ca.key ]
then
  echo "Need a certificate authority first"
  exit 1
fi

echo "### Generating your key"

openssl genrsa -aes256 -passout pass:xxxx -out client.pass.key 4096 
openssl rsa -passin pass:xxxx -in client.pass.key -out client.key
rm client.pass.key

openssl req -passout pass:xxxx -new -key client.key -out client.csr -subj "/C=XX/ST=/L=/O=/CN=$CN"

echo "### Issuing certificate"
openssl x509 -req -days 3650 -in client.csr -CA ../ca/ca.pem -CAkey ../ca/ca.key -set_serial "$CLIENT_SN" -out client.pem

rm client.csr

cp ../ca/ca.pem .

## Various ways of putting these 3 things into a single file, but python supports none of them
#echo "### Maybe you want a certificate chain"
#cat client.key client.pem ../ca/ca.pem > client.full.pem

#echo "### Or maybe pkcs12 is your thing"
#openssl pkcs12 -export -password pass:xxxx -out client.full.pfx -inkey client.key -in client.pem -certfile ../ca/ca.pem

#echo "### Fuck it, just zip it all up"
#cd ..
#zip -r resp.zip "$SUBDIR"

popd

