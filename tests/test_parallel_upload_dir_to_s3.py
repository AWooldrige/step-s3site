# -*- coding: utf-8 -*-
from os.path import join
from tempfile import mkdtemp
from shutil import rmtree
from unittest import TestCase, main
import boto
from moto import mock_s3

from s3sitedeploy import parallel_upload_dir_to_s3


class ParallelUploadDirToS3TestCase(TestCase):

    def setUp(self):
        self.bucket_name = "www-test-com-bucket"
        self.temp_dir = mkdtemp()

    def tearDown(self):
        rmtree(self.temp_dir)

    @mock_s3
    def test_normal_use_case(self):
        conn = boto.connect_s3()
        conn.create_bucket(self.bucket_name)
        parallel_upload_dir_to_s3(
            "tests/fixtures/example-multi-depth-project",
            self.bucket_name, "dkf20fj", "3jf9d0sf")
        bucket = conn.get_bucket(self.bucket_name)
        self.assertEquals(
            "This is a great story\n",
            bucket.get_key("text/2014/attempt-1.txt").read())

    @mock_s3
    def test_can_handle_many_files(self):
        for i in range(1, 500):
            example_file = join(self.temp_dir, str(i) + ".txt")
            with open(example_file, "w") as f:
                f.write("test of this \n thing")
        conn = boto.connect_s3()
        conn.create_bucket(self.bucket_name)
        status = parallel_upload_dir_to_s3(self.temp_dir, self.bucket_name,
                                           "dkf20fj", "3jf9d0sf")
        self.assertTrue(status)
        bucket = conn.get_bucket(self.bucket_name)
        self.assertEquals("test of this \n thing",
                          bucket.get_key("1.txt").read())


if __name__ == '__main__':
    main()
