import logging
from os import environ, walk
from os.path import join, isfile, relpath
from json import load
from mimetypes import guess_type
import gzip
from re import compile
from jsonschema import validate

from multiprocessing.dummy import Pool as ThreadPool


from boto.s3.connection import S3Connection
from boto.s3.key import Key

log = logging.getLogger(__name__)

CONFIG_FILENAME = "s3sitedeploy.json"


def extract_wercker_env_vars():
    extracted = {}
    expected_env_vars = [
        ("source_dir", "WERCKER_SOURCE_DIR", True),
        ("deploy_dir", "WERCKER_S3SITEDEPLOY_DEPLOY_DIR", False),
        ("bucket_name", "WERCKER_S3SITEDEPLOY_BUCKET_NAME", True),
        ("access_key_id", "WERCKER_S3SITEDEPLOY_ACCESS_KEY_ID", True),
        ("secret_access_key", "WERCKER_S3SITEDEPLOY_SECRET_ACCESS_KEY", True),
        ("log_level", "WERCKER_S3SITEDEPLOY_LOG_LEVEL", False)]
    for map_to, key, required in expected_env_vars:
        try:
            extracted[map_to] = environ[key]
        except KeyError:
            if required:
                log.error("The environment variable '%s' is required", key)
                raise
    log.debug("Extracted Wercker environment variables successfully (not"
              "printing as they contain security credentials)")
    return extracted


def _validate_s3sitedeploy_json(json):
    with open("s3sitedeploy.schema.json") as schema_file:
        return validate(json, load(schema_file)) is None


def _list_all_files_in_dir(dir):
    return {relpath(join(dp, f), dir)
            for dp, _, fn in walk(dir)
            for f in fn
            if isfile(join(dp, f))} - {CONFIG_FILENAME}


def _get_s3site_config(dir):
    config_filepath = join(dir, CONFIG_FILENAME)
    try:
        with open(config_filepath) as config:
            try:
                decoded = load(config)
            except ValueError:
                log.exception("%s possibly not valid JSON", CONFIG_FILENAME)
                raise
            if _validate_s3sitedeploy_json(decoded):
                return decoded
    except IOError:
        log.exception("Could not find configuration file %s", config_filepath)
        return {}


def _append_charset(content_type):
    """
    Files stored in S3 really should be in UTF-8. For this reason, I've not
    made it configurable. UTF-8 encoding assumed for all text/* files
    """
    if content_type.startswith("text/"):
        return "{0}; charset=UTF-8".format(content_type)
    else:
        return content_type


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


def _get_object_directives(object_path, object_specific_config):
    for directive in object_specific_config:
        path = compile(directive["path"])
        if path.match(object_path):
            log.debug(
                "Object path %s matched expression %s, directives: %s",
                object_path, str(directive["path"]), str(directive))
            return directive
    return None


def _upload_file_to_s3(filepath, bucket, destination_key, site_config):
    key = Key(bucket=bucket, name=destination_key)
    content_type, content_encoding = guess_type(filepath)
    log.debug("Guessed content type '%s' and encoding '%s' for '%s'",
              content_type, content_encoding, filepath)
    # TODO: Add test around this
    directives = _get_object_directives(destination_key,
                                        site_config.get("object_specific", []))
    headers = {
        "x-amz-acl": "public-read",
        "Content-Type": _append_charset(content_type),
        "Cache-Control": "no-cache"}
    if content_encoding:
        headers["Content-Encoding"] = content_encoding
    else:
        # TODO: Add test around this
        should_gzip = content_type in site_config.get("gzip_mimetypes", [])
        try:
            # Allow for object specific overrides
            should_gzip = directives["gzip"]
        except (KeyError, TypeError):
            pass
        if should_gzip:
            headers["Content-Encoding"] = "gzip"
            filepath = _compress_the_file(filepath)
    try:
        headers.update(directives["headers"])
    except (KeyError, TypeError):
        pass
    bytes_written = key.set_contents_from_filename(filepath, headers=headers)
    log.info("Uploaded '%s' (transmitted %d bytes)", destination_key,
             bytes_written)
    return bytes_written


def parallel_upload_dir_to_s3(local_directory, bucket_name, access_key_id,
                              secret_access_key):
    config = _get_s3site_config(local_directory)
    files = _list_all_files_in_dir(local_directory)

    def _threadsafe_upload_file_to_s3(filepath):
        def _attempt_upload():
            conn = S3Connection(access_key_id, secret_access_key)
            s3_bucket = conn.get_bucket(bucket_name)
            _upload_file_to_s3(join(local_directory, filepath), s3_bucket,
                               filepath, config)
            return True
        for attempt in range(1, 5):
            log.debug("Uploading %s (attempt %s)", filepath, attempt)
            try:
                return _attempt_upload()
            except:
                log.exception("Could not upload file %s", filepath)
        return False
    pool = ThreadPool(10)
    results = pool.map(_threadsafe_upload_file_to_s3, files)
    pool.close()
    pool.join()
    return all(results)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    e = extract_wercker_env_vars()
    try:
        local_directory = join(e["source_dir"], e["deploy_dir"])
    except KeyError:
        local_directory = e["source_dir"]
    parallel_upload_dir_to_s3(
        local_directory, e["bucket_name"], e["access_key_id"],
        e["secret_access_key"])
