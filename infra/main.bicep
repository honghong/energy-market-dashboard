// Azure infrastructure for the Energy Market Dashboard.
//
// Deployed in two passes by .github/workflows/deploy.yml:
//   1. deployApps=false  -> registry, Key Vault, identity, PostgreSQL, Container Apps environment
//   2. (image is built into the registry with `az acr build`)
//   3. deployApps=true   -> the web Container App and the scheduled pipeline Container Apps Job

targetScope = 'resourceGroup'

@description('Azure region. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Short prefix for resource names (lowercase letters and digits).')
@minLength(3)
@maxLength(8)
param prefix string = 'emd'

@description('Create the Container App and Job. False on the first pass, before an image exists.')
param deployApps bool = false

@description('Image tag in the registry to run, e.g. the git commit SHA.')
param imageTag string = 'latest'

@description('PostgreSQL administrator login name.')
param postgresAdminUser string = 'energyadmin'

@description('PostgreSQL administrator password.')
@secure()
param postgresAdminPassword string

@description('EIA Open Data API key. Leave empty to run on simulated sample data.')
@secure()
param eiaApiKey string = ''

@description('UTC cron schedule for the ingestion job. Default: 22:30 UTC on weekdays, after EIA daily updates.')
param ingestCron string = '30 22 * * 1-5'

@description('Minimum web replicas. 0 scales to zero when idle (cheapest; first request has a cold start).')
@minValue(0)
@maxValue(1)
param minReplicas int = 0

var suffix = uniqueString(resourceGroup().id)
var names = {
  logs: '${prefix}-logs-${suffix}'
  identity: '${prefix}-id-${suffix}'
  registry: take('${prefix}acr${suffix}', 50)
  keyVault: take('${prefix}-kv-${suffix}', 24)
  postgres: '${prefix}-pg-${suffix}'
  environment: '${prefix}-env-${suffix}'
  app: '${prefix}-web'
  job: '${prefix}-ingest'
}
var databaseName = 'energy'
var hasEiaKey = !empty(eiaApiKey)

// Built-in role definition IDs
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var keyVaultSecretsUserRole = '4633458b-17de-408a-b874-0445c86b69e6'

// ---------------------------------------------------------------- monitoring

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.logs
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------- identity + secrets

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.identity
  location: location
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: names.registry
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, acrPullRole)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: names.keyVault
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identity.id, keyVaultSecretsUserRole)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      keyVaultSecretsUserRole
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------- database

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' = {
  name: names.postgres
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2022-12-01' = {
  parent: postgres
  name: databaseName
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// Allows connections from Azure services (the Container Apps). TLS is required by the server.
resource allowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2022-12-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource dbUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: 'postgresql+psycopg://${postgresAdminUser}:${uriComponent(postgresAdminPassword)}@${postgres.properties.fullyQualifiedDomainName}:5432/${databaseName}?sslmode=require'
  }
}

resource eiaSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (hasEiaKey) {
  parent: keyVault
  name: 'eia-api-key'
  properties: { value: eiaApiKey }
}

// ---------------------------------------------------------------- container apps

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: names.environment
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var image = '${registry.properties.loginServer}/energy-dashboard:${imageTag}'

var appSecrets = concat(
  [
    {
      name: 'database-url'
      keyVaultUrl: dbUrlSecret.properties.secretUri
      identity: identity.id
    }
  ],
  hasEiaKey
    ? [
        {
          name: 'eia-api-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/eia-api-key'
          identity: identity.id
        }
      ]
    : []
)

var appEnv = concat(
  [
    { name: 'DATABASE_URL', secretRef: 'database-url' }
    { name: 'DATA_SOURCE', value: hasEiaKey ? 'eia' : 'sample' }
  ],
  hasEiaKey ? [{ name: 'EIA_API_KEY', secretRef: 'eia-api-key' }] : []
)

resource web 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: names.app
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  dependsOn: [acrPull, kvSecretsUser, database, allowAzure, eiaSecret]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
      secrets: appSecrets
    }
    template: {
      containers: [
        {
          name: 'web'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: appEnv
          probes: [
            {
              type: 'Readiness'
              httpGet: { path: '/api/health', port: 8000 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
            {
              type: 'Liveness'
              httpGet: { path: '/api/health', port: 8000 }
              initialDelaySeconds: 15
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 1
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '50' } } }]
      }
    }
  }
}

resource ingestJob 'Microsoft.App/jobs@2024-03-01' = if (deployApps) {
  name: names.job
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  dependsOn: [acrPull, kvSecretsUser, database, allowAzure, eiaSecret]
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: ingestCron
        parallelism: 1
        replicaCompletionCount: 1
      }
      replicaTimeout: 1800
      replicaRetryLimit: 1
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
      secrets: appSecrets
    }
    template: {
      containers: [
        {
          name: 'ingest'
          image: image
          command: ['python', '-m', 'app.pipeline']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: appEnv
        }
      ]
    }
  }
}

// ---------------------------------------------------------------- outputs

output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output appName string = names.app
output jobName string = names.job
output appUrl string = deployApps ? 'https://${web!.properties.configuration.ingress.fqdn}' : ''
