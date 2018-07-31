#!/usr/bin/env python3
import asyncio
import argparse
import json
import os
import sys
import time
import glob

import aiohttp

AGENT_URL = os.environ.get('AGENT_URL', 'http://localhost:5006/onbis')

async def issue_cred(http_client, cred_path, ident):
    with open(cred_path) as cred_file:
        creds = json.load(cred_file)

    for cred in creds:
        if not cred:
            raise ValueError('Credential could not be parsed')
        schema = cred.get('schema')
        if not schema:
            raise ValueError('No schema defined')
        version = cred.get('version', '')
        attrs = cred.get('attributes')
        if not attrs:
            raise ValueError('No schema attributes defined')

        print('Submitting credential {} {}'.format(ident, cred_path))

        start = time.time()
        try:
            response = await http_client.post(
                '{}/issue-credential'.format(AGENT_URL),
                params={'schema': schema, 'version': version},
                json=attrs
            )
            if response.status != 200:
                raise RuntimeError(
                    'Credential could not be processed: {}'.format(await response.text())
                )
            result_json = await response.json()
        except Exception as exc:
            raise Exception(
                'Could not issue credential. '
                'Are von-x and TheOrgBook running?') from exc

        elapsed = time.time() - start
        print('Response to {} from von-x ({:.2f}s):\n\n{}\n'.format(ident, elapsed, result_json))

async def submit_all(cred_paths, parallel=True):
    start = time.time()
    async with aiohttp.ClientSession() as http_client:
        all = []
        idx = 1
        for cred_path in cred_paths:
            req = issue_cred(http_client, cred_path, idx)
            if parallel:
                all.append(req)
            else:
                await req
            idx += 1
        if all:
            await asyncio.gather(*all)
    elapsed = time.time() - start
    print('Total time: {:.2f}s'.format(elapsed))

if __name__ == "__main__":
    cred_paths = glob.glob('../testdata/*.json')
    asyncio.get_event_loop().run_until_complete(submit_all(cred_paths, False))
