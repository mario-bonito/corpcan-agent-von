import asyncio
import argparse
import json
import os
import sys
import time
import aiohttp

DEFAULT_AGENT_URL = os.environ.get('AGENT_URL', 'http://localhost:5000/onbis')

parser = argparse.ArgumentParser(description='issue one or more credentials via von-x')
parser.add_argument('paths', nargs='+', help='the path to a credential JSON file')
parser.add_argument('-u', '--url', default=DEFAULT_AGENT_URL, help='the URL of the von-x service')
parser.add_argument('-p', '--parallel', default='1', help='number of parallel process')
parser.add_argument('-d', '--tempdir', default='temp', help='temporary directory to hold tracking files')
parser.add_argument('-s', '--split', action='store_true', help='split files in number of parallels')

args = parser.parse_args()

AGENT_URL = args.url
CRED_PATHS = args.paths
PARALLEL = args.parallel
TEMPDIR = args.tempdir
SPLIT = args.split

async def issue_cred(session, cred_path, start_point, end_point, split_cnt):
    basename = os.path.basename(cred_path)
    bad = open(TEMPDIR + '/' + basename + '.bad', 'a')
    done_file = TEMPDIR + '/' + basename + f'_{split_cnt}.done'
    done_mode = 'r+' if os.path.exists(done_file) else 'w+'
    done = open(done_file, done_mode)
    bad.write(f'################################################\n')
    bad.write(f'#         {time.asctime()}             #\n')
    bad.write(f'################################################\n\n')

    with open(cred_path) as fp:
        done_pos = done.readline()
        if done_pos: fp.seek(int(done_pos))
        else: fp.seek(start_point)

        current_point = fp.tell()
        cred_json = fp.readline() if current_point < end_point else None
        idx = 1
        while cred_json:
            start_time = time.time()
            try:
                cred = json.loads(cred_json)
                if not cred: raise ValueError('Credential could not be parsed.')
                schema = cred.get('schema')
                version = '' #cred.get('version', '')
                attrs = cred.get('attributes')
                if not schema: raise ValueError('No schema defined.')
                if not attrs: raise ValueError('Missing attributes.')
                
                async with session.post(
                    '{}/issue-credential'.format(AGENT_URL),
                    params={'schema': schema, 'version': version},
                    json=attrs
                ) as response:
                    if response.status != 200: raise ValueError(await response.text())
                    result_json = await response.json()
                    if not result_json.get('success'): raise ValueError(result_json)
            except Exception as e:
                bad.write(f'({split_cnt},{idx}): {cred_json}{e}\n\n')
                result_json = {}

            elapsed = time.time() - start_time
            print(f'{basename}({split_cnt},{idx}): Response from von-x ({elapsed:.2f}s).\n{result_json}\n')
            done.seek(0)
            done.write(str(current_point))
            if current_point < end_point:
                cred_json = fp.readline()
                current_point = fp.tell()
                idx += 1
            else:
                break
    bad.close()
    done.close()

async def issue_all(loop, paths, parallel):
    start_time = time.time()
    async with aiohttp.ClientSession(loop=loop, trust_env=False) as session:
        tasks = [
            issue_cred(session, path, start, end, cnt)
            for path in paths for cnt, (start, end) in enumerate(split_points(path, parallel))
        ]
        if tasks:
            await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    print(f'Total time: {elapsed:.2f}s')

def split_points(file_path, count):
    file_size = os.path.getsize(file_path)
    split_cnt = int(count)
    chunk_size = file_size // split_cnt
    
    with open(file_path) as fp:
        start = fp.tell()
        for s in range(split_cnt):
            fp.seek(chunk_size * (s + 1))
            fp.readline()
            end = fp.tell()
            if end >= file_size: end = file_size
            yield (start, end)
            start = end

def split_file(file_path, count):
    basename = os.path.basename(file_path)
    ext = os.path.splitext(basename)[1]
    with open(file_path) as big_file:
        for cnt, (start, end) in enumerate(split_points(file_path, count)):
            big_file.seek(start)
            line = big_file.readline()
            small_file_name = TEMPDIR + '/' + basename.replace(ext, f'_{cnt}{ext}')
            print(f'split[{cnt}]: {small_file_name}')
            with open(small_file_name, 'w') as small_file:
                while line:
                    small_file.write(line)
                    line = big_file.readline() if big_file.tell() < end else None
            
if __name__ == "__main__":
    if not TEMPDIR.startswith('/'):
        TEMPDIR = os.path.dirname(CRED_PATHS[0]) + '/' + TEMPDIR
    if not os.path.exists(TEMPDIR):
        os.makedirs(TEMPDIR)
    if SPLIT:
        for split in split_points(CRED_PATHS[0], PARALLEL): print(f'{split}')
        split_file(CRED_PATHS[0], PARALLEL)
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(issue_all(loop, CRED_PATHS, PARALLEL))
    