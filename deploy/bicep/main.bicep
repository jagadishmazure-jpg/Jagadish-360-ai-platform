// Bicep parity with deploy/terraform/azure. VALIDATED ONLY (bicep build in CI); never deployed from this repo.
param prefix string = 'p360'
param location string = resourceGroup().location
param gpuVmSize string = 'Standard_NC4as_T4_v3'

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${prefix}-kv'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
  }
}

resource aks 'Microsoft.ContainerService/managedClusters@2024-02-01' = {
  name: '${prefix}-aks'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    dnsPrefix: prefix
    disableLocalAccounts: true
    aadProfile: { managed: true, enableAzureRBAC: true }
    oidcIssuerProfile: { enabled: true }
    securityProfile: { workloadIdentity: { enabled: true } }
    networkProfile: { networkPlugin: 'azure', networkPolicy: 'azure' }
    addonProfiles: { azureKeyvaultSecretsProvider: { enabled: true, config: { enableSecretRotation: 'true' } } }
    agentPoolProfiles: [
      { name: 'system', mode: 'System', vmSize: 'Standard_D4s_v5', count: 2 }
      { name: 'gpu', mode: 'User', vmSize: gpuVmSize, count: 1, nodeTaints: [ 'sku=gpu:NoSchedule' ] }
    ]
  }
}
