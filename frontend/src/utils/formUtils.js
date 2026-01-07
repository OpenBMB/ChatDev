export const isListField = (field) => {
  return field.type && field.type.includes('list[')
}

export const hasChildRoutes = (field) => {
  return Array.isArray(field?.childRoutes) && field.childRoutes.length > 0
}

export const isInlineConfigField = (field) => {
  return hasChildRoutes(field) && !isListField(field)
}

export const getSchemaFields = (modal) => {
  return modal?.schema?.fields || []
}

export const getDisplayFields = (modal) => {
  return getSchemaFields(modal)
}

export const determineRouteControllerField = (modal, field) => {
  if (!hasChildRoutes(field)) {
    return null
  }
  const schemaFields = getSchemaFields(modal)
  const preferredTypeField = schemaFields.find(entry => entry.name === 'type')
  if (preferredTypeField) {
    return preferredTypeField.name
  }
  const routeValues = field.childRoutes
    .map(route => route?.childKey?.value)
    .filter(value => value !== undefined && value !== null)
  if (!routeValues.length) {
    const fallbackField = schemaFields.find(entry => Array.isArray(entry.enum) && entry.enum.length)
    return fallbackField ? fallbackField.name : null
  }
  const matchingEnumField = schemaFields.find(
    entry => Array.isArray(entry.enum) && routeValues.every(value => entry.enum.includes(value))
  )
  return matchingEnumField ? matchingEnumField.name : null
}

export const getActiveChildRoute = (modal, field) => {
  if (!hasChildRoutes(field)) {
    return null
  }
  const routes = field.childRoutes || []
  if (!routes.length) {
    return null
  }
  const controllerFieldName = determineRouteControllerField(modal, field)
  if (!controllerFieldName) {
    return routes[0]
  }
  const controllerValue = modal.formData?.[controllerFieldName]
  return routes.find(route => {
    const keyValue = route?.childKey?.value
    if (keyValue === undefined || keyValue === null) {
      return controllerValue === undefined || controllerValue === null || controllerValue === ''
    }
    return keyValue === controllerValue
  }) || null
}

export const canOpenConditionalChildModal = (modal, field) => {
  return Boolean(getActiveChildRoute(modal, field))
}

export const getConditionalChildKeyValue = (modal, field) => {
  const route = getActiveChildRoute(modal, field)
  if (route?.childKey?.value) {
    return route.childKey.value
  }
  if (field.childKey?.value) {
    return field.childKey.value
  }
  return null
}

export const isFieldVisible = (modal, field) => {
  if (!field?.advance) {
    return true
  }
  return Boolean(modal?.showAdvanced)
}

export const childNodeButtonLabel = (modal, field) => {
  if (isListField(field)) {
    return `Add Entry`
  }
  return modal.formData[field.name] ? `Edit ${field.childNode}` : `Configure ${field.childNode}`
}

export const conditionalChildButtonLabel = (modal, field) => {
  if (!canOpenConditionalChildModal(modal, field)) {
    return 'Configure'
  }
  const childNodeName = getConditionalChildKeyValue(modal, field)
  return modal.formData[field.name] ? `Edit ${childNodeName}` : `Configure ${childNodeName}`
}
