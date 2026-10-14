# Cross-account Storage Lens access

Run the CLI below with administrator credentials in **Digital Corpora account
809276937361**. It creates `DigitalCorporaStorageLensReadOnly`, trusting **Simson
Garfinkel account 376778049323**, with read-only access to every Storage Lens
dashboard owned by Digital Corpora, including any enabled Advanced metrics. There
is no separate Advanced viewing permission. This grants dashboard access only;
enabling Advanced, changing configuration, and reading exported S3 files are separate.
[AWS Storage Lens permissions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_iam_permissions.html)

## Run from the repository

```sh
AWS_CONFIG_FILE="$HOME/.aws/config" AWS_PROFILE=digitalcorpora-admin make -C doc/statistics-options-2026-10-09 grant-storage-lens-access
```

Replace `digitalcorpora-admin` with your actual Digital Corpora administrator
profile name in your home AWS config. The project SSO profiles are read-only and
cannot create this role. In AWS CloudShell,
sign into account 809276937361, upload the single script, and run:

```sh
bash grant-storage-lens-access.sh
```

The script requires Bash and AWS CLI v2, checks the current account before mutation,
and needs `iam:CreateRole` and `iam:PutRolePolicy` for the new role. An SCP or
permissions boundary can still restrict the administrator or subsequent role use.
No dashboard, bucket policy, Advanced setting, or export destination is changed.
IAM role creation/access has no fee; existing paid Storage Lens settings retain
their existing charges.

For a local preview without AWS calls or credentials:

```sh
make -C doc/statistics-options-2026-10-09 plan-storage-lens-access
```

This intentionally creates a new role only: if the name already exists, it stops
without replacing that role's trust or policies. If policy attachment fails after
creation, the new role remains and the command fails. Inspect its trust and all
attached policies in IAM, then attach the `permissionsPolicy` printed by `--plan`
using `aws iam put-role-policy`; do not blindly reuse an unrelated existing role.

## Use it from Simson's account

Sign into account 376778049323 with an IAM user or federated role, then open
[Switch to Digital Corpora Storage Lens](https://signin.aws.amazon.com/switchrole?account=809276937361&roleName=DigitalCorporaStorageLensReadOnly&displayName=DigitalCorpora-StorageLens).
Open the [S3 Storage Lens dashboards in Oregon](https://us-west-2.console.aws.amazon.com/s3/lens?region=us-west-2).
Choose the dashboard's home Region if it differs from Oregon. IAM permissions
apply to Digital Corpora dashboards in all Regions, including the default dashboard.
The root login cannot switch console roles or view Storage Lens dashboards.

The supplied `arn:aws:iam::376778049323:root` delegates trust to that **account**;
it does not restrict access to its root user. The IAM identity you use in that
account must also have permission to assume this role. An administrator identity
usually already has it; otherwise attach this policy to the actual IAM user/role
or Identity Center permission set in account 376778049323:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::809276937361:role/DigitalCorporaStorageLensReadOnly"
  }]
}
```

The repository now has SSO and role profiles in `etc/aws-digitalcorpora-config`.
After `direnv allow`, authenticate and verify access:

```sh
make aws-sso-login
make aws-identity
make aws-storage-lens-identity
make aws-storage-lens-list
```

The `digitalcorpora` SSO source profile selects `DigitalCorporaAccess` in
account `376778049323`. The `digitalcorpora-storage-lens` role profile selects
`DigitalCorporaStorageLensReadOnly` in account `809276937361`. `.envrc` clears
inherited static keys and tokens and bypasses the 1Password shell wrapper.
For direct CLI operations, use `--profile digitalcorpora-storage-lens`.
SSO uses `us-east-1`; dashboard configuration queries default to `us-west-2`.

Allow a short time for IAM propagation. CLI configuration listing alone does not
verify dashboard metrics: open the console and inspect an enabled Advanced dashboard
after switching roles. The Storage Lens dashboard itself is a console view; exported
CSV/Parquet access needs separately scoped `s3:GetObject` permissions, not supplied
by this CLI. [AWS cross-account role tutorial](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_cross-account-with-roles.html),
[account principal semantics](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_principal.html#principal-accounts),
[S3 action/resource reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_s3.html)

## Verification status

The role policies and Bash syntax are checked locally; the report build was rendered
and visually inspected. No IAM changes were performed by the agent. On 9 October 2026, SSO login in
account `376778049323` and assumption of the existing read-only role in account
`809276937361` were verified against AWS. Dashboard metric display still requires
console verification; role assumption alone does not verify metrics or exports.
