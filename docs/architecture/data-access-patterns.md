# Aegis Data Access Patterns

This document describes the DynamoDB single-table design and access patterns for the Aegis incident management platform.

## Table Design

### Primary Table: aegis-incidents

The main table uses a composite primary key:
- **Partition Key (PK)**: String
- **Sort Key (SK)**: String

### Global Secondary Indexes (GSIs)

1. **GSI1**: Status and severity queries
   - PK: `GSI1PK` 
   - SK: `GSI1SK`

2. **GSI2**: User and service queries
   - PK: `GSI2PK`
   - SK: `GSI2SK`

3. **GSI3**: Date-based queries
   - PK: `GSI3PK`
   - SK: `GSI3SK`

## Entity Types

### 1. Incident Metadata
```
PK: INCIDENT#<incident_id>
SK: METADATA
GSI1PK: STATUS#<status>
GSI1SK: SEVERITY#<severity>#INCIDENT#<incident_id>
GSI2PK: SERVICE#<service_name>
GSI2SK: <created_at_timestamp>
```

### 2. Timeline Events
```
PK: INCIDENT#<incident_id>
SK: EVENT#<timestamp>#<event_id>
```

### 3. Comments
```
PK: INCIDENT#<incident_id>
SK: COMMENT#<timestamp>
```

### 4. Participants
```
PK: INCIDENT#<incident_id>
SK: USER#<user_id>
GSI2PK: USER#<user_id>
GSI2SK: INCIDENT#<incident_id>
```

### 5. AI Summaries
```
PK: INCIDENT#<incident_id>
SK: SUMMARY#<timestamp>
```

## Access Patterns

### Pattern 1: Get all data for an incident
**Operation**: Query  
**Index**: Main table  
**Key Condition**: `PK = INCIDENT#<incident_id>`

```javascript
const params = {
  TableName: 'aegis-incidents',
  KeyConditionExpression: 'PK = :pk',
  ExpressionAttributeValues: {
    ':pk': `INCIDENT#${incidentId}`
  }
};
```

### Pattern 2: List incidents by status
**Operation**: Query  
**Index**: GSI1  
**Key Condition**: `GSI1PK = STATUS#<status>`

```javascript
const params = {
  TableName: 'aegis-incidents',
  IndexName: 'GSI1',
  KeyConditionExpression: 'GSI1PK = :status',
  ExpressionAttributeValues: {
    ':status': `STATUS#OPEN`
  }
};
```

### Pattern 3: List incidents by status and severity
**Operation**: Query  
**Index**: GSI1  
**Key Condition**: `GSI1PK = STATUS#<status> AND begins_with(GSI1SK, 'SEVERITY#<severity>')`

```javascript
const params = {
  TableName: 'aegis-incidents',
  IndexName: 'GSI1',
  KeyConditionExpression: 'GSI1PK = :status AND begins_with(GSI1SK, :severity)',
  ExpressionAttributeValues: {
    ':status': 'STATUS#OPEN',
    ':severity': 'SEVERITY#P0'
  }
};
```

### Pattern 4: Get all incidents for a user
**Operation**: Query  
**Index**: GSI2  
**Key Condition**: `GSI2PK = USER#<user_id>`

```javascript
const params = {
  TableName: 'aegis-incidents',
  IndexName: 'GSI2',
  KeyConditionExpression: 'GSI2PK = :user',
  ExpressionAttributeValues: {
    ':user': `USER#${userId}`
  }
};
```

### Pattern 5: Get incidents for a service
**Operation**: Query  
**Index**: GSI2  
**Key Condition**: `GSI2PK = SERVICE#<service_name>`

```javascript
const params = {
  TableName: 'aegis-incidents',
  IndexName: 'GSI2',
  KeyConditionExpression: 'GSI2PK = :service',
  ExpressionAttributeValues: {
    ':service': `SERVICE#payment-service`
  },
  ScanIndexForward: false // Most recent first
};
```

### Pattern 6: Get incidents by date range
**Operation**: Query  
**Index**: GSI3  
**Key Condition**: `GSI3PK = DATE#<date> AND GSI3SK BETWEEN :start AND :end`

```javascript
const params = {
  TableName: 'aegis-incidents',
  IndexName: 'GSI3',
  KeyConditionExpression: 'GSI3PK = :date AND GSI3SK BETWEEN :start AND :end',
  ExpressionAttributeValues: {
    ':date': 'DATE#2025-01-15',
    ':start': 'TIME#2025-01-15T00:00:00Z',
    ':end': 'TIME#2025-01-15T23:59:59Z'
  }
};
```

### Pattern 7: Update incident status
**Operation**: UpdateItem  
**Key**: `PK = INCIDENT#<incident_id>, SK = METADATA`

```javascript
const params = {
  TableName: 'aegis-incidents',
  Key: {
    PK: `INCIDENT#${incidentId}`,
    SK: 'METADATA'
  },
  UpdateExpression: 'SET #status = :status, updated_at = :timestamp, GSI1PK = :gsi1pk',
  ExpressionAttributeNames: {
    '#status': 'status'
  },
  ExpressionAttributeValues: {
    ':status': 'RESOLVED',
    ':timestamp': new Date().toISOString(),
    ':gsi1pk': 'STATUS#RESOLVED'
  }
};
```

### Pattern 8: Add timeline event
**Operation**: PutItem

```javascript
const params = {
  TableName: 'aegis-incidents',
  Item: {
    PK: `INCIDENT#${incidentId}`,
    SK: `EVENT#${timestamp}#${eventId}`,
    type: 'STATUS_CHANGED',
    description: 'Status changed to RESOLVED',
    timestamp: timestamp,
    source: 'System'
  }
};
```

### Pattern 9: Batch get multiple incidents
**Operation**: BatchGetItem

```javascript
const params = {
  RequestItems: {
    'aegis-incidents': {
      Keys: incidentIds.map(id => ({
        PK: `INCIDENT#${id}`,
        SK: 'METADATA'
      }))
    }
  }
};
```

### Pattern 10: Count incidents by status
**Operation**: Query with Select COUNT  
**Index**: GSI1

```javascript
const params = {
  TableName: 'aegis-incidents',
  IndexName: 'GSI1',
  KeyConditionExpression: 'GSI1PK = :status',
  ExpressionAttributeValues: {
    ':status': 'STATUS#OPEN'
  },
  Select: 'COUNT'
};
```

## TTL Strategy

Items with time-to-live:
- Comments older than 90 days
- Timeline events older than 180 days (except key events)
- AI summaries older than 365 days

## Cost Optimization

1. **On-Demand vs Provisioned**
   - Development: Provisioned with auto-scaling
   - Production: On-demand for unpredictable workloads

2. **Index Projections**
   - GSI1 & GSI2: ALL projection for complete data access
   - GSI3: INCLUDE projection with only essential attributes

3. **Archive Strategy**
   - Closed incidents older than 90 days: Move to S3
   - Use DynamoDB Streams to trigger archival Lambda

## Performance Considerations

1. **Hot Partitions**
   - Use incident ID in partition key to distribute load
   - Avoid status-only partition keys for high-volume statuses

2. **Item Size**
   - Keep individual items under 4KB
   - Store large content (post-mortems) in S3 with references

3. **Query Efficiency**
   - Use Query over Scan whenever possible
   - Limit results and implement pagination
   - Use sparse indexes for filtered queries

## Migration Patterns

### Adding New Attributes
```python
# Use UpdateItem with SET if not exists
update_expression = "SET new_attr = if_not_exists(new_attr, :default)"
```

### Changing Index Structure
1. Create new GSI with desired structure
2. Backfill data using DynamoDB Streams
3. Update application to use new GSI
4. Delete old GSI after verification

## Monitoring

Key metrics to monitor:
- ConsumedReadCapacityUnits
- ConsumedWriteCapacityUnits
- UserErrors (4xx)
- SystemErrors (5xx)
- ThrottledRequests
- SuccessfulRequestLatency

## Best Practices

1. **Idempotency**: Use conditional writes to prevent duplicates
2. **Retries**: Implement exponential backoff for throttled requests
3. **Batch Operations**: Use batch writes for multiple items (max 25)
4. **Caching**: Cache frequently accessed metadata in ElastiCache
5. **Monitoring**: Set up CloudWatch alarms for throttling and errors