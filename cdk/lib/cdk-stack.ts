import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

export class CdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create VPC with public subnets for ultra-simple architecture
    const vpc = new ec2.Vpc(this, 'FixThatPromptVpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
      ],
    });

    // Gateway VPC Endpoint for DynamoDB (keeps traffic on AWS backbone)
    vpc.addGatewayEndpoint('DynamoDbEndpoint', {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
    });

    // Create ECR repository
    const repository = new ecr.Repository(this, 'FixThatPromptRepository', {
      repositoryName: 'fix-that-prompt-stack',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create ECS Cluster
    const cluster = new ecs.Cluster(this, 'FixThatPromptCluster', {
      vpc,
      clusterName: 'fix-that-prompt-cluster',
    });

    // Create CloudWatch Log Group
    const logGroup = new logs.LogGroup(this, 'FixThatPromptLogGroup', {
      logGroupName: '/ecs/fix-that-prompt-stack',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create Task Definition
    const taskDefinition = new ecs.FargateTaskDefinition(
      this,
      'FixThatPromptTaskDef',
      {
        memoryLimitMiB: 1024,
        cpu: 512,
      }
    );

    // -------------------- DynamoDB: table (secure defaults) --------------------
    const table = new dynamodb.Table(this, 'FixThatPromptTable', {
      tableName: 'fix-that-prompt-leaderboard',
      partitionKey: { name: 'username', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // change to RETAIN in prod
    });

    // Add Global Secondary Index for querying by score
    table.addGlobalSecondaryIndex({
      indexName: 'score-index',
      partitionKey: {
        name: 'game_status',
        type: dynamodb.AttributeType.STRING, // 'completed' or 'active'
      },
      sortKey: { name: 'final_score', type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Least-privilege access for the running container to read/write the table
    table.grantReadWriteData(taskDefinition.taskRole);

    // Add container to task definition
    const currentTimestamp = Date.now().toString();
    const imageTag = process.env.IMAGE_TAG || 'latest';
    const container = taskDefinition.addContainer('FixThatPromptContainer', {
      image: ecs.ContainerImage.fromEcrRepository(repository, imageTag),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'fix-that-prompt-stack',
        logGroup,
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
        DYNAMODB_TABLE_NAME: table.tableName,
        AWS_REGION: this.region,
      },
    });

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
      'Allow HTTP traffic from anywhere'
    );

    // Allow traffic from ALB to ECS tasks
    ecsSecurityGroup.addIngressRule(
      albSecurityGroup,
      ec2.Port.tcp(8080),
      'Allow traffic from ALB to ECS tasks'
    );

    // Create Application Load Balancer
    const alb = new elbv2.ApplicationLoadBalancer(this, 'FixThatPromptAlb', {
      vpc,
      internetFacing: true,
      securityGroup: albSecurityGroup,
      loadBalancerName: 'fix-that-prompt-alb',
    });

    // Create Target Group
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
          interval: cdk.Duration.seconds(30),
          timeout: cdk.Duration.seconds(5),
          healthyThresholdCount: 2,
          unhealthyThresholdCount: 5,
        },
      }
    );

    // Add listener to ALB
    alb.addListener('FixThatPromptListener', {
      port: 80,
      defaultTargetGroups: [targetGroup],
    });

    // Create ECS Service
    const service = new ecs.FargateService(this, 'FixThatPromptService', {
      cluster,
      taskDefinition,
      desiredCount: 1, // Single instance for Chainlit session consistency
      assignPublicIp: true,
      securityGroups: [ecsSecurityGroup],
      serviceName: 'fix-that-prompt-service',
    });

    // Attach service to target group
    service.attachToApplicationTargetGroup(targetGroup);

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
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
          responseHeadersPolicy:
            cloudfront.ResponseHeadersPolicy.CORS_ALLOW_ALL_ORIGINS,
        },
        comment:
          'Fix That Prompt Stack CloudFront Distribution with WebSocket support',
      }
    );

    // Outputs
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

    new cdk.CfnOutput(this, 'LeaderboardTableName', {
      value: table.tableName,
      description: 'DynamoDB table name for leaderboard',
    });
  }
}
