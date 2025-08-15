import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as autoscaling from 'aws-cdk-lib/aws-autoscaling';
import { Construct } from 'constructs';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export class CdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create VPC with public subnets for ultra-simple architecture
    const vpc = new ec2.Vpc(this, 'FixThatPromptVpc', {
      maxAzs: 2,
      natGateways: 0, // No NAT gateways for cost optimization
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
      ],
    });

    // Create DynamoDB table for leaderboard
    const leaderboardTable = new dynamodb.Table(
      this,
      'FixThatPromptLeaderboard',
      {
        tableName: 'fix-that-prompt-leaderboard',
        partitionKey: { name: 'username', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST, // On-demand pricing
        pointInTimeRecoverySpecification: {
          pointInTimeRecoveryEnabled: true, // Enable backup and restore
        },
        removalPolicy: cdk.RemovalPolicy.RETAIN, // Keep data when stack is deleted
      },
    );

    // Add Global Secondary Index for querying by score
    leaderboardTable.addGlobalSecondaryIndex({
      indexName: 'score-index',
      partitionKey: {
        name: 'game_status',
        type: dynamodb.AttributeType.STRING, // 'completed' or 'active'
      },
      sortKey: { name: 'final_score', type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Create ECR repository
    const repository = new ecr.Repository(this, 'FixThatPromptRepository', {
      repositoryName: 'fix-that-prompt-stack',
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
    });

    // Create ECS Cluster
    const cluster = new ecs.Cluster(this, 'FixThatPromptCluster', {
      vpc,
      clusterName: 'fix-that-prompt-cluster',
      enableFargateCapacityProviders: true,
    });

    // Create CloudWatch Log Groups with enhanced retention
    const applicationLogGroup = new logs.LogGroup(
      this,
      'FixThatPromptApplicationLogs',
      {
        logGroupName: '/ecs/fix-that-prompt-stack/application',
        retention: logs.RetentionDays.THREE_MONTHS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      },
    );

    const errorLogGroup = new logs.LogGroup(this, 'FixThatPromptErrorLogs', {
      logGroupName: '/ecs/fix-that-prompt-stack/errors',
      retention: logs.RetentionDays.ONE_YEAR,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const dynamodbLogGroup = new logs.LogGroup(
      this,
      'FixThatPromptDynamoDBLogs',
      {
        logGroupName: '/ecs/fix-that-prompt-stack/dynamodb',
        retention: logs.RetentionDays.ONE_YEAR,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      },
    );

    // Create Task Definition with enhanced resources
    const taskDefinition = new ecs.FargateTaskDefinition(
      this,
      'FixThatPromptTaskDef',
      {
        memoryLimitMiB: 1024,
        cpu: 512,
      },
    );

    // Grant DynamoDB permissions to the task (least privilege)
    leaderboardTable.grantReadWriteData(taskDefinition.taskRole);

    // Add container to task definition
    const currentTimestamp = Date.now().toString();
    const imageTag = process.env.IMAGE_TAG || 'latest';

    const container = taskDefinition.addContainer(
      'FixThatPromptContainer',
      {
        image: ecs.ContainerImage.fromEcrRepository(repository, imageTag),
        logging: ecs.LogDrivers.awsLogs({
          streamPrefix: 'fix-that-prompt-stack',
          logGroup: applicationLogGroup,
        }),
        portMappings: [
          {
            containerPort: 8080,
            protocol: ecs.Protocol.TCP,
          },
        ],
        environment: {
          PORT: '8080',
          DEPLOYMENT_TIME: currentTimestamp,
          VERSION: currentTimestamp,
          IMAGE_TAG: imageTag,
          LOG_LEVEL: 'INFO',
          ENVIRONMENT: 'production',
          DYNAMODB_TABLE_NAME: leaderboardTable.tableName,
        },
        healthCheck: {
          command: ['CMD-SHELL', 'curl -f http://localhost:8080/ || exit 1'],
          interval: cdk.Duration.seconds(30),
          timeout: cdk.Duration.seconds(5),
          retries: 3,
          startPeriod: cdk.Duration.seconds(60),
        },
      },
    );

    // Create Security Group for ECS tasks
    const ecsSecurityGroup = new ec2.SecurityGroup(this, 'EcsSecurityGroup', {
      vpc,
      description: 'Security group for Fix That Prompt ECS tasks',
      allowAllOutbound: true,
    });

    // Create Security Group for ALB
    const albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSecurityGroup', {
      vpc,
      description: 'Security group for Fix That Prompt ALB',
      allowAllOutbound: true,
    });

    // Allow HTTP traffic from anywhere to ALB
    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP traffic from anywhere',
    );

    // Allow HTTPS traffic from anywhere to ALB (for future use)
    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      'Allow HTTPS traffic from anywhere',
    );

    // Allow traffic from ALB to ECS tasks
    ecsSecurityGroup.addIngressRule(
      albSecurityGroup,
      ec2.Port.tcp(8080),
      'Allow traffic from ALB to ECS tasks',
    );

    // Create Application Load Balancer
    const alb = new elbv2.ApplicationLoadBalancer(this, 'FixThatPromptAlb', {
      vpc,
      internetFacing: true,
      securityGroup: albSecurityGroup,
      loadBalancerName: 'fix-that-prompt-alb',
      idleTimeout: cdk.Duration.seconds(300), // 5 minutes for WebSocket connections
    });

    // Create Target Group with enhanced health checks
    const targetGroup = new elbv2.ApplicationTargetGroup(
      this,
      'FixThatPromptTargetGroup',
      {
        vpc,
        port: 8080,
        protocol: elbv2.ApplicationProtocol.HTTP,
        targetType: elbv2.TargetType.IP,
        healthCheck: {
          enabled: true,
          path: '/',
          healthyHttpCodes: '200-299',
          interval: cdk.Duration.seconds(15), // Faster health checks
          timeout: cdk.Duration.seconds(5),
          healthyThresholdCount: 2,
          unhealthyThresholdCount: 3,
        },
        deregistrationDelay: cdk.Duration.seconds(30), // Faster instance removal
      },
    );

    // Add listener to ALB
    alb.addListener('FixThatPromptListener', {
      port: 80,
      defaultTargetGroups: [targetGroup],
    });

    // Create ECS Service with auto-scaling
    const service = new ecs.FargateService(this, 'FixThatPromptService', {
      cluster,
      taskDefinition,
      desiredCount: 2, // Start with 2 instances for high availability
      assignPublicIp: true, // Required for public subnets without NAT
      securityGroups: [ecsSecurityGroup],
      serviceName: 'fix-that-prompt-service',
      enableExecuteCommand: true, // Enable ECS Exec for debugging
      circuitBreaker: { rollback: true }, // Auto-rollback on deployment failures
      minHealthyPercent: 100,
      maxHealthyPercent: 200,
    });

    // Attach service to target group
    service.attachToApplicationTargetGroup(targetGroup);

    // Create Auto Scaling for the service
    const scaling = service.autoScaleTaskCount({
      minCapacity: 2, // Minimum 2 instances for HA
      maxCapacity: 10, // Maximum 10 instances
    });

    // Scale up based on CPU utilization
    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Scale up based on memory utilization
    scaling.scaleOnMemoryUtilization('MemoryScaling', {
      targetUtilizationPercent: 80,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Scale up based on custom metric (fix: use full names)
    scaling.scaleOnMetric('CustomScaling', {
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApplicationELB',
        metricName: 'RequestCount',
        dimensionsMap: {
          LoadBalancer: alb.loadBalancerFullName,
          TargetGroup: targetGroup.targetGroupFullName,
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(1),
      }),
      scalingSteps: [
        { upper: 10, change: -1 },
        { lower: 20, change: +1 },
      ],
      adjustmentType: autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
    });

    // Create CloudFront distribution
    const distribution = new cloudfront.Distribution(
      this,
      'FixThatPromptDistribution',
      {
        defaultBehavior: {
          origin: new origins.HttpOrigin(alb.loadBalancerDnsName, {
            protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
          }),
          viewerProtocolPolicy:
            cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED, // Dynamic app
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER, // Fwd all
          responseHeadersPolicy:
            cloudfront.ResponseHeadersPolicy.CORS_ALLOW_ALL_ORIGINS,
        },
        comment:
          'Fix That Prompt Stack CloudFront Distribution with WebSocket support',
      },
    );

    // Create CloudWatch Alarms for monitoring
    const cpuAlarm = new cloudwatch.Alarm(this, 'HighCPUAlarm', {
      metric: service.metricCpuUtilization(),
      threshold: 80,
      evaluationPeriods: 2,
      alarmDescription: 'High CPU utilization on Fix That Prompt service',
    });

    const memoryAlarm = new cloudwatch.Alarm(this, 'HighMemoryAlarm', {
      metric: service.metricMemoryUtilization(),
      threshold: 85,
      evaluationPeriods: 2,
      alarmDescription: 'High memory utilization on Fix That Prompt service',
    });

    // Fix deprecation: use new metrics API for unhealthy hosts
    const unhealthyHostAlarm = new cloudwatch.Alarm(
      this,
      'UnhealthyHostAlarm',
      {
        metric: targetGroup.metrics.unhealthyHostCount(),
        threshold: 1,
        evaluationPeriods: 1,
        alarmDescription:
          'Unhealthy hosts in Fix That Prompt target group',
      },
    );

    // Create DynamoDB monitoring alarms
    // Fix deprecation: use per-operation throttled metrics + math expression
    const ddbThrottlePut = leaderboardTable
      .metricThrottledRequestsForOperation('PutItem', {
        period: cdk.Duration.minutes(1),
      });
    const ddbThrottleGet = leaderboardTable
      .metricThrottledRequestsForOperation('GetItem', {
        period: cdk.Duration.minutes(1),
      });
    const ddbThrottleUpdate = leaderboardTable
      .metricThrottledRequestsForOperation('UpdateItem', {
        period: cdk.Duration.minutes(1),
      });
    const ddbThrottleQuery = leaderboardTable
      .metricThrottledRequestsForOperation('Query', {
        period: cdk.Duration.minutes(1),
      });
    const ddbThrottleScan = leaderboardTable
      .metricThrottledRequestsForOperation('Scan', {
        period: cdk.Duration.minutes(1),
      });

    const ddbThrottleAll = new cloudwatch.MathExpression({
      expression: 'put + get + upd + qry + scn',
      period: cdk.Duration.minutes(1),
      usingMetrics: {
        put: ddbThrottlePut,
        get: ddbThrottleGet,
        upd: ddbThrottleUpdate,
        qry: ddbThrottleQuery,
        scn: ddbThrottleScan,
      },
    });

    const dynamoDBThrottledRequestsAlarm = new cloudwatch.Alarm(
      this,
      'DynamoDBThrottledRequestsAlarm',
      {
        metric: ddbThrottleAll,
        threshold: 1,
        evaluationPeriods: 1,
        alarmDescription: 'DynamoDB throttled requests detected',
      },
    );

    const dynamoDBUserErrorsAlarm = new cloudwatch.Alarm(
      this,
      'DynamoDBUserErrorsAlarm',
      {
        metric: leaderboardTable.metricUserErrors(),
        threshold: 1,
        evaluationPeriods: 1,
        alarmDescription: 'DynamoDB user errors detected',
      },
    );

    // Output important values
    new cdk.CfnOutput(this, 'RepositoryUri', {
      value: repository.repositoryUri,
      description: 'ECR Repository URI',
    });

    new cdk.CfnOutput(this, 'ClusterName', {
      value: cluster.clusterName,
      description: 'ECS Cluster Name',
    });

    new cdk.CfnOutput(this, 'ServiceName', {
      value: service.serviceName,
      description: 'ECS Service Name',
    });

    new cdk.CfnOutput(this, 'LoadBalancerDnsName', {
      value: alb.loadBalancerDnsName,
      description: 'Application Load Balancer DNS Name',
    });

    new cdk.CfnOutput(this, 'CloudFrontDomainName', {
      value: distribution.domainName,
      description: 'CloudFront Domain Name',
    });

    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: distribution.distributionId,
      description: 'CloudFront Distribution ID',
    });

    new cdk.CfnOutput(this, 'VpcId', {
      value: vpc.vpcId,
      description: 'VPC ID',
    });

    // DynamoDB outputs
    new cdk.CfnOutput(this, 'LeaderboardTableName', {
      value: leaderboardTable.tableName,
      description: 'DynamoDB table name for leaderboard',
    });

    new cdk.CfnOutput(this, 'LeaderboardTableArn', {
      value: leaderboardTable.tableArn,
      description: 'DynamoDB table ARN for leaderboard',
    });

    // Log group outputs
    new cdk.CfnOutput(this, 'ApplicationLogGroup', {
      value: applicationLogGroup.logGroupName,
      description: 'Application CloudWatch Log Group',
    });

    new cdk.CfnOutput(this, 'ErrorLogGroup', {
      value: errorLogGroup.logGroupName,
      description: 'Error CloudWatch Log Group',
    });

    new cdk.CfnOutput(this, 'DynamoDBLogGroup', {
      value: dynamodbLogGroup.logGroupName,
      description: 'DynamoDB CloudWatch Log Group',
    });
  }
}
