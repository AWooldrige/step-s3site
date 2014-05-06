# -*- coding: utf-8 -*-
from unittest import TestCase, main
from jsonschema import ValidationError

from s3sitedeploy import _validate_s3sitedeploy_json


class BaseJsonSchemaTestCase(TestCase):

    def assertValid(self, json):
        self.assertTrue(_validate_s3sitedeploy_json(json))

    def assertInvalid(self, json):
        self.assertRaises(
            ValidationError, _validate_s3sitedeploy_json, json)


class ValidateOverallSchemaTestCase(BaseJsonSchemaTestCase):

    def test_no_additional_properties(self):
        self.assertInvalid({"something_else": "here"})


class ValidateGzipMimetypesPropertyTestCase(BaseJsonSchemaTestCase):

    def test_not_required(self):
        self.assertValid({})

    def test_can_be_empty_list(self):
        self.assertValid({"gzip_mimetypes": []})

    def test_cannot_be_other_types(self):
        self.assertInvalid({"gzip_mimetypes": "text/html"})
        self.assertInvalid({"gzip_mimetypes": {"type": "text/html"}})
        self.assertInvalid({"gzip_mimetypes": 123})
        self.assertInvalid({"gzip_mimetypes": True})

    def test_valid_use_cases(self):
        self.assertValid({"gzip_mimetypes": ["text/html"]})
        self.assertValid({"gzip_mimetypes": ["text/html", "application/json"]})

    def test_must_be_list_of_strings(self):
        self.assertInvalid({"gzip_mimetypes": [381, 123]})
        self.assertInvalid({"gzip_mimetypes": [True, False]})
        self.assertInvalid({"gzip_mimetypes": [{"a": "b"}, {"c": "d"}]})
        self.assertInvalid({"gzip_mimetypes": [[1], [2]]})

    def test_must_be_unique(self):
        self.assertInvalid({"gzip_mimetypes": ["text/html", "text/html"]})


class ValidateObjectSpecificHeadersPropertyTestCase(BaseJsonSchemaTestCase):

    def test_not_required(self):
        self.assertValid({})

    def test_can_be_empty_list(self):
        self.assertValid({"object_specific": []})

    def test_cannot_be_other_types(self):
        self.assertInvalid({"object_specific": "dancing"})
        self.assertInvalid({"object_specific": {"_path": r"^.*$"}})
        self.assertInvalid({"object_specific": 123})
        self.assertInvalid({"object_specific": True})


class ValidateObjectSpecificDirective(BaseJsonSchemaTestCase):

    def assertDirectiveValid(self, directive):
        self.assertValid({"object_specific": [directive]})

    def assertDirectiveInvalid(self, directive):
        self.assertInvalid({"object_specific": [directive]})

    def test_path_must_be_present(self):
        self.assertDirectiveInvalid({})

    def test_path_must_not_be_empty(self):
        self.assertDirectiveInvalid({"path": ""})

    def test_path_valid_use_cases(self):
        self.assertDirectiveValid({"path": "robots.txt"})
        self.assertDirectiveValid({"path": r"image/[0-9].jpg$"})
        self.assertDirectiveValid({"path": r"^recipe/.*"})

    def test_path_must_be_string(self):
        self.assertDirectiveInvalid({"path": ["robots.txt", "index.html"]})
        self.assertDirectiveInvalid({"path": 123})
        self.assertDirectiveInvalid({"path": True})
        self.assertDirectiveInvalid({"path": {"a": "b"}})

    def test_headers_can_be_empty(self):
        self.assertDirectiveValid({
            "path": r"^recipe/.*",
            "headers": {}})

    def test_headers_valid_use_cases(self):
        self.assertDirectiveValid({
            "path": r"^recipe/.*",
            "headers": {"Cache-Control": "max-age=10"}})
        self.assertDirectiveValid({
            "path": r"^recipe/.*",
            "headers": {"Cache-Control": "max-age=10",
                        "x-amx-example-header": "1234"}})

    def test_headers_must_be_string_to_string_map(self):
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "headers": {"Cache-Control": 10}})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "headers": {"Cache-Control": True}})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "headers": {"Cache-Control": [1]}})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "headers": {"Cache-Control": {"max-age": "10"}}})

    def test_gzip_valid_use_cases(self):
        self.assertDirectiveValid({
            "path": "robots.txt",
            "gzip": False})
        self.assertDirectiveValid({
            "path": r"images/listing.html",
            "gzip": True})

    def test_gzip_must_be_boolean(self):
        self.assertDirectiveInvalid({
            "path": r"images/listing.html",
            "gzip": "no"})
        self.assertDirectiveInvalid({
            "path": r"images/listing.html",
            "gzip": 0})
        self.assertDirectiveInvalid({
            "path": r"images/listing.html",
            "gzip": [True]})
        self.assertDirectiveInvalid({
            "path": r"images/listing.html",
            "gzip": {"value": True}})

    def test_directives_extra_properties_no_allowed(self):
        self.assertDirectiveInvalid({
            "path": "robots.txt",
            "steak": "medium rare"})


if __name__ == '__main__':
    main()
