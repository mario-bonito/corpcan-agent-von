#!/usr/bin/env python3
#
# Copyright 2017-2018 Government of Canada
# Public Services and Procurement Canada - buyandsell.gc.ca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

#
# "requests" must be installed - pip3 install requests
#

import asyncio
import argparse
import json
import os
import sys

import aiohttp

DEFAULT_AGENT_URL = os.environ.get('AGENT_URL', 'http://localhost:5000/onbis')

parser = argparse.ArgumentParser(description='Proof one or more credentials via von-x')
parser.add_argument('credential_ids', nargs='+', help='the credential IDs to be proofed')
parser.add_argument('-n', '--name', default='registration', help='the name of the proof request')
parser.add_argument('-u', '--url', default=DEFAULT_AGENT_URL, help='the URL of the von-x service')

args = parser.parse_args()

AGENT_URL = args.url
PROOF_NAME = args.name
CREDENTIAL_IDS = args.credential_ids

async def request_proof(http_client, proof_name, credential_ids):
    print('Requesting proof: {} {}'.format(proof_name, credential_ids))

    try:
        response = await http_client.post(
            '{}/request-proof'.format(AGENT_URL),
            params={'name': proof_name},
            json=credential_ids,
        )
        if response.status != 200:
            raise RuntimeError(
                'Proof request could not be processed: {}'.format(await response.text())
            )
        result_json = await response.json()
    except Exception as exc:
        raise Exception(
            'Could not complete proof request. '
            'Are von-x and TheOrgBook running?') from exc

    print('Response from von-x:\n\n{}\n'.format(result_json))

async def request_all(CREDENTIAL_IDS):
    async with aiohttp.ClientSession(trust_env=True) as http_client:
        for credential_id in CREDENTIAL_IDS:
            await request_proof(http_client, PROOF_NAME, {'credential_ids': credential_id})

asyncio.get_event_loop().run_until_complete(request_all(CREDENTIAL_IDS))
