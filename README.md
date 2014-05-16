# s3sitedeploy - Wercker S3 Static Site Deployment Step
You need s3sitedeploy if:

* You have a static site built with Wercker
* You want it deployed to S3
* You want more granular page/object specific settings than provided by s3sync

This is still in early stages of development - not recommended for production use.

[![wercker status](https://app.wercker.com/status/37c8b18803f5556d6b9434c49d9a0aee/m/master "wercker status")](https://app.wercker.com/project/bykey/37c8b18803f5556d6b9434c49d9a0aee)

# Step options

 * `bucket_name` (required) - The name of the S3 bucket to deploy to. E.g. "www-example-com-public-bucket"
 * `access_key_id` (required) - Access key ID credential for the AWS IAM user that  has permission to upload to the bucket
 * `secret_access_key` (required) - Secret access key credential for the access key ID
 * `deploy_dir` (optional) - Include only if your site is output into a subdirectory of the Wercker build job output directory. E.g. "generated-site-html/"

An example `wercker.yml`

    deploy:
        steps:
            - awooldrige/s3sitedeploy:
                access_key_id: $AWS_ACCESS_KEY_ID
                secret_access_key: $AWS_SECRET_ACCESS_KEY
                bucket_name: $AWS_BUCKET_NAME


# JSON configuration file
Further configuration is available by including an `s3sitedeploy.json` file within the root directory to upload. At present, this configuration file allows you to:

 * Set page/object specific headers, for example setting a long Cache-Control on CSS and images, but a short one on all webpages
 * Specify that certain mimetypes should be automatically gzipped before uploading to S3


### Example site configuration
The following example configuration:

 * Sets by default all objects to have a cache lifetime of two minutes
 * Sets a long cache lifetime on all items under `assets/` which is where all CSS, images and JavaScript are kept
 * Sets an easter egg header on a certain article
 * Sets all HTML pages, stylesheets and JavaScript to be gzipped automatically

    {
        "object_specific": [
            {
                "path": ".*",
                "headers": { "Cache-Control": "max-age=180" }
            },
            {
                "path": "^assets/.*",
                "headers": { "Cache-Control": "max-age=31104000" }
            },
            {
                "path": "^news/2014/how-to/index\.html*",
                "headers": {
                    "X-Easter-Egg": "found",
                    "Cache-Control": "private, max-age=10"
                }
            },
        ],
        "gzip_mimetypes": [
            "text/html", "text/css", "application/javascript"
        ]
    }
