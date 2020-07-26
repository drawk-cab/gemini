#!/bin/bash

export DIR=~/.gemini
pushd "$DIR"

mkdir -p ca
cd ca

if [ ! -f ca.pem ]
then
  openssl genrsa -aes256 -passout pass:xxxx -out ca.pass.key 4096
  openssl rsa -passin pass:xxxx -in ca.pass.key -out ca.key
  rm ca.pass.key

  openssl req -new -x509 -days 3650 -key ca.key -out ca.pem
fi

