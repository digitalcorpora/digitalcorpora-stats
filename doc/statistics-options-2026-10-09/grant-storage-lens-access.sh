#!/usr/bin/env bash
# Create a Digital Corpora role for viewing Storage Lens from Simson's account.
# The trust delegates to account 376778049323; its identities need AssumeRole.
# The role reads free and already-enabled Advanced dashboards and their settings.
# It cannot enable paid metrics, modify dashboards, or read corpus/export objects.
# Check the active account before creating a new role and its inline policy.
# An existing role is never overwritten; a partial failure needs operator repair.
# --plan prints the exact policies locally without AWS credentials or mutations.
# AWS_PROFILE and AWS_REGION select normal AWS CLI credentials and endpoint settings.
set -euo pipefail

role_name=DigitalCorporaStorageLensReadOnly
trust_policy='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":"arn:aws:iam::376778049323:root"},"Action":"sts:AssumeRole"}]}'
read_policy='{"Version":"2012-10-17","Statement":[{"Sid":"ListDashboards","Effect":"Allow","Action":"s3:ListStorageLensConfigurations","Resource":"*"},{"Sid":"ReadDigitalCorporaDashboards","Effect":"Allow","Action":["s3:GetStorageLensConfiguration","s3:GetStorageLensConfigurationTagging","s3:GetStorageLensDashboard"],"Resource":"arn:aws:s3:*:809276937361:storage-lens/*"}]}'

case "${1:-}" in
    --plan)
        [[ $# -eq 1 ]] || { echo 'Use --plan without other arguments.' >&2; exit 2; }
        printf '{"roleName":"%s","trustPolicy":%s,"permissionsPolicy":%s}\n' "$role_name" "$trust_policy" "$read_policy"
        exit 0
        ;;
    --help)
        echo 'Usage: bash grant-storage-lens-access.sh [--plan|--help]'
        echo 'Run without arguments using administrator credentials in account 809276937361.'
        exit 0
        ;;
esac
[[ $# -eq 0 ]] || { echo 'Unknown arguments; see --help.' >&2; exit 2; }
command -v aws >/dev/null || { echo 'AWS CLI is required.' >&2; exit 1; }
account_id=$(aws sts get-caller-identity --query Account --output text --no-cli-pager)
[[ "$account_id" == 809276937361 ]] || { echo "Refusing to create a role in account $account_id; expected 809276937361." >&2; exit 1; }

aws iam create-role --role-name "$role_name" --description 'Read Digital Corpora Storage Lens dashboards from Simson account 376778049323' --assume-role-policy-document "$trust_policy" --query Role.Arn --output text --no-cli-pager
if ! aws iam put-role-policy --role-name "$role_name" --policy-name StorageLensReadOnly --policy-document "$read_policy" --no-cli-pager; then
    echo "Role created, but policy attachment failed. Inspect $role_name and attach the printed --plan permissionsPolicy before using it." >&2
    exit 1
fi
echo "Created read-only role: arn:aws:iam::809276937361:role/$role_name"
echo "Switch role: https://signin.aws.amazon.com/switchrole?account=809276937361&roleName=$role_name&displayName=DigitalCorpora-StorageLens"
