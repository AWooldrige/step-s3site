import logging
from os import environ, walk
from os.path import join, isfile, relpath
from json import load
from mimetypes import guess_type
import gzip
from re import compile

from boto.s3.connection import S3Connection
from boto.s3.key import Key

log = logging.getLogger(__name__)


def extract_wercker_env_vars():
    extracted = {}
    expected_env_vars = [
        ("root_dir", "WERCKER_SOURCE_DIR", True),
        ("source_dir", "WERCKER_S3SITEDEPLOY_SOURCE_DIR", False),
        ("bucket_name", "WERCKER_S3SITEDEPLOY_BUCKET_NAME", True),
        ("access_key_id", "WERCKER_S3SITEDEPLOY_ACCESS_KEY_ID", True),
        ("secret_access_key", "WERCKER_S3SITEDEPLOY_SECRET_ACCESS_KEY", True)]
    for map_to, key, required in expected_env_vars:
        try:
            extracted[key] = environ[key]
        except KeyError:
            if required:
                log.error("The environment variable '%s' is required", key)
                raise
    log.debug("Extracted Wercker environment variables: %s", str(extracted))
    return extracted


def _list_all_files_in_dir(dir):
    return {relpath(join(dp, f), dir)
            for dp, _, fn in walk(dir)
            for f in fn
            if isfile(join(dp, f))}


def _get_s3site_config(dir):
    try:
        with open(join(dir, "s3site.config")) as config:
            return load(config)
    except IOError:
        return {
            "headers": [{"path": r".*", "Cache-Control": "max-age=60"}],
            "gzip": ["text/html", "text/css", "text/plain",
                     "application/javascript"]}


def _cache_control_for_filepath(filepath, cache_config):
    for directive in reversed(cache_config):
        path = compile(directive["path"])
        if path.match(filepath):
            log.debug(
                "Filepath %s matched expression %s, applying Cache-Control %s",
                filepath, str(directive["path"]), directive["Cache-Control"])
            return directive["Cache-Control"]
    return "max-age=60, public"


def _compress_the_file(filepath):
    """
    TODO: Make this function usable with a 'with' statement, which deletes it
    after the yield
    """
    compressed_filepath = "{0}.s3sitedeploy.tmp.gz".format(filepath)
    log.debug("Compressing %s to %s", filepath, compressed_filepath)
    with open(filepath) as f_in:
        with gzip.open(compressed_filepath, "wb") as gz_out:
            gz_out.writelines(f_in)
    return compressed_filepath


def _upload_file_to_s3(filepath, bucket, destination_key, site_config):
    key = Key(bucket=bucket, name=destination_key)
    content_type, content_encoding = guess_type(filepath)
    log.debug("Guessed content type '%s' and encoding '%s' for '%s'",
              content_type, content_encoding, filepath)
    headers = {
        "x-amz-acl": "public-read",
        "Content-Type": content_type,
        "Cache-Control": _cache_control_for_filepath(
            destination_key, site_config["headers"])}
    if content_type in site_config["gzip"] and not content_encoding:
        log.debug("Content type '%s' is in the list of ones to gzip. File %s "
                  "will be gzipped then uploaded", content_type, filepath)
        headers["Content-Encoding"] = "gzip"
        compressed_filepath = _compress_the_file(filepath)
        return key.set_contents_from_filename(compressed_filepath,
                                              headers=headers)
    else:
        log.debug("Content type '%s' not int the list of ones to gzip (or %s "
                  "is already gzip encoded, about to upload as is",
                  content_type, filepath)
        if content_encoding:
            headers["Content-Encoding"] = content_encoding
        return key.set_contents_from_filename(filepath, headers=headers)


def upload_dir_to_s3(local_directory, bucket_name, access_key_id,
                     secret_access_key):
    conn = S3Connection(access_key_id, secret_access_key)
    s3_bucket = conn.get_bucket(bucket_name)
    config = _get_s3site_config(local_directory)
    files = _list_all_files_in_dir(local_directory)
    for filepath in files:
        _upload_file_to_s3(join(local_directory, filepath), s3_bucket,
                           filepath, config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    e = extract_wercker_env_vars()
    try:
        local_directory = e["source_dir"]
    except KeyError:
        local_directory = e["root_dir"]
    upload_dir_to_s3(local_directory, e["bucket_region"], e["bucket_name"],
                     e["access_key_id"], e["secret_access_key"])
