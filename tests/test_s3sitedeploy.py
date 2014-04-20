from unittest import TestCase, main
from mock import patch, Mock
from os.path import abspath
from os import environ
import gzip

from s3sitedeploy import (_cache_control_for_filepath,  _list_all_files_in_dir,
                          _upload_file_to_s3, _compress_the_file,
                          extract_wercker_env_vars)


class ExtractWerckerEnvVarsTestCase(TestCase):

    def setUp(self):
        environ["WERCKER_SOURCE_DIR"] = "/test/path"
        environ["WERCKER_S3SITEDEPLOY_DEPLOY_DIR"] = "public_html/"
        environ["WERCKER_S3SITEDEPLOY_BUCKET_NAME"] = "site.com-bucket-13819"
        environ["WERCKER_S3SITEDEPLOY_ACCESS_KEY_ID"] = "fj2038fd*940$$F"
        environ["WERCKER_S3SITEDEPLOY_SECRET_ACCESS_KEY"] = ")39dj1'1jfkd"

    def test_correct_mappings(self):
        expected = {
            "source_dir": "/test/path",
            "deploy_dir": "public_html/",
            "bucket_name": "site.com-bucket-13819",
            "access_key_id": "fj2038fd*940$$F",
            "secret_access_key": ")39dj1'1jfkd"
        }
        self.assertEqual(expected, extract_wercker_env_vars())

    def test_required_fields(self):
        required = {"WERCKER_SOURCE_DIR", "WERCKER_S3SITEDEPLOY_BUCKET_NAME",
                    "WERCKER_S3SITEDEPLOY_ACCESS_KEY_ID",
                    "WERCKER_S3SITEDEPLOY_SECRET_ACCESS_KEY"}
        for key in required:
            del environ[key]
            self.assertRaises(KeyError, extract_wercker_env_vars)

    def test_not_required_fields(self):
        del environ["WERCKER_S3SITEDEPLOY_DEPLOY_DIR"]
        expected = {
            "source_dir": "/test/path",
            "bucket_name": "site.com-bucket-13819",
            "access_key_id": "fj2038fd*940$$F",
            "secret_access_key": ")39dj1'1jfkd"
        }
        self.assertEqual(expected, extract_wercker_env_vars())


class CacheControlForFilepathTestCase(TestCase):
    def setUp(self):
        self.default_cache_control = "max-age=60, public"
        self.conf = []

    def assertIt(self, expected_cache_control, filepath):
        return self.assertEqual(
            expected_cache_control,
            _cache_control_for_filepath(filepath, self.conf))

    def test_no_config(self):
        self.conf = []
        self.assertIt(self.default_cache_control, "css/style.css")

    def test_catchall_wildcard(self):
        self.conf = [{"path": r".*", "Cache-Control": "private, max-age=10"}]
        self.assertIt("private, max-age=10", "test.txt")
        self.assertIt("private, max-age=10", "images/10.jpg")

    def test_exact_match(self):
        self.conf = [{"path": r"images/10.jpg", "Cache-Control": "no-cache"}]
        self.assertIt("no-cache", "images/10.jpg")
        self.assertIt(self.default_cache_control, "/images/10.jpg")
        self.assertIt(self.default_cache_control, "css/style.css")

    def test_ordering_last_match_wins(self):
        self.conf = [
            {"path": r".*", "Cache-Control": "no-cache"},
            {"path": r"images/.*", "Cache-Control": "no-store"},
            {"path": r"images/10.jpg", "Cache-Control": "max-age=15"},
        ]
        self.assertIt("no-cache", "test.txt")
        self.assertIt("no-store", "images/test.jpg")
        self.assertIt("max-age=15", "images/10.jpg")

    def test_many_paths(self):
        self.conf = [
            {"path": r"^images/[0-3]+.jpg$", "Cache-Control": "no-store"},
            {"path": r"images/99.jpg", "Cache-Control": "max-age=15"},
            {"path": r".*css/.*", "Cache-Control": "no-cache"},
        ]
        self.assertIt("no-store", "images/123.jpg")
        self.assertIt("no-store", "images/0.jpg")
        self.assertIt("max-age=15", "images/99.jpg")
        self.assertIt("max-age=15", "images/99.jpg")
        self.assertIt(self.default_cache_control, "images/876.jpg")
        self.assertIt(self.default_cache_control, "text/test.txt")
        self.assertIt("no-cache", "/first/style/css/app.css")

    def test_error_if_directive_with_no_path(self):
        """ This is a build time tool, it should hardfail """
        self.conf = [{"Cache-Control": "private, max-age=10"}]
        self.assertRaises(KeyError, _cache_control_for_filepath,
                          "test.txt", self.conf)

    def test_error_if_directive_with_no_cache_control_gets_default(self):
        """ This is a build time tool, it should hardfail """
        self.conf = [{"path": r".*"}]
        self.assertRaises(KeyError, _cache_control_for_filepath,
                          "test.txt", self.conf)


class ListAllFilesInDirTestCase(TestCase):

    def test_non_existant_directory(self):
        self.assertEquals(set([]), _list_all_files_in_dir("non-existent"))

    def test_empty_directory(self):
        self.assertEquals(set([]), _list_all_files_in_dir(
            "tests/fixtures/empty-project/"))

    def test_multi_depth_project(self):
        expected = {"index.html",
                    "text/poem.txt",
                    "text/2014/attempt-1.txt",
                    "text/2014/attempt-43.txt"}
        files = _list_all_files_in_dir(
            "tests/fixtures/example-multi-depth-project/")
        self.assertEquals(expected, files)

    def test_check_leading_trailing_slashes(self):
        trailing = _list_all_files_in_dir(
            "tests/fixtures/example-multi-depth-project/")
        no_trailing = _list_all_files_in_dir(
            "tests/fixtures/example-multi-depth-project")
        absolute = _list_all_files_in_dir(
            abspath("tests/fixtures/example-multi-depth-project/"))
        self.assertEquals(trailing, no_trailing)
        self.assertEquals(trailing, absolute)


class CompressTheFileTestCase(TestCase):

    def test_file_is_gzipped_correctly(self):
        expected_filepath = "tests/fixtures/compression-tests/webpage.html.gz"
        just_compressed = _compress_the_file(
            "tests/fixtures/compression-tests/webpage.html")
        with gzip.open(just_compressed) as f_just_compressed:
            with gzip.open(expected_filepath) as f_expected:
                self.assertEquals(f_expected.read(), f_just_compressed.read())

    def test_original_file_left_intact(self):
        filepath = "tests/fixtures/compression-tests/webpage.html"
        with open(filepath) as f_original:
            original_contents = f_original.read()
        _compress_the_file(filepath)
        with open(filepath) as f_original:
            self.assertEqual(original_contents, f_original.read())


class UploadFileToS3TestCase(TestCase):

    def setUp(self):
        self.mock_bucket = Mock()
        self.example_config = {
            "headers": [{"path": r".*", "Cache-Control": "max-age=60"}],
            "gzip": ["text/html", "text/css", "text/plain",
                     "application/javascript"]}

    @patch("s3sitedeploy.Key")
    @patch("s3sitedeploy._compress_the_file")
    def test_content_type_guessed_and_set_correctly_for_html_file(
            self, mock_compress_the_file, mock_key):
        mock_compress_the_file.return_value = "example-file.gz"
        expected_headers = {
            "x-amz-acl": "public-read",
            "Content-Type": "text/html",
            "Content-Encoding": "gzip",
            "Cache-Control": "max-age=60"}
        _upload_file_to_s3(
            "tests/fixtures/webpage-without-compression.html",
            self.mock_bucket, "webpage-without-compression.html",
            self.example_config)
        mock_key.assert_called_once_with(
            bucket=self.mock_bucket, name="webpage-without-compression.html")
        mock_key.return_value.set_contents_from_filename.\
            assert_called_once_with("example-file.gz",
                                    headers=expected_headers)

    @patch("s3sitedeploy.Key")
    def test_gzipping_not_performed_if_file_is_already_gzipped(self, mock_key):
        expected_headers = {
            "x-amz-acl": "public-read",
            "Content-Type": "text/html",
            "Content-Encoding": "gzip",
            "Cache-Control": "max-age=60"}
        _upload_file_to_s3(
            "tests/fixtures/webpage-with-compression.html.gz",
            self.mock_bucket, "webpage-with-compression.html.gz",
            self.example_config)
        mock_key.assert_called_once_with(
            bucket=self.mock_bucket, name="webpage-with-compression.html.gz")
        mock_key.return_value.set_contents_from_filename.\
            assert_called_once_with(
                "tests/fixtures/webpage-with-compression.html.gz",
                headers=expected_headers)

    @patch("s3sitedeploy.Key")
    def test_gzipping_not_performed_if_mimetype_is_not_in_list(self, mock_key):
        expected_headers = {
            "x-amz-acl": "public-read",
            "Content-Type": "image/jpeg",
            "Cache-Control": "max-age=60"}
        _upload_file_to_s3("tests/fixtures/example-image.jpg",
                           self.mock_bucket, "example-image.jpg",
                           self.example_config)
        mock_key.assert_called_once_with(
            bucket=self.mock_bucket, name="example-image.jpg")
        mock_key.return_value.set_contents_from_filename.\
            assert_called_once_with("tests/fixtures/example-image.jpg",
                                    headers=expected_headers)


if __name__ == '__main__':
    main()
