#!/usr/bin/env python3
"""
Diagnostic script to check DynamoDB setup and configuration.
"""

import os
import sys
from pathlib import Path


def check_environment():
    """Check environment variables."""
    print("🔍 Checking environment variables...")

    required_vars = ["DYNAMODB_TABLE_NAME", "AWS_REGION"]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var} = {value}")
        else:
            print(f"   ❌ {var} = Not set")
            missing_vars.append(var)

    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        return False

    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    print("\n🔍 Checking dependencies...")

    required_packages = [
        ("boto3", "AWS SDK for Python"),
        ("botocore", "AWS SDK core components"),
    ]

    missing_packages = []
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package} - {description}")
        except ImportError:
            print(f"   ❌ {package} - {description} (NOT INSTALLED)")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("   Install with: pip install " + " ".join(missing_packages))
        return False

    return True


def check_aws_credentials():
    """Check AWS credentials."""
    print("\n🔍 Checking AWS credentials...")

    try:
        import boto3

        # Try to get caller identity
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()

        print(f"   ✅ AWS Account: {identity['Account']}")
        print(f"   ✅ User/Role ARN: {identity['Arn']}")
        return True

    except Exception as e:
        print(f"   ❌ AWS credentials error: {e}")
        print("   💡 Configure AWS credentials with:")
        print("      - aws configure")
        print(
            "      - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)"
        )
        print("      - IAM role (if running on EC2)")
        return False


def check_dynamodb_table():
    """Check if DynamoDB table exists and is accessible."""
    print("\n🔍 Checking DynamoDB table...")

    table_name = os.getenv("DYNAMODB_TABLE_NAME", "fix-that-prompt-leaderboard")
    region = os.getenv("AWS_REGION", "ap-southeast-1")

    try:
        import boto3
        from botocore.exceptions import ClientError

        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)

        # Check if table exists
        table.load()

        print(f"   ✅ Table '{table_name}' exists")
        print(f"   ✅ Table status: {table.table_status}")
        print(f"   ✅ Item count: {table.item_count}")

        # Check GSI
        gsi_found = False
        for gsi in table.global_secondary_indexes or []:
            if gsi["IndexName"] == "score-index":
                print(f"   ✅ GSI 'score-index' exists")
                gsi_found = True
                break

        if not gsi_found:
            print("   ⚠️  GSI 'score-index' not found")

        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            print(f"   ❌ Table '{table_name}' does not exist")
            print("   💡 Deploy your CDK stack: cd cdk && cdk deploy")
        elif error_code == "AccessDenied":
            print(f"   ❌ Access denied to table '{table_name}'")
            print("   💡 Check IAM permissions for DynamoDB")
        else:
            print(f"   ❌ DynamoDB error: {e}")
        return False

    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False


def check_imports():
    """Check if our custom modules can be imported."""
    print("\n🔍 Checking project imports...")

    # Add src to path
    src_path = Path(__file__).parent.parent / "src"
    sys.path.insert(0, str(src_path))

    modules_to_check = [
        ("database.dynamodb_leaderboard", "DynamoDB leaderboard backend"),
        ("database.leaderboard_db", "Leaderboard database wrapper"),
        ("models.player_session", "Player session models"),
    ]

    import_errors = []
    for module_name, description in modules_to_check:
        try:
            __import__(module_name)
            print(f"   ✅ {module_name} - {description}")
        except ImportError as e:
            print(f"   ❌ {module_name} - {description} (IMPORT ERROR)")
            print(f"      Error: {e}")
            import_errors.append(module_name)

    if import_errors:
        print(f"\n⚠️  Import errors in: {', '.join(import_errors)}")
        return False

    return True


def test_dynamodb_connection():
    """Test actual DynamoDB connection."""
    print("\n🔍 Testing DynamoDB connection...")

    try:
        # Add src to path
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))

        from database.dynamodb_leaderboard import DynamoDBLeaderboard

        # Try to initialize
        db = DynamoDBLeaderboard()
        print("   ✅ DynamoDB backend initialized successfully")

        # Try a simple operation
        total_players = db.get_total_players()
        print(f"   ✅ Successfully queried table (total players: {total_players})")

        return True

    except Exception as e:
        print(f"   ❌ DynamoDB connection test failed: {e}")
        return False


def main():
    """Run all diagnostic checks."""
    print("🏥 DynamoDB Diagnostic Tool")
    print("=" * 50)

    checks = [
        ("Environment Variables", check_environment),
        ("Dependencies", check_dependencies),
        ("AWS Credentials", check_aws_credentials),
        ("DynamoDB Table", check_dynamodb_table),
        ("Project Imports", check_imports),
        ("DynamoDB Connection", test_dynamodb_connection),
    ]

    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"   💥 {check_name} check crashed: {e}")
            results.append((check_name, False))

    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 50)

    passed = 0
    failed = 0

    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 All checks passed! DynamoDB should be working correctly.")
    else:
        print(f"\n⚠️  {failed} checks failed. Please fix the issues above.")

        print("\n💡 Common solutions:")
        print("   1. Install dependencies: pip install boto3 botocore")
        print("   2. Configure AWS credentials: aws configure")
        print("   3. Deploy CDK stack: cd cdk && cdk deploy")
        print("   4. Set environment variables in .env file")


if __name__ == "__main__":
    main()
