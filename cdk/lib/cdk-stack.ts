import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
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
    const leaderboardTable = new dynamodb.Table(this, 'FixThatPromptLeaderboard', {
      tableName: 'fix-that-prompt-leaderboard',
      partitionKey: { name: 'username', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST, // On-demand pricing for variable workloads
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true, // Enable backup and restore
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Keep data when stack is deleted
    });

    // Add Global Secondary Index for querying by score
    leaderboardTable.addGlobalSecondaryIndex({
      indexName: 'score-index',
      partitionKey: { name: 'game_status', type: dynamodb.AttributeType.STRING }, // 'completed' or 'active'
      sortKey: { name: 'final_score', type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Create Cognito User Pool
    const userPool = new cognito.UserPool(this, 'FixThatPromptUserPool', {
      userPoolName: 'fix-that-prompt-user-pool',
      // Sign-in options
      signInAliases: {
        email: true,
        username: true,
      },
      // Self sign-up configuration
      selfSignUpEnabled: true,
      // Email verification
      userVerification: {
        emailSubject: 'Verify your email for Fix That Prompt',
        emailBody: 'Thank you for signing up to Fix That Prompt! Your verification code is {####}',
        emailStyle: cognito.VerificationEmailStyle.CODE,
      },
      // Password policy
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      // Account recovery
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      // Standard attributes
      standardAttributes: {
        email: {
          required: true,
          mutable: true,
        },
        givenName: {
          required: false,
          mutable: true,
        },
        familyName: {
          required: false,
          mutable: true,
        },
      },
      // Remove users after 7 days if not confirmed
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
    });

    // Create User Pool Client (for web applications)
    const userPoolClient = new cognito.UserPoolClient(this, 'FixThatPromptUserPoolClient', {
      userPool,
      userPoolClientName: 'fix-that-prompt-web-client',
      // Authentication flows
      authFlows: {
        userSrp: true, // Secure Remote Password protocol
        userPassword: true, // Allow username/password auth
        adminUserPassword: true, // Allow admin to set passwords
      },
      // OAuth settings
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: false, // Not recommended for production
        },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: [
          'http://localhost:8000/auth/oauth/aws-cognito/callback', // Chainlit OAuth callback (port 8000)
        ],
        logoutUrls: [
          'http://localhost:8000/', // For local Chainlit development
        ],
      },
      // Token validity periods
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      // Security settings
      preventUserExistenceErrors: true,
      generateSecret: true, // Set to true for server-side applications
    });

    // Create User Pool Domain for hosted UI
    const userPoolDomain = new cognito.UserPoolDomain(this, 'FixThatPromptUserPoolDomain', {
      userPool,
      cognitoDomain: {
        domainPrefix: `fix-that-prompt-${cdk.Stack.of(this).account}-${cdk.Stack.of(this).region}`,
      },
    });

    // Identity Pool removed: backend-only access to AWS resources. Users do not need direct AWS credentials.

    // Create ECR repository
    const repository = new ecr.Repository(this, 'FixThatPromptRepository', {
      repositoryName: 'fix-that-prompt-stack',
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
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
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'FixThatPromptTaskDef', {
      memoryLimitMiB: 512,
      cpu: 256,
    });

    // Add container to task definition
    const currentTimestamp = Date.now().toString();
    const imageTag = process.env.IMAGE_TAG || 'latest';
    // Optional: Provide Cognito Client Secret at deploy time (for confidential client flows)
    const cognitoClientSecretParam = new cdk.CfnParameter(this, 'CognitoClientSecret', {
      type: 'String',
      noEcho: true,
      description:
        'Cognito App Client Secret for OAuth token exchange. Leave empty if using public client + PKCE.',
      default: '',
    });
    // Chainlit auth secret for signing session cookies/tokens
    const chainlitAuthSecretParam = new cdk.CfnParameter(this, 'ChainlitAuthSecret', {
      type: 'String',
      noEcho: true,
      description: 'Secret used by Chainlit to sign auth tokens (generate with `chainlit create-secret`).',
      default: '',
    });
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
        'PORT': '8080',
        'DEPLOYMENT_TIME': currentTimestamp, // Force new deployment with timestamp
        'VERSION': currentTimestamp, // Additional versioning
        'IMAGE_TAG': imageTag, // Track which image tag is being used
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
    const targetGroup = new elbv2.ApplicationTargetGroup(this, 'FixThatPromptTargetGroup', {
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
    });

    // Add listener to ALB
    alb.addListener('FixThatPromptListener', {
      port: 80,
      defaultTargetGroups: [targetGroup],
    });

    // Create ECS Service
    const service = new ecs.FargateService(this, 'FixThatPromptService', {
      cluster,
      taskDefinition,
      desiredCount: 1,
      assignPublicIp: true, // Required for public subnets without NAT
      securityGroups: [ecsSecurityGroup],
      serviceName: 'fix-that-prompt-service',
    });

    // Attach service to target group
    service.attachToApplicationTargetGroup(targetGroup);

    // Create CloudFront distribution
    // Using ALB DNS name as origin with WebSocket support for Chainlit
    const distribution = new cloudfront.Distribution(this, 'FixThatPromptDistribution', {
      defaultBehavior: {
        origin: new origins.HttpOrigin(alb.loadBalancerDnsName, {
          protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED, // Disable caching for dynamic app
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER, // Forward all headers, query strings, and cookies
        responseHeadersPolicy: cloudfront.ResponseHeadersPolicy.CORS_ALLOW_ALL_ORIGINS,
      },
      comment: 'Fix That Prompt Stack CloudFront Distribution with WebSocket support',
    });

    const hostedUiBaseUrl = userPoolDomain.baseUrl();
    container.addEnvironment('CHAINLIT_URL',
      `https://${distribution.distributionDomainName}`);
    container.addEnvironment('COGNITO_REDIRECT_URI',
      `https://${distribution.distributionDomainName}/auth/oauth/aws-cognito/callback`);
    // Provide IDs for app runtime helpers
    container.addEnvironment('COGNITO_USER_POOL_ID', userPool.userPoolId);
    container.addEnvironment('COGNITO_CLIENT_ID', userPoolClient.userPoolClientId);
    container.addEnvironment('COGNITO_USER_POOL_DOMAIN', userPoolDomain.domainName);
    container.addEnvironment('AWS_REGION', cdk.Stack.of(this).region);
    container.addEnvironment('OAUTH_COGNITO_SCOPE', 'openid email profile');
    container.addEnvironment('OAUTH_COGNITO_CLIENT_ID', userPoolClient.userPoolClientId);
    // If using a confidential client (has secret), Chainlit/your OAuth handler must send HTTP Basic auth.
    // Provide the secret via a secure stack parameter at deploy time.
    container.addEnvironment('OAUTH_COGNITO_CLIENT_SECRET', cognitoClientSecretParam.valueAsString);
    // Use *base URL* (not bare host) so your app can append /oauth2/authorize etc.
    container.addEnvironment('OAUTH_COGNITO_BASE_URL', hostedUiBaseUrl);
    // If your code needs prebuilt endpoints, export them explicitly:
    container.addEnvironment('OAUTH_COGNITO_AUTHORIZE_URL',
      `${hostedUiBaseUrl}/oauth2/authorize`);
    container.addEnvironment('OAUTH_COGNITO_TOKEN_URL',
      `${hostedUiBaseUrl}/oauth2/token`);
    container.addEnvironment('OAUTH_COGNITO_USERINFO_URL',
      `${hostedUiBaseUrl}/oauth2/userInfo`);

    // Chainlit OAuth provider configuration (aws-cognito)
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_PROVIDER_ID', 'aws-cognito');
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_CLIENT_ID', userPoolClient.userPoolClientId);
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_CLIENT_SECRET', cognitoClientSecretParam.valueAsString);
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_AUTHORIZATION_URL', `${hostedUiBaseUrl}/oauth2/authorize`);
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_TOKEN_URL', `${hostedUiBaseUrl}/oauth2/token`);
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_USER_INFO_URL', `${hostedUiBaseUrl}/oauth2/userInfo`);
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_SCOPES', 'openid email profile');
    container.addEnvironment('CHAINLIT_AUTH_OAUTH_REDIRECT_URL',
      `https://${distribution.distributionDomainName}/auth/oauth/aws-cognito/callback`);
    container.addEnvironment('CHAINLIT_AUTH_SECRET', chainlitAuthSecretParam.valueAsString);

    // Ensure Cognito App Client also accepts CloudFront callback/logout URLs
    const cfnUserPoolClient = userPoolClient.node.defaultChild as cognito.CfnUserPoolClient;
    cfnUserPoolClient.callbackUrLs = [
      ...(cfnUserPoolClient.callbackUrLs || []),
      `https://${distribution.distributionDomainName}/auth/oauth/aws-cognito/callback`,
    ];
    cfnUserPoolClient.logoutUrLs = [
      ...(cfnUserPoolClient.logoutUrLs || []),
      `https://${distribution.distributionDomainName}/`,
    ];

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
      value: distribution.distributionDomainName,
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

    // Cognito outputs
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: userPool.userPoolId,
      description: 'Cognito User Pool ID',
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID',
    });

    new cdk.CfnOutput(this, 'UserPoolDomain', {
      value: userPoolDomain.domainName,
      description: 'Cognito User Pool Domain',
    });

    // Identity Pool outputs removed

    // DynamoDB outputs
    new cdk.CfnOutput(this, 'LeaderboardTableName', {
      value: leaderboardTable.tableName,
      description: 'DynamoDB table name for leaderboard',
    });

    new cdk.CfnOutput(this, 'LeaderboardTableArn', {
      value: leaderboardTable.tableArn,
      description: 'DynamoDB table ARN for leaderboard',
    });

    // The code that defines your stack goes here

    // example resource
    // const queue = new sqs.Queue(this, 'CdkQueue', {
    //   visibilityTimeout: cdk.Duration.seconds(300)
    // });
  }
}
