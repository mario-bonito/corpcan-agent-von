import os
import sys
import time
import json
import argparse
import asyncio
import aiohttp

DEFAULT_AGENT_URL = os.environ.get('AGENT_URL', 'http://localhost:5000/onbis')

parser = argparse.ArgumentParser(description='issue one or more credentials via von-x')
parser.add_argument('paths', nargs='+', help='the path to a credential JSON file')
parser.add_argument('-u', '--url', default=DEFAULT_AGENT_URL, help='the URL of the von-x service')
parser.add_argument('-p', '--parallel', default='1', help='number of parallel process')
parser.add_argument('-d', '--tempdir', default='temp', help='temporary directory to hold tracking files')
parser.add_argument('-s', '--split', action='store_true', help='split files in number of parallels')
parser.add_argument('-b', '--batch_size', default='1', help='number of credentials in one post')

args = parser.parse_args()

AGENT_URL = args.url
CRED_PATHS = args.paths
PARALLEL = args.parallel
TEMPDIR = args.tempdir
SPLIT = args.split
BACH_SIZE = args.batch_size

async def issue_cred(session, cred_path, start_point, end_point, split_cnt, batch_size):
    basename = os.path.basename(cred_path)
    bad = open(TEMPDIR + '/' + basename + '.bad', 'a')
    done_file = TEMPDIR + '/' + basename + f'_{split_cnt}.done'
    done_mode = 'r+' if os.path.exists(done_file) else 'w+'
    done = open(done_file, done_mode)
    #bad.write(f'################################################\n')
    #bad.write(f'#         {time.asctime()}             #\n')
    #bad.write(f'################################################\n\n')

    with open(cred_path) as fp:
        done_pos = done.readline()
        if done_pos: fp.seek(int(done_pos))
        else: fp.seek(start_point)

        current_point = fp.tell()
        batch_cnt = 0
        while current_point < end_point:
            batch = []
            cred_cnt = 0
            while cred_cnt < batch_size and current_point < end_point:
                cred_json = fp.readline()
                current_point = fp.tell()
                if (cred_json):
                    batch.append(json.loads(cred_json))
                    cred_cnt += 1
                else:
                    break
            batch_cnt += 1
            cred_json = json.loads(json.dumps(batch))

            start_time = time.time()
            try:
                async with session.post(
                    '{}/issue-credential'.format(AGENT_URL.strip()),
                    params={},
                    json=cred_json
                ) as response:
                    if response.status != 200:
                        raise ValueError(await response.text())
                    result = await response.json()
                    if isinstance(result, list):
                        for idx, result_json in enumerate(result):
                            if not result_json.get('success'):
                                bad.write(json.dumps(batch[idx]))
                        result_json = result
                    else:
                        if not result_json.get('success'):
                            bad.write(json.dumps(batch[0]))
            except Exception as e:
                for bad_json in batch:
                    bad.write(json.dumps(bad_json) + '\n')
                result_json = {"error": e}
            done.seek(0)
            done.write(str(current_point))
            elapsed = time.time() - start_time
            print(f'{basename}({split_cnt},{batch_cnt}): Response from von-x ({elapsed:.2f}s).\n{result_json}\n')

    bad.close()
    done.close()

async def issue_all(loop, paths, parallel, batch_size):
    start_time = time.time()
    basicAuth = aiohttp.BasicAuth(login='onbisuser', password='onbispass')
    async with aiohttp.ClientSession(loop=loop, trust_env=True, auth=basicAuth) as session:
        tasks = [
            issue_cred(session, path, start, end, cnt, int(batch_size))
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
        loop.run_until_complete(issue_all(loop, CRED_PATHS, PARALLEL, BACH_SIZE))
    