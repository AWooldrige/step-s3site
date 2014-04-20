#!/usr/bin/env python
import logging
from s3sitedeploy import extract_wercker_env_vars, upload_dir_to_s3

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    e = extract_wercker_env_vars()
    try:
        local_directory = join(e["root_dir"], e["source_dir"])
    except KeyError:
        local_directory = e["root_dir"]
    upload_dir_to_s3(local_directory, e["bucket_region"], e["bucket_name"],
                     e["access_key_id"], e["secret_access_key"])
