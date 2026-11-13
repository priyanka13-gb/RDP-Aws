"""Render IAM review files locally. Never calls AWS or enables publishing."""

import argparse
import json
import re
from pathlib import Path


def policies(account, subject):
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValueError("Use a valid account ID privately.")
    if not re.fullmatch(r"repo:priyanka13-gb(?:@[0-9]+)?/RDP-Aws(?:@[0-9]+)?"
                        r":environment:ecr-release", subject):
        raise ValueError("Exact confirmed repository/environment subject required; no wildcard.")
    trust = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Action": "sts:AssumeRoleWithWebIdentity",
        "Principal": {"Federated": f"arn:aws:iam::{account}:oidc-provider/"
                                    "token.actions.githubusercontent.com"},
        "Condition": {"StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": subject}}}]}
    policy = {"Version": "2012-10-17", "Statement": [
        {"Sid": "RegionalECRAuthorizationOnly", "Effect": "Allow",
         "Action": ["ecr:GetAuthorizationToken"], "Resource": "*",
         "Condition": {"StringEquals": {"aws:RequestedRegion": "ap-southeast-2"}}},
        {"Sid": "ExistingApplicationRepositoryOnly", "Effect": "Allow",
         "Action": ["ecr:DescribeRepositories", "ecr:DescribeImages", "ecr:BatchGetImage",
                    "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage",
                    "ecr:DescribeImageScanFindings"],
         "Resource": f"arn:aws:ecr:ap-southeast-2:{account}:repository/"
                     "aws-resilient-delivery-platform-dev",
         "Condition": {"StringEquals": {"aws:RequestedRegion": "ap-southeast-2"}}}]}
    return trust, policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--subject", required=True)
    args = parser.parse_args()
    trust, permission = policies(args.account_id, args.subject)
    directory = Path(__file__).resolve().parents[1] / ".tools" / "release-iam"
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in [("trust.json", trust), ("permissions.json", permission)]:
        (directory / name).write_text(json.dumps(value, indent=2) + "\n")
    print("IAM review files saved in ignored .tools/release-iam. No AWS calls made.")


if __name__ == "__main__":
    main()
