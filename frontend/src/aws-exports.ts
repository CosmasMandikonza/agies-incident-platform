// AWS Amplify configuration
// Copy this file to aws-exports.ts and update with your values

const awsConfig = {
  // AWS Region
  aws_project_region: 'us-east-1',
  
  // Cognito User Pool
  aws_cognito_region: 'us-east-1',
  aws_user_pools_id: 'YOUR_USER_POOL_ID',
  aws_user_pools_web_client_id: 'YOUR_USER_POOL_CLIENT_ID',
  
  // API Gateway
  aws_api_gateway_name: 'AegisAPI',
  aws_api_gateway_region: 'us-east-1',
  aws_api_gateway_endpoint: 'https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev',
  
  // AppSync GraphQL
  aws_appsync_graphqlEndpoint: 'https://YOUR_APPSYNC_ID.appsync-api.us-east-1.amazonaws.com/graphql',
  aws_appsync_region: 'us-east-1',
  aws_appsync_authenticationType: 'AMAZON_COGNITO_USER_POOLS',
  
  // S3 Storage (if needed)
  aws_user_files_s3_bucket: 'aegis-user-files',
  aws_user_files_s3_bucket_region: 'us-east-1',
  
  // Feature flags
  features: {
    enableAIScribe: true,
    enableChaosExperiments: false,
    enableAdvancedAnalytics: true,
  },
};

export default awsConfig;