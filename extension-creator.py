import cgi
import json
import os
import sys
import time
from argparse import ArgumentParser
from urllib.parse import quote, unquote, urlencode
from urllib.request import urlopen, Request,urlretrieve
import replicate


CURRENT_DIR_PATH = os.path.dirname(os.path.realpath(__file__))
URL_API = "https://www.lalal.ai/api/"

key="###"
REPLICATE_API_TOKEN="####"
def update_percent(pct):
    pct = str(pct)
    sys.stdout.write("\b" * len(pct))
    sys.stdout.write(" " * len(pct))
    sys.stdout.write("\b" * len(pct))
    sys.stdout.write(pct)
    sys.stdout.flush()


def make_content_disposition(filename, disposition='attachment'):
    try:
        filename.encode('ascii')
        file_expr = f'filename="{filename}"'
    except UnicodeEncodeError:
        quoted = quote(filename)
        file_expr = f"filename*=utf-8''{quoted}"
    return f'{disposition}; {file_expr}'


def upload_file(file_path, license):
    url_for_upload = URL_API + "upload/" 
    _, filename = os.path.split(file_path)
    headers = {
        "Content-Disposition": make_content_disposition(filename),
        "Authorization": f"license {key}",
    }
    with open(file_path, 'rb') as f:
        request = Request(url_for_upload, f, headers)
        with urlopen(request) as response:
            upload_result = json.load(response)
            if upload_result["status"] == "success":
                return upload_result["id"]
            else:
                raise RuntimeError(upload_result["error"])


def split_file(file_id, license, stem, filter_type, splitter):
    url_for_split = URL_API + "split/"
    headers = {
        "Authorization": f"license {key}",
    }
    query_args = {'id': file_id, 'stem': stem, 'filter': filter_type, 'splitter': splitter}
    encoded_args = urlencode(query_args).encode('utf-8')
    request = Request(url_for_split, encoded_args, headers=headers)
    with urlopen(request) as response:
        split_result = json.load(response)
        if split_result["status"] == "error":
            raise RuntimeError(split_result["error"])


def check_file(file_id):
    url_for_check = URL_API + "check/?"
    query_args = {'id': file_id}
    encoded_args = urlencode(query_args)

    is_queueup = False

    while True:
        with urlopen(url_for_check + encoded_args) as response:
            check_result = json.load(response)

        if check_result["status"] == "error":
            raise RuntimeError(check_result["error"])

        task_state = check_result["task"]["state"]

        if task_state == "error":
            raise RuntimeError(check_result["task"]["error"])

        if task_state == "progress":
            progress = int(check_result["task"]["progress"])
            if progress == 0 and not is_queueup:
                print("Queue up...")
                is_queueup = True
            elif progress > 0:
                update_percent(f"Progress: {progress}%")

        if task_state == "success":
            update_percent("Progress: 100%\n")
            stem_track_url = check_result["split"]["stem_track"]
            back_track_url = check_result["split"]["back_track"]
            return stem_track_url, back_track_url

        time.sleep(15)


def get_filename_from_content_disposition(header):
    _, params = cgi.parse_header(header)
    filename = params.get('filename')
    print(filename)
    if filename:
        return filename
    filename = params.get('filename*')
    if filename:
        encoding, quoted = filename.split("''")
        unquoted = unquote(quoted, encoding)
        return unquoted
    raise ValueError('Invalid header Content-Disposition')


def download_file(url_for_download, output_path):
    with urlopen(url_for_download) as response:
        filename = get_filename_from_content_disposition(response.headers["Content-Disposition"])
        file_path = os.path.join(output_path, filename)
        with open(file_path, 'wb') as f:
            while (chunk := response.read(8196)):
                f.write(chunk)
    return file_path


def batch_process_for_file(license, input_path, output_path, stem, filter_type, splitter):
    print('goose')
    try:
        print(f'Uploading the file "{input_path}"...')
        file_id = upload_file(file_path=input_path, license=license)
        print(f'The file "{input_path}" has been successfully uploaded (file id: {file_id})')

        print(f'Processing the file "{input_path}"...')
        split_file(file_id, license, stem, filter_type, splitter)
        stem_track_url, back_track_url = check_file(file_id)

        print(f'Downloading the stem track file "{stem_track_url}"...')
        downloaded_file = download_file(stem_track_url, output_path)
        print(f'The stem track file has been downloaded to "{downloaded_file}"')

        print(f'Downloading the back track file "{back_track_url}"...')
        downloaded_file = download_file(back_track_url, output_path)
        print(f'The back track file has been downloaded to "{downloaded_file}"')

        print(f'The file "{input_path}" has been successfully split')
    except Exception as err:
        print(f'Cannot process the file "{input_path}": {err}')


def batch_process(license, input_path, output_path, stem, filter_type, splitter):
    if os.path.isfile(input_path):
        batch_process_for_file(license, input_path, output_path, stem, filter_type, splitter)
    else:
        for path in os.listdir(input_path):
            path = os.path.join(input_path, path)
            if os.path.isfile(path):
                batch_process_for_file(license, path, output_path, stem, filter_type, splitter)


def main():
    output = replicate.run(
    "facebookresearch/musicgen:7a76a8258b23fae65c5a22debb8841d1d7e816b75c2f24218cd2bd8573787906",
    input={"model_version": "melody","prompt":"Edo25 major g melodies that sound triumphant and cinematic. Leading up to a crescendo that resolves in a 9th harmonic","input_audio":"https://github.com/jamesthesnake/stem-remixer/blob/main/stripes.mp3"}
)
    print(output)
    urlretrieve(output,"hereyr.wav")
    parser = ArgumentParser(description='Lalalai splitter')
    parser.add_argument('--prompt',type=str)
    parser.add_argument('--input', type=str, required=True, help='Input directory or a file')
    parser.add_argument('--output', type=str, default=CURRENT_DIR_PATH, help='Output directory')
    parser.add_argument('--stem', type=str, default='bass', choices=['vocals', 'drum', 'bass', 'piano', 'electric_guitar', 'acoustic_guitar', 'synthesizer', 'voice', 'strings', 'wind'], help='Stem option. Stems "voice", "strings", "wind" are not supported by Cassiopeia')
    parser.add_argument('--filter', type=int, default=1, choices=[0, 1, 2], help='0 (mild), 1 (normal), 2 (aggressive)')
    parser.add_argument('--splitter', type=str, default='phoenix', choices=['phoenix', 'cassiopeia'], help='The type of neural network used to split audio')

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    batch_process(key, args.input, args.output, args.stem, args.filter, args.splitter)


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        print(err)

