import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';

export class McpServerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // DynamoDB Table for MCP Server
    const mcpTable = new dynamodb.Table(this, 'McpItemsTable', {
      tableName: 'mcp-items',
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: true,
    });

    // Add GSI for listing items by timestamp
    mcpTable.addGlobalSecondaryIndex({
      indexName: 'timestamp-index',
      partitionKey: { name: 'type', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.NUMBER },
    });

    // Main VPC with both public and private subnets
    const vpc = new ec2.Vpc(this, 'McpVpc', {
      maxAzs: 2,
      cidr: '10.0.0.0/16',
      natGateways: 1,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // Security Groups
    const albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSecurityGroup', {
      vpc: vpc,
      description: 'Security group for Application Load Balancer',
      allowAllOutbound: true,
    });

    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP traffic from internet'
    );

    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      'Allow HTTPS traffic from internet'
    );

    const mcpServerSecurityGroup = new ec2.SecurityGroup(this, 'McpServerSecurityGroup', {
      vpc: vpc,
      description: 'Security group for MCP server',
      allowAllOutbound: true,
    });

    mcpServerSecurityGroup.addIngressRule(
      albSecurityGroup,
      ec2.Port.tcp(8000),
      'Allow HTTP traffic from ALB'
    );

    const frontendSecurityGroup = new ec2.SecurityGroup(this, 'FrontendSecurityGroup', {
      vpc: vpc,
      description: 'Security group for frontend',
      allowAllOutbound: true,
    });

    frontendSecurityGroup.addIngressRule(
      albSecurityGroup,
      ec2.Port.tcp(3000),
      'Allow HTTP traffic from ALB'
    );

    // ECS Cluster
    const cluster = new ecs.Cluster(this, 'McpCluster', {
      vpc: vpc,
      clusterName: 'mcp-cluster',
    });

    // Task Execution Role
    const taskExecutionRole = new iam.Role(this, 'TaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    // MCP Server Task Role
    const mcpServerTaskRole = new iam.Role(this, 'McpServerTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      inlinePolicies: {
        DynamoDBAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:PutItem',
                'dynamodb:GetItem',
                'dynamodb:UpdateItem',
                'dynamodb:DeleteItem',
                'dynamodb:Query',
                'dynamodb:Scan',
              ],
              resources: [
                mcpTable.tableArn,
                `${mcpTable.tableArn}/index/*`,
              ],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:ListFoundationModels',
                'bedrock:GetFoundationModel',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // Log Groups
    const mcpServerLogGroup = new logs.LogGroup(this, 'McpServerLogGroup', {
      logGroupName: '/ecs/mcp-server',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const frontendLogGroup = new logs.LogGroup(this, 'FrontendLogGroup', {
      logGroupName: '/ecs/frontend',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Application Load Balancer
    const alb = new elbv2.ApplicationLoadBalancer(this, 'MainAlb', {
      vpc: vpc,
      internetFacing: true,
      loadBalancerName: 'mcp-main-alb',
      securityGroup: albSecurityGroup,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC,
      },
    });

    // Target Groups
    const mcpServerTargetGroup = new elbv2.ApplicationTargetGroup(this, 'McpServerTargetGroup', {
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      vpc: vpc,
      targetType: elbv2.TargetType.IP,
      targetGroupName: 'mcp-server-tg',
      healthCheck: {
        enabled: true,
        path: '/health',
        protocol: elbv2.Protocol.HTTP,
        port: '8000',
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
        timeout: cdk.Duration.seconds(10),
        interval: cdk.Duration.seconds(30),
      },
    });

    const frontendTargetGroup = new elbv2.ApplicationTargetGroup(this, 'FrontendTargetGroup', {
      port: 3000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      vpc: vpc,
      targetType: elbv2.TargetType.IP,
      targetGroupName: 'frontend-tg',
      healthCheck: {
        enabled: true,
        path: '/',
        protocol: elbv2.Protocol.HTTP,
        port: '3000',
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
        timeout: cdk.Duration.seconds(10),
        interval: cdk.Duration.seconds(30),
      },
    });

    // Listener with path-based routing
    const listener = alb.addListener('MainListener', {
      port: 80,
      defaultTargetGroups: [frontendTargetGroup], // Default to frontend
    });

    // Route /api/* to backend
    listener.addTargetGroups('McpServerRoute', {
      targetGroups: [mcpServerTargetGroup],
      conditions: [elbv2.ListenerCondition.pathPatterns(['/api/*', '/health', '/docs', '/mcp', '/mcp/*'])],
      priority: 100,
    });

    // Task Definitions
    const mcpServerTaskDefinition = new ecs.FargateTaskDefinition(this, 'McpServerTaskDefinition', {
      memoryLimitMiB: 512,
      cpu: 256,
      executionRole: taskExecutionRole,
      taskRole: mcpServerTaskRole,
    });

    const frontendTaskDefinition = new ecs.FargateTaskDefinition(this, 'FrontendTaskDefinition', {
      memoryLimitMiB: 512,
      cpu: 256,
      executionRole: taskExecutionRole,
    });

    // Container Definitions
    mcpServerTaskDefinition.addContainer('McpServerContainer', {
      image: ecs.ContainerImage.fromAsset('./mcp-server', {
        platform: cdk.aws_ecr_assets.Platform.LINUX_AMD64,
      }),
      environment: {
        DYNAMODB_TABLE_NAME: mcpTable.tableName,
        AWS_DEFAULT_REGION: this.region,
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'mcp-server',
        logGroup: mcpServerLogGroup,
      }),
      portMappings: [
        {
          containerPort: 8000,
          protocol: ecs.Protocol.TCP,
        },
      ],
    });

    frontendTaskDefinition.addContainer('FrontendContainer', {
      image: ecs.ContainerImage.fromAsset('./simple-frontend', {
        platform: cdk.aws_ecr_assets.Platform.LINUX_AMD64,
      }),
      environment: {
        NODE_ENV: 'production',
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'frontend',
        logGroup: frontendLogGroup,
      }),
      portMappings: [
        {
          containerPort: 3000,
          protocol: ecs.Protocol.TCP,
        },
      ],
    });

    // ECS Services
    const mcpServerService = new ecs.FargateService(this, 'McpServerService', {
      cluster: cluster,
      taskDefinition: mcpServerTaskDefinition,
      desiredCount: 1,
      assignPublicIp: false,
      securityGroups: [mcpServerSecurityGroup],
      serviceName: 'mcp-server-service',
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
    });

    const frontendService = new ecs.FargateService(this, 'FrontendService', {
      cluster: cluster,
      taskDefinition: frontendTaskDefinition,
      desiredCount: 1,
      assignPublicIp: false,
      securityGroups: [frontendSecurityGroup],
      serviceName: 'frontend-service',
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
    });

    // Attach services to target groups
    mcpServerService.attachToApplicationTargetGroup(mcpServerTargetGroup);
    frontendService.attachToApplicationTargetGroup(frontendTargetGroup);

    // Outputs
    new cdk.CfnOutput(this, 'ApplicationUrl', {
      value: `http://${alb.loadBalancerDnsName}`,
      description: 'Main application URL (Frontend and API)',
    });

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: `http://${alb.loadBalancerDnsName}/api`,
      description: 'API base URL',
    });

    new cdk.CfnOutput(this, 'HealthCheckUrl', {
      value: `http://${alb.loadBalancerDnsName}/health`,
      description: 'Backend health check URL',
    });

    new cdk.CfnOutput(this, 'DynamoDBTableName', {
      value: mcpTable.tableName,
      description: 'DynamoDB table name',
    });

    new cdk.CfnOutput(this, 'LoadBalancerDnsName', {
      value: alb.loadBalancerDnsName,
      description: 'Load balancer DNS name',
    });
  }
}