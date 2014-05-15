# -*- coding: utf-8 -*-
from unittest import TestCase, main
from mock import patch, Mock
from os.path import abspath
from os import environ
import gzip
from jsonschema import ValidationError

from s3sitedeploy import (
    _list_all_files_in_dir, _upload_file_to_s3, _compress_the_file,
    extract_wercker_env_vars, _append_charset, _get_object_directives,
    _get_s3site_config)


class ExtractWerckerEnvVarsTestCase(TestCase):

    def setUp(self):
        environ["WERCKER_SOURCE_DIR"] = "/test/path"
        environ["WERCKER_S3SITEDEPLOY_DEPLOY_DIR"] = "public_html/"
        environ["WERCKER_S3SITEDEPLOY_BUCKET_NAME"] = "site.com-bucket-13819"
        environ["WERCKER_S3SITEDEPLOY_ACCESS_KEY_ID"] = "fj2038fd*940$$F"
        environ["WERCKER_S3SITEDEPLOY_SECRET_ACCESS_KEY"] = ")39dj1'1jfkd"
        environ["WERCKER_S3SITEDEPLOY_LOG_LEVEL"] = "debug"
        self.expected = {
            "source_dir": "/test/path",
            "deploy_dir": "public_html/",
            "bucket_name": "site.com-bucket-13819",
            "access_key_id": "fj2038fd*940$$F",
            "secret_access_key": ")39dj1'1jfkd",
            "log_level": "debug"
        }

    def test_correct_mappings_all_fields(self):
        self.assertEqual(self.expected, extract_wercker_env_vars())

    def test_required_field_source_dir(self):
        del environ["WERCKER_SOURCE_DIR"]
        self.assertRaises(KeyError, extract_wercker_env_vars)

    def test_required_field_bucket_name(self):
        del environ["WERCKER_S3SITEDEPLOY_BUCKET_NAME"]
        self.assertRaises(KeyError, extract_wercker_env_vars)

    def test_required_field_access_key_id(self):
        del environ["WERCKER_S3SITEDEPLOY_ACCESS_KEY_ID"]
        self.assertRaises(KeyError, extract_wercker_env_vars)

    def test_required_field_secret_access_key(self):
        del environ["WERCKER_S3SITEDEPLOY_SECRET_ACCESS_KEY"]
        self.assertRaises(KeyError, extract_wercker_env_vars)

    def test_not_required_fields(self):
        del environ["WERCKER_S3SITEDEPLOY_DEPLOY_DIR"]
        del environ["WERCKER_S3SITEDEPLOY_LOG_LEVEL"]
        del self.expected["deploy_dir"]
        del self.expected["log_level"]
        self.assertEqual(self.expected, extract_wercker_env_vars())


class GetObjectDirectivesTestCase(TestCase):
    def setUp(self):
        self.conf = []

    def assertIt(self, expected_headers, object_path):
        return self.assertEqual(
            expected_headers,
            _get_object_directives(object_path, self.conf))

    def test_no_config(self):
        self.assertIt(None, "css/style.css")

    def test_catchall_wildcard_matches_everything(self):
        self.conf = [{
            "path": r".*",
            "headers": {"Cache-Control": "max-age=10"}}]
        expected = {"path": r".*", "headers": {"Cache-Control": "max-age=10"}}
        self.assertIt(expected, "test.txt")
        self.assertIt(expected, "images/10.jpg")
        self.assertIt(expected, "style/unicode/£€¡.css")

    def test_exact_match_no_regex_use(self):
        self.conf = [{"path": "images/£10.50.jpg",
                      "headers": {"x-amz-storage-class": "RRS"}}]
        expected = {"path": "images/£10.50.jpg",
                    "headers": {"x-amz-storage-class": "RRS"}}
        self.assertIt(expected, "images/£10.50.jpg")
        self.assertIt(None, "/images/£10.50.jpg")
        self.assertIt(None, "css/style.css")

    def test_ordering_first_match_wins(self):
        self.conf = [{"path": r"images/10.jpg",
                      "headers": {"Cache-Control": "max-age=15"}},
                     {"path": r"images/.*",
                      "headers": {"Cache-Control": "no-store"}},
                     {"path": r".*",
                      "headers": {"Cache-Control": "no-cache"}}]
        self.assertIt({"path": r".*",
                       "headers": {"Cache-Control": "no-cache"}},
                      "test.txt")
        self.assertIt({"path": r"images/.*",
                       "headers": {"Cache-Control": "no-store"}},
                      "images/test.jpg")
        self.assertIt({"path": r"images/10.jpg",
                       "headers": {"Cache-Control": "max-age=15"}},
                      "images/10.jpg")

    def test_example_full_use_case(self):
        self.conf = [
            {"path": r"^images/[0-3]+.jpg$",
             "gzip": False,
             "headers": {"Cache-Control": "no-store",
                         "x-amz-storage-class": "RRS"}},
            {"path": r"images/99.jpg",
             "headers": {"Cache-Control": "max-age=15"},
             "something_else": 1234},
            {"path": r".*css/.*",
             "headers": {"Cache-Control": "no-cache",
                         "X-Example": "932.38"}}]
        self.assertIt({"path": r"^images/[0-3]+.jpg$", "gzip": False,
                       "headers": {"Cache-Control": "no-store",
                                   "x-amz-storage-class": "RRS"}},
                      "images/123.jpg")
        self.assertIt({"path": r"^images/[0-3]+.jpg$", "gzip": False,
                       "headers": {"Cache-Control": "no-store",
                                   "x-amz-storage-class": "RRS"}},
                      "images/0.jpg")
        self.assertIt({"path": r"images/99.jpg",
                       "headers": {"Cache-Control": "max-age=15"},
                       "something_else": 1234},
                      "images/99.jpg")
        self.assertIt(None, "images/876.jpg")
        self.assertIt(None, "text/test.txt")
        self.assertIt({"path": r".*css/.*",
                       "headers": {"Cache-Control": "no-cache",
                                   "X-Example": "932.38"}},
                      "/first/style/css/app.css")


class AppendCharsetTestCase(TestCase):

    def test_multiple_text_files(self):
        examples = {"text/csv", "text/encaprtp", "text/html", "text/jcr-cnd",
                    "text/mizar", "text/prs.lines.tag", "text/rtf",
                    "text/rtp-enc-aescm128", "text/vnd.debian.copyright",
                    "text/vnd.IPTC.NITF"}
        expected = {"{0}; charset=UTF-8".format(ct) for ct in examples}
        actual = {_append_charset(ct) for ct in examples}
        self.assertEqual(expected, actual)

    def test_multiple_non_text_files(self):
        examples = {"application/atom+xml", "application/javascript",
                    "application/pdf", "application/font-woff", "audio/mpeg",
                    "audio/vorbis", "image/jpeg", "image/svg+xml",
                    "video/quicktime", "video/avi",
                    "application/vnd.oasis.opendocument.text"}
        actual = {_append_charset(ct) for ct in examples}
        self.assertEqual(examples, actual)


class ListAllFilesInDirTestCase(TestCase):

    def test_non_existant_directory(self):
        self.assertEquals(set([]), _list_all_files_in_dir("non-existent"))

    def test_empty_directory(self):
        self.assertEquals(set([]), _list_all_files_in_dir(
            "tests/fixtures/empty-project/"))

    def test_s3siteconfig_not_returned(self):
        files = _list_all_files_in_dir(
            "tests/fixtures/example-multi-depth-project/")
        self.assertTrue("s3sitedeploy.json" not in files)

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
            "object_specific": [
                {"path": r".*",
                 "headers": {"Cache-Control": "max-age=60"}}],
            "gzip_mimetypes": ["text/html", "text/css", "text/plain",
                               "application/javascript"]}

    @patch("s3sitedeploy.Key")
    @patch("s3sitedeploy._compress_the_file")
    def test_content_type_guessed_and_set_correctly_for_html_file(
            self, mock_compress_the_file, mock_key):
        mock_compress_the_file.return_value = "example-file.gz"
        expected_headers = {
            "x-amz-acl": "public-read",
            "Content-Type": "text/html; charset=UTF-8",
            "Content-Encoding": "gzip",
            "Cache-Control": "max-age=60"}
        _upload_file_to_s3(
            "tests/fixtures/webpage-without-compression.html",
            self.mock_bucket, "webpage-without-compression.html",
            self.example_config)
        mock_key.assert_called_once_with(self.mock_bucket)
        mock_key.key.assertEquals("webpage-without-compression.html")
        mock_key.return_value.set_contents_from_filename.\
            assert_called_once_with("example-file.gz",
                                    headers=expected_headers)

    @patch("s3sitedeploy.Key")
    def test_gzipping_not_performed_if_file_is_already_gzipped(self, mock_key):
        expected_headers = {
            "x-amz-acl": "public-read",
            "Content-Type": "text/html; charset=UTF-8",
            "Content-Encoding": "gzip",
            "Cache-Control": "max-age=60"}
        _upload_file_to_s3(
            "tests/fixtures/webpage-with-compression.html.gz",
            self.mock_bucket, "webpage-with-compression.html.gz",
            self.example_config)
        mock_key.assert_called_once_with(self.mock_bucket)
        mock_key.key.assertEquals("webpage-without-compression.html.gz")
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
        mock_key.assert_called_once_with(self.mock_bucket)
        mock_key.key.assertEquals("example-image.jpg")
        mock_key.return_value.set_contents_from_filename.\
            assert_called_once_with("tests/fixtures/example-image.jpg",
                                    headers=expected_headers)

    @patch("s3sitedeploy.Key")
    def test_gzipping_not_performed_if_object_override(self, mock_key):
        self.example_config = {
            "object_specific": [
                {"path": r".*",
                 "gzip": False}],
            "gzip_mimetypes": ["text/html", "text/css", "text/plain",
                               "application/javascript"]}
        expected_headers = {
            "x-amz-acl": "public-read",
            "Content-Type": "text/html; charset=UTF-8",
            "Cache-Control": "no-cache"}
        _upload_file_to_s3(
            "tests/fixtures/webpage-without-compression.html",
            self.mock_bucket, "webpage-without-compression.html",
            self.example_config)
        mock_key.assert_called_once_with(self.mock_bucket)
        mock_key.key.assertEquals("webpage-without-compression.html")
        mock_key.return_value.set_contents_from_filename.\
            assert_called_once_with(
                "tests/fixtures/webpage-without-compression.html",
                headers=expected_headers)

    @patch("s3sitedeploy.Key")
    def test_header_overrides_honoured(self, mock_key):
        self.example_config = {
            "object_specific": [
                {"path": r".*",
                 "headers": {"Cache-Control": "private, max-age=10",
                             "x-amz-acl": "public-dance"}}],
            "gzip_mimetypes": ["text/html", "text/css", "text/plain",
                               "application/javascript"]}
        expected_headers = {
            "x-amz-acl": "public-dance",
            "Content-Type": "image/jpeg",
            "Cache-Control": "private, max-age=10"}
        _upload_file_to_s3("tests/fixtures/example-image.jpg",
                           self.mock_bucket, "example-image.jpg",
                           self.example_config)
        mock_key.assert_called_once_with(self.mock_bucket)
        mock_key.key.assertEquals("example-image.jpg")
        mock_key.return_value.set_contents_from_filename.\
            assert_called_once_with("tests/fixtures/example-image.jpg",
                                    headers=expected_headers)


class GetS3siteConfigTestCase(TestCase):

    def test_read_correctly(self):
        expected = {
            "object_specific": [
                {"path": r".*",
                 "headers": {"Cache-Control": "max-age=3600"},
                 "gzip": False},
                {"path": r"^recipe/.*",
                 "headers": {"Cache-Control": "max-age=3600"}}],
            "gzip_mimetypes": ["text/html", "text/css", "text/plain",
                               "text/yaml", "application/javascript"]}
        config = _get_s3site_config(
            "tests/fixtures/example-multi-depth-project/")
        self.assertEquals(expected, config)

    def test_config_is_validated_against_schema(self):
        self.assertRaises(ValidationError, _get_s3site_config,
                          "tests/fixtures/invalid-s3sitedeploy-json/")

    def test_default_returned_if_file_doesnt_exist(self):
        config = _get_s3site_config("test/fixtures/DoesNtExiSt")
        self.assertEquals({}, config)


if __name__ == '__main__':
    main()
