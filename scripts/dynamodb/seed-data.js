#!/usr/bin/env node

/**
 * Script to seed DynamoDB with sample data for development/testing
 */

const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const { program } = require('commander');
const { faker } = require('@faker-js/faker');

// Parse command line arguments
program
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .option('-e, --endpoint <endpoint>', 'DynamoDB endpoint (for local)', '')
  .option('-p, --profile <profile>', 'AWS profile to use', 'default')
  .option('--prefix <prefix>', 'Table name prefix', 'aegis')
  .option('-n, --num-incidents <number>', 'Number of incidents to create', '20')
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

const dynamodb = new AWS.DynamoDB.DocumentClient(config);
const tableName = `${options.prefix}-incidents`;

// Constants
const SEVERITIES = ['P0', 'P1', 'P2', 'P3', 'P4'];
const STATUSES = ['OPEN', 'ACKNOWLEDGED', 'MITIGATING', 'RESOLVED', 'CLOSED'];
const SERVICES = ['api-gateway', 'payment-service', 'user-service', 'database', 'cache-layer', 'notification-service'];
const SOURCES = ['CloudWatch Alarm', 'Datadog', 'PagerDuty', 'Manual', 'Synthetic Monitor'];
const EVENT_TYPES = [
  'INCIDENT_CREATED',
  'STATUS_CHANGED',
  'SEVERITY_CHANGED',
  'USER_JOINED',
  'COMMENT_ADDED',
  'AUTOMATED_TRIAGE',
  'NOTIFICATION_SENT'
];

const SAMPLE_USERS = [
  { id: 'user-001', name: 'Alice Johnson', role: 'SRE Lead' },
  { id: 'user-002', name: 'Bob Smith', role: 'Backend Engineer' },
  { id: 'user-003', name: 'Carol Davis', role: 'DevOps Engineer' },
  { id: 'user-004', name: 'David Wilson', role: 'Platform Engineer' },
  { id: 'user-005', name: 'Emma Brown', role: 'Site Reliability Engineer' }
];

// Helper functions
function generateIncidentId() {
  return `INC-${Date.now()}-${Math.random().toString(36).substr(2, 9).toUpperCase()}`;
}

function randomElement(array) {
  return array[Math.floor(Math.random() * array.length)];
}

function generateIncidentTitle(service, severity) {
  const issues = [
    'High Error Rate',
    'Connection Timeout',
    'Memory Leak Detected',
    'CPU Utilization Spike',
    'Database Connection Pool Exhausted',
    'API Gateway 5XX Errors',
    'Increased Latency',
    'Service Unavailable',
    'Disk Space Critical',
    'Network Connectivity Issues'
  ];
  
  return `[${severity}] ${service}: ${randomElement(issues)}`;
}

function generateTimestamp(baseTime, offsetMinutes = 0) {
  const date = new Date(baseTime);
  date.setMinutes(date.getMinutes() + offsetMinutes);
  return date.toISOString();
}

async function createIncident(index) {
  const incidentId = generateIncidentId();
  const severity = randomElement(SEVERITIES);
  const status = randomElement(STATUSES);
  const service = randomElement(SERVICES);
  const source = randomElement(SOURCES);
  
  // Base timestamp (random time in the last 30 days)
  const daysAgo = Math.floor(Math.random() * 30);
  const baseTime = new Date();
  baseTime.setDate(baseTime.getDate() - daysAgo);
  baseTime.setHours(Math.floor(Math.random() * 24));
  baseTime.setMinutes(Math.floor(Math.random() * 60));
  
  const createdAt = baseTime.toISOString();
  
  // Create items batch
  const items = [];
  
  // 1. Incident metadata
  const metadata = {
    PK: `INCIDENT#${incidentId}`,
    SK: 'METADATA',
    GSI1PK: `STATUS#${status}`,
    GSI1SK: `SEVERITY#${severity}#INCIDENT#${incidentId}`,
    GSI2PK: `SERVICE#${service}`,
    GSI2SK: createdAt,
    GSI3PK: `DATE#${createdAt.split('T')[0]}`,
    GSI3SK: `TIME#${createdAt}`,
    id: incidentId,
    title: generateIncidentTitle(service, severity),
    description: faker.lorem.paragraph(),
    status,
    severity,
    source,
    service,
    created_at: createdAt,
    updated_at: generateTimestamp(baseTime, Math.random() * 60),
    metadata: {
      service,
      region: randomElement(['us-east-1', 'us-west-2', 'eu-west-1']),
      environment: randomElement(['production', 'staging']),
      alert_count: Math.floor(Math.random() * 50) + 1,
      error_rate: (Math.random() * 100).toFixed(2),
      response_time: Math.floor(Math.random() * 5000) + 100
    }
  };
  
  // Add status-specific timestamps
  if (['ACKNOWLEDGED', 'MITIGATING', 'RESOLVED', 'CLOSED'].includes(status)) {
    metadata.acknowledged_at = generateTimestamp(baseTime, 5);
  }
  if (['RESOLVED', 'CLOSED'].includes(status)) {
    metadata.resolved_at = generateTimestamp(baseTime, 30 + Math.random() * 120);
  }
  if (status === 'CLOSED') {
    metadata.closed_at = generateTimestamp(baseTime, 180 + Math.random() * 60);
  }
  
  items.push(metadata);
  
  // 2. Timeline events
  const numEvents = Math.floor(Math.random() * 10) + 3;
  let timeOffset = 0;
  
  for (let i = 0; i < numEvents; i++) {
    timeOffset += Math.floor(Math.random() * 15) + 1;
    const eventTimestamp = generateTimestamp(baseTime, timeOffset);
    
    items.push({
      PK: `INCIDENT#${incidentId}`,
      SK: `EVENT#${eventTimestamp}#${uuidv4()}`,
      incident_id: incidentId,
      event_id: uuidv4(),
      timestamp: eventTimestamp,
      type: randomElement(EVENT_TYPES),
      description: faker.lorem.sentence(),
      source: randomElement(['System', 'User', 'Automation']),
      metadata: {
        user_id: randomElement(SAMPLE_USERS).id,
        details: faker.lorem.sentence()
      }
    });
  }
  
  // 3. Participants
  const numParticipants = Math.floor(Math.random() * 3) + 1;
  const selectedUsers = faker.helpers.arrayElements(SAMPLE_USERS, numParticipants);
  
  selectedUsers.forEach((user, index) => {
    items.push({
      PK: `INCIDENT#${incidentId}`,
      SK: `USER#${user.id}`,
      GSI2PK: `USER#${user.id}`,
      GSI2SK: `INCIDENT#${incidentId}`,
      incident_id: incidentId,
      user_id: user.id,
      name: user.name,
      role: index === 0 ? 'Incident Commander' : user.role,
      joined_at: generateTimestamp(baseTime, index * 5)
    });
  });
  
  // 4. Comments
  const numComments = Math.floor(Math.random() * 5);
  for (let i = 0; i < numComments; i++) {
    timeOffset += Math.floor(Math.random() * 10) + 5;
    const commentTimestamp = generateTimestamp(baseTime, timeOffset);
    const author = randomElement(selectedUsers);
    
    items.push({
      PK: `INCIDENT#${incidentId}`,
      SK: `COMMENT#${commentTimestamp}`,
      incident_id: incidentId,
      comment_id: uuidv4(),
      timestamp: commentTimestamp,
      author_id: author.id,
      author_name: author.name,
      text: faker.lorem.sentences(Math.floor(Math.random() * 3) + 1)
    });
  }
  
  // 5. AI Summary (for some incidents)
  if (Math.random() > 0.5 && ['RESOLVED', 'CLOSED'].includes(status)) {
    timeOffset += 30;
    items.push({
      PK: `INCIDENT#${incidentId}`,
      SK: `SUMMARY#${generateTimestamp(baseTime, timeOffset)}`,
      incident_id: incidentId,
      summary_id: uuidv4(),
      timestamp: generateTimestamp(baseTime, timeOffset),
      summary_text: faker.lorem.paragraphs(2),
      model_id: 'anthropic.claude-3-sonnet-20240229-v1:0',
      prompt_tokens: Math.floor(Math.random() * 1000) + 500,
      completion_tokens: Math.floor(Math.random() * 500) + 200
    });
  }
  
  // Write batch to DynamoDB
  const batches = [];
  for (let i = 0; i < items.length; i += 25) {
    batches.push(items.slice(i, i + 25));
  }
  
  for (const batch of batches) {
    const params = {
      RequestItems: {
        [tableName]: batch.map(item => ({
          PutRequest: { Item: item }
        }))
      }
    };
    
    await dynamodb.batchWrite(params).promise();
  }
  
  console.log(`✓ Created incident ${index + 1}/${options.numIncidents}: ${incidentId} (${severity}, ${status})`);
  
  return incidentId;
}

async function seedData() {
  console.log('Seeding DynamoDB with sample incident data...\n');
  console.log('Configuration:');
  console.log(`- Region: ${options.region}`);
  console.log(`- Endpoint: ${options.endpoint || 'AWS'}`);
  console.log(`- Table: ${tableName}`);
  console.log(`- Number of incidents: ${options.numIncidents}`);
  console.log('');
  
  try {
    // Check if table exists
    await dynamodb.scan({ TableName: tableName, Limit: 1 }).promise();
    
    const incidentIds = [];
    for (let i = 0; i < parseInt(options.numIncidents); i++) {
      const incidentId = await createIncident(i);
      incidentIds.push(incidentId);
      
      // Small delay to avoid throttling
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    console.log('\n✅ Sample data seeded successfully!');
    console.log('\nCreated incidents:');
    console.log(incidentIds.join('\n'));
    
    // Print some statistics
    const stats = await dynamodb.scan({
      TableName: tableName,
      Select: 'COUNT'
    }).promise();
    
    console.log(`\nTotal items in table: ${stats.Count}`);
    
  } catch (error) {
    console.error('\n❌ Seeding failed:', error.message);
    if (error.code === 'ResourceNotFoundException') {
      console.error(`Table ${tableName} not found. Run create-tables.js first.`);
    }
    process.exit(1);
  }
}

// Run the seeding
seedData();