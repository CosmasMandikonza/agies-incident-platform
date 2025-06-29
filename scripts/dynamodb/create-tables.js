#!/usr/bin/env node

/**
 * Script to create DynamoDB tables for Aegis
 * Can be used for local development or initial setup
 */

const AWS = require('aws-sdk');
const { program } = require('commander');

// Parse command line arguments
program
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .option('-e, --endpoint <endpoint>', 'DynamoDB endpoint (for local)', '')
  .option('-p, --profile <profile>', 'AWS profile to use', 'default')
  .option('--prefix <prefix>', 'Table name prefix', 'aegis')
  .parse(process.argv);

const options = program.opts();

// Configure AWS SDK
const config = {
  region: options.region,
};

if (options.endpoint) {
  config.endpoint = options.endpoint;
}

if (options.profile && !options.endpoint) {
  const credentials = new AWS.SharedIniFileCredentials({ profile: options.profile });
  config.credentials = credentials;
}

const dynamodb = new AWS.DynamoDB(config);

// Table definitions
const tables = [
  {
    name: `${options.prefix}-incidents`,
    definition: {
      TableName: `${options.prefix}-incidents`,
      KeySchema: [
        { AttributeName: 'PK', KeyType: 'HASH' },
        { AttributeName: 'SK', KeyType: 'RANGE' }
      ],
      AttributeDefinitions: [
        { AttributeName: 'PK', AttributeType: 'S' },
        { AttributeName: 'SK', AttributeType: 'S' },
        { AttributeName: 'GSI1PK', AttributeType: 'S' },
        { AttributeName: 'GSI1SK', AttributeType: 'S' },
        { AttributeName: 'GSI2PK', AttributeType: 'S' },
        { AttributeName: 'GSI2SK', AttributeType: 'S' },
        { AttributeName: 'GSI3PK', AttributeType: 'S' },
        { AttributeName: 'GSI3SK', AttributeType: 'S' }
      ],
      GlobalSecondaryIndexes: [
        {
          IndexName: 'GSI1',
          KeySchema: [
            { AttributeName: 'GSI1PK', KeyType: 'HASH' },
            { AttributeName: 'GSI1SK', KeyType: 'RANGE' }
          ],
          Projection: { ProjectionType: 'ALL' },
          ProvisionedThroughput: {
            ReadCapacityUnits: 5,
            WriteCapacityUnits: 5
          }
        },
        {
          IndexName: 'GSI2',
          KeySchema: [
            { AttributeName: 'GSI2PK', KeyType: 'HASH' },
            { AttributeName: 'GSI2SK', KeyType: 'RANGE' }
          ],
          Projection: { ProjectionType: 'ALL' },
          ProvisionedThroughput: {
            ReadCapacityUnits: 5,
            WriteCapacityUnits: 5
          }
        },
        {
          IndexName: 'GSI3',
          KeySchema: [
            { AttributeName: 'GSI3PK', KeyType: 'HASH' },
            { AttributeName: 'GSI3SK', KeyType: 'RANGE' }
          ],
          Projection: {
            ProjectionType: 'INCLUDE',
            NonKeyAttributes: ['title', 'severity', 'status', 'created_at']
          },
          ProvisionedThroughput: {
            ReadCapacityUnits: 5,
            WriteCapacityUnits: 5
          }
        }
      ],
      BillingMode: 'PROVISIONED',
      ProvisionedThroughput: {
        ReadCapacityUnits: 10,
        WriteCapacityUnits: 10
      },
      StreamSpecification: {
        StreamEnabled: true,
        StreamViewType: 'NEW_AND_OLD_IMAGES'
      },
      SSESpecification: {
        Enabled: true,
        SSEType: 'AES256'
      },
      TimeToLiveSpecification: {
        AttributeName: 'ttl',
        Enabled: true
      },
      Tags: [
        { Key: 'Application', Value: 'Aegis' },
        { Key: 'Environment', Value: options.endpoint ? 'local' : 'dev' }
      ]
    }
  },
  {
    name: `${options.prefix}-idempotency`,
    definition: {
      TableName: `${options.prefix}-idempotency`,
      KeySchema: [
        { AttributeName: 'id', KeyType: 'HASH' }
      ],
      AttributeDefinitions: [
        { AttributeName: 'id', AttributeType: 'S' }
      ],
      BillingMode: 'PAY_PER_REQUEST',
      TimeToLiveSpecification: {
        AttributeName: 'expiration',
        Enabled: true
      },
      SSESpecification: {
        Enabled: true,
        SSEType: 'AES256'
      },
      Tags: [
        { Key: 'Application', Value: 'Aegis' },
        { Key: 'Environment', Value: options.endpoint ? 'local' : 'dev' }
      ]
    }
  }
];

// Helper functions
async function tableExists(tableName) {
  try {
    await dynamodb.describeTable({ TableName: tableName }).promise();
    return true;
  } catch (error) {
    if (error.code === 'ResourceNotFoundException') {
      return false;
    }
    throw error;
  }
}

async function createTable(table) {
  console.log(`Creating table: ${table.name}...`);
  
  try {
    const exists = await tableExists(table.name);
    if (exists) {
      console.log(`✓ Table ${table.name} already exists`);
      return;
    }
    
    await dynamodb.createTable(table.definition).promise();
    console.log(`✓ Table ${table.name} created successfully`);
    
    // Wait for table to be active
    await dynamodb.waitFor('tableExists', { TableName: table.name }).promise();
    console.log(`✓ Table ${table.name} is now active`);
    
  } catch (error) {
    console.error(`✗ Failed to create table ${table.name}:`, error.message);
    throw error;
  }
}

async function setupTables() {
  console.log('Setting up DynamoDB tables for Aegis...\n');
  console.log('Configuration:');
  console.log(`- Region: ${options.region}`);
  console.log(`- Endpoint: ${options.endpoint || 'AWS'}`);
  console.log(`- Table prefix: ${options.prefix}`);
  console.log('');
  
  try {
    for (const table of tables) {
      await createTable(table);
    }
    
    console.log('\n✅ All tables created successfully!');
    
    // Print connection info
    console.log('\nTable Information:');
    tables.forEach(table => {
      console.log(`- ${table.name}`);
    });
    
    if (options.endpoint) {
      console.log(`\nLocal DynamoDB endpoint: ${options.endpoint}`);
      console.log('You can view tables at: http://localhost:8001 (if using dynamodb-admin)');
    }
    
  } catch (error) {
    console.error('\n❌ Table setup failed:', error.message);
    process.exit(1);
  }
}

// Run the setup
setupTables();