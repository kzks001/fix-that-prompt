# Shutting Down All AWS Resources Created by This CDK Stack

To quickly shut down (destroy) all AWS resources and services provisioned by this CDK stack (including ECS Fargate, ALB, VPC, etc.), follow these steps:

## 1. Open a Terminal

## 2. Change Directory to the CDK App

```
cd cdk
```

## 3. Destroy the Stack

Run the following command to destroy all resources:

```
npx cdk destroy --force
```

- The `--force` flag skips the confirmation prompt for a faster shutdown.
- This will delete **all resources** created by the stack.

## 4. (Optional) Destroy a Specific Stack

If you have multiple stacks and want to destroy a specific one, use:

```
npx cdk destroy <StackName> --force
```
Replace `<StackName>` with the name of your stack (e.g., `CdkStack`).

---

**Note:**
- This operation is irreversible. All AWS resources created by the stack will be deleted.
- Make sure you have saved any important data before running the destroy command. 