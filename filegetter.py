from ftplib import FTP
from urllib.parse import urlparse
import argparse
import hashlib
import os.path
import msgpack
import requests
from pathlib import Path
import sys

LFC_WGET_LIST = 'http://www.linuxfromscratch.org/lfs/view/development/wget-list'
#LFC_WGET_LIST = 'http://nuc/wget-list'

if sys.platform == 'win32':
    storagedir = os.path.join('d:', os.sep, 'lfsget')
else:
    storagedir = os.path.join('.', os.sep, 'lfsget')


def clean_storage_dir(directory):
    d = Path(directory)
    for f in d.glob('*'):
        print(f)


def checksum_dir(directory, sums=None):
    if sums:
        hashes = sums
    else:
        hashes = dict()

    if sums:
        files = [Path(p) for p in sums.keys()]
    else:
        dir = Path(directory)
        files = dir.glob('*')

    for f in files:
        digest = file_digest(f)
        if sums:
            hashes[f.as_posix()] = (sums[f.as_posix()] == digest)
        else:
            hashes[f.as_posix()] = digest

    return hashes


def file_digest(filename):
    h = hashlib.new('sha1')
    with filename.open('rb') as hashable:
        while True:
            buf = hashable.read(128)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def check_package_list(directory, checksums):
    return True


def refresh_package_list():
    filename = os.path.join(storagedir, 'wget-list')
    rd = requests.get(LFC_WGET_LIST)
    if rd.ok:
        package_list = []
        for line in rd.iter_lines():
            package_list.append(line.decode(encoding=rd.apparent_encoding))

        with open(filename, 'wb') as f:
            f.write(msgpack.packb(package_list, encoding='utf-8'))
    else:
        print(rd.status_code)
        sys.exit(2)


def download_packages():
    sums = read_sums_file()

    package_files = read_wget_list_file()
    if not package_files:
        refresh_package_list()
        package_files = read_wget_list_file()

    for pkg_uri in package_files:
        uri = urlparse(pkg_uri)
        filename = Path(storagedir,
                        Path(uri.path).name).as_posix()

        if os.path.exists(filename):
            filesum = sums.get(filename)
            if filesum and filesum == file_digest(Path(filename)):
                print("{} ok.".format(filename))
                continue
        try:
            if uri.scheme in {'http', 'https'}:
                pkg_rd = requests.get(pkg_uri)
                if pkg_rd.ok:
                    with open(filename, 'wb') as f:
                        for chunk in pkg_rd.iter_content(4096):
                            f.write(chunk)
                else:
                    print("Error {}".format(pkg_rd.reason))

            elif uri.scheme in {'ftp'}:
                ftp_conn = FTP(uri.netloc)
                print(ftp_conn.getwelcome())
                ftp_conn.login()
                ftp_conn.retrbinary('RETR {}'.format(uri.path), open(filename, 'wb').write)
        except Exception as e:
            print("Error while getting {}".format(pkg_uri))
            print(e)
            continue


def read_wget_list_file():
    """

    :rtype : list of filenames
    """
    try:
        filename = os.path.join(storagedir, 'wget-list')
        with open(filename, 'rb') as f:
            return msgpack.unpackb(f.read(), encoding='utf-8')
    except FileNotFoundError:
        return []


def read_sums_file():
    try:
        filename = os.path.join(storagedir, 'wget-sums')
        with open(filename, 'rb') as f:
            return msgpack.unpackb(f.read(), encoding='utf-8')
    except FileNotFoundError:
        return dict()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Runs LFS')
    parser.add_argument('-r', '--refresh', action='store_true',
                        default=False, help='Update wget list file')
    options = parser.parse_args()

    print("Storage directory is '{}'".format(storagedir))
    if not os.path.exists(storagedir):
        os.mkdir(storagedir)

    print("File list: {}".format(read_wget_list_file()))
    print("Sums: {}".format(read_sums_file()))

    sums = checksum_dir(storagedir)
    with open(os.path.join(storagedir, 'wget-sums'), 'wb') as f:
        f.write(msgpack.packb(sums, encoding='utf-8'))

    # clean_storage_dir(storagedir)
    download_packages()
