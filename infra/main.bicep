targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('The azd environment name.')
param environmentName string

@description('Primary Azure region.')
param location string = 'koreacentral'

@description('Object ID running azd, used for ACR remote-build access.')
param principalId string = ''

var tags = {
  'azd-env-name': environmentName
  product: 'meeting-mirror'
}
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var resourceGroupName = 'rg-${environmentName}'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module application './resources.bicep' = {
  name: 'meeting-mirror-resources'
  scope: resourceGroup
  params: {
    location: location
    principalId: principalId
    resourceToken: resourceToken
    tags: tags
  }
}

output AZURE_CONTAINER_ENVIRONMENT_NAME string = application.outputs.environmentName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = application.outputs.registryEndpoint
output AZURE_CONTAINER_REGISTRY_NAME string = application.outputs.registryName
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_TENANT_ID string = tenant().tenantId
output SERVICE_WEB_IMAGE_NAME string = application.outputs.imageName
output SERVICE_WEB_NAME string = application.outputs.appName
output SERVICE_WEB_URI string = application.outputs.appUrl
