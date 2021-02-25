How we are set up with AWS
==========================

* MySQL database runs on Dreamhost at mysql.digitalcorpora.org (cheaper than AWS)
  - Used for WordPress
  - Used for storing all files and hashes of the files (transitioning to DynamoDB)
* DynamoDB runs in us-west-2.
  - Used for storing all files and hashes of the files
* AWS EC2 us-west-2
  - Key pairs stores simson's Keypair for gaining access to the ec2-user on any VMs we spin up
* AWS Secrets
  - secret digitalcorpora/dbwriter stores username/password for MySQL database user
  - $0.40 per secret per month, $0.05 per 10,000 API calls
* AWS Lambda
  - Not in use yet; will use for automatically hashing new files as they are uploaded to S3

* MyWebApplication Role
  - SecretsManagerReadWrite, AmazonS3ReadOnlyAccess, AmazonDynamoDBFullAccess
* Lambda is launched with the IAM role DCStatsRole (for Lambda)
  - IAM Role DCStats has access to: SecretsManagerReadWrite, AmazonS3ReadOnlyAccess, AmazonDynamoDBFullAccess